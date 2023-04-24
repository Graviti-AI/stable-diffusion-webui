import datetime
import json
import logging
import multiprocessing
import os
import time
from multiprocessing import Process
from typing import Any, Dict, Optional

import requests
from fastapi import HTTPException

import modules.shared
from modules.api.daemon_api import DAEMON_STATUS_DOWN, DAEMON_STATUS_PENDING, SECRET_HEADER_KEY
from modules.shared import cmd_opts

logger = logging.getLogger(__name__)


class ServiceNotAvailableException(HTTPException):
    def __init__(
            self,
            status_code: int,
            detail: Any = None,
            headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class ServiceStatus:
    try:
        import version
        release_version = version.version
    except Exception as e:
        logger.error(f'find release version failed: {e.__str__()}')
        release_version = ''

    system_deployed_at = datetime.datetime.now()
    host_ip = os.getenv('HOST_IP', default='')
    node_name = os.getenv('NODE_NAME', '')
    node_accepted_tiers = os.getenv('ACCEPTED_TIERS', '').split(',')
    server_port = cmd_opts.port if cmd_opts.port else 7860

    service_restarted_at = datetime.datetime.now()
    service_idled_at = None
    service_pending_at = None

    starting_flag = True
    state = None
    service_restart_count = 0
    current_task = None
    queued_tasks = None
    memory_usage = None
    finished_task_count = 0


def start_with_daemon(service_func):
    import psutil
    service_status = ServiceStatus()

    # set multiprocessing to start service process in spawn mode, to fix CUDA complain 'To use CUDA
    # with multiprocessing, you must use the ‘spawn‘ start method'
    multiprocessing.set_start_method('spawn')

    # server info
    logger.info(
        f'launch service at 0.0.0.0:{service_status.server_port}, '
        f'node_name: {service_status.node_name}, '
        f'node_accepted_tiers: {service_status.node_accepted_tiers}, '
        f'release_version: {service_status.release_version}'
    )

    # redis for heart beat
    redis_client = _get_redis_client()

    # use a sub-process to run service
    service: Optional[Process] = None

    # request session for getting service status
    session = requests.Session()

    # create service process at startup

    service = _renew_service(
        service,
        service_func,
        service_status)

    while True:
        try:
            # get service status
            current_service_state = _get_service_status(session, service,
                                                        service_status.server_port,
                                                        15 if service_status.starting_flag else 3)
            # service is started normally, reset starting_flag to False
            service_status.starting_flag = False

            # fetch current tasks
            pending_task_info = _get_service_pending_task_info(session, service_status.server_port)
            service_status.current_task = pending_task_info.get('current_task', '')
            service_status.queued_tasks = pending_task_info.get('queued_tasks', {})
            service_status.finished_task_count = pending_task_info.get('finished_task_count', 0)

            # check if service is idle:
            if service_status.current_task or len(service_status.queued_tasks) > 0:
                service_status.service_idled_at = None
            elif not service_status.service_idled_at:
                service_status.service_idled_at = datetime.datetime.now()

            # check system memory
            service_status.memory_usage = psutil.virtual_memory()
            available_memory = service_status.memory_usage.available / (1024 * 1024 * 1024)
            if current_service_state != DAEMON_STATUS_DOWN and available_memory < cmd_opts.ram_size_to_pending:
                # not enough memory, BE should turn to pending (out-of-service)
                queued_tasks_list = _fix_time_str_for_queued_tasks(service_status.queued_tasks)
                logger.warning(
                    f"insufficient ram: {available_memory:0.2f}/{cmd_opts.ram_size_to_pending:.02f}GB, "
                    f"current_task: '{service_status.current_task}', "
                    f"queued_tasks: {queued_tasks_list}"
                )
                current_service_state = DAEMON_STATUS_PENDING
                _set_service_status(session, service_status.server_port, current_service_state)

            # check if service should restart at once.
            if available_memory < cmd_opts.ram_size_to_restart:
                # service is OOM, force to restart it
                logger.warning(
                    f'service is out of memory: {available_memory:0.2f}/{cmd_opts.ram_size_to_restart:.2f}GB, '
                    'restart it now'
                )
                # renew service
                service = _renew_service(
                    service,
                    service_func,
                    service_status)
                continue

            # send heartbeat event
            _heartbeat(redis_client, service_status)

            # calculate service pending duration
            if service_status.state != current_service_state:
                logger.info(
                    f'service status updated: '
                    f'{service_status.state} -> {current_service_state}'
                )
                service_status.state = current_service_state
                if current_service_state in (
                        DAEMON_STATUS_DOWN, DAEMON_STATUS_PENDING
                ) and service_status.service_pending_at is None:
                    logger.warning(
                        f"service status turned into {current_service_state}"
                    )
                    service_status.service_pending_at = datetime.datetime.now()

            # log pending duration
            if service_status.service_pending_at:
                pending_duration = (datetime.datetime.now() - service_status.service_pending_at).total_seconds()
                logger.warning(f"service is {current_service_state} for {pending_duration:0.2f}s")
            else:
                pending_duration = 0

            # service should restart or shutdown if idle and pending for more than 60 seconds
            if not service_status.current_task and pending_duration > cmd_opts.maximum_system_pending_time:
                if current_service_state == DAEMON_STATUS_PENDING:
                    # restart BE if out-of-service
                    logger.warning(
                        f'insufficient ram, restart service now, '
                        f'pending_duration: {pending_duration:0.2f}s, '
                        f'queued_tasks_len: {len(service_status.queued_tasks)}'
                    )
                    # renew service
                    service = _renew_service(
                        service,
                        service_func,
                        service_status)
                elif current_service_state == DAEMON_STATUS_DOWN:
                    # service is going to down, exit main process
                    logger.warning(f'service is down, exit process now')
                    service.terminate()
                    service.join()
                    break
                else:
                    pass
        except ServiceNotAvailableException as e:
            logger.warning(f'service is not responding: {e.__str__()}')
            session = requests.Session()
            if service_status.starting_flag:
                # service process is not responding, kill it and relaunch
                # it may happened at startup due to port inuse
                logger.warning(f'service is not responding, kill at restart it')
                service = _renew_service(
                    service,
                    service_func,
                    service_status)
        except Exception as e:
            logger.error(f'error in heartbeat: {e.__str__()}')
            time.sleep(3)
            session = requests.Session()
            redis_client = _get_redis_client()
        time.sleep(1)

    logger.info(f'exit')


def _make_time_str(t):
    return datetime.datetime.utcfromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S')


def _fix_time_str_for_queued_tasks(queued_tasks):
    queued_tasks_list = []
    for task_id, task_info in queued_tasks.items():
        added_at = task_info.get('added_at', 0)
        last_accessed_at = task_info.get('last_accessed_at', 0)
        inactivated = time.time() - last_accessed_at
        fixed_task_info = {
            'task_id': task_id,
            'added_at': _make_time_str(added_at),
            'last_accessed_at': _make_time_str(last_accessed_at),
            'inactivated': f'{int(inactivated)}s'
        }
        task_info.update(fixed_task_info)
        queued_tasks_list.append(task_info)

    return queued_tasks_list


def _renew_service(service: Optional[Process], service_func, service_status: ServiceStatus):
    if service:
        logger.info('release current service process')
        service.terminate()
        service.join()
        service.close()
        # use a new port to launch service, since gradio may not able to release current port correctly
        service_status.server_port += 1

        if not service_status.starting_flag:
            service_status.service_restart_count += 1

    logger.info(f'create new service process on port {service_status.server_port}')
    service = Process(target=service_func, args=(service_status.server_port,))
    service.start()
    time.sleep(5)
    service_status.starting_flag = True
    service_status.service_pending_at = None
    service_status.state = 'starting'
    service_status.service_restarted_at = datetime.datetime.now()
    service_status.service_idled_at = None
    return service


def _get_redis_client():
    import redis.client
    redis_address = os.getenv('REDIS_ADDRESS', default='')
    if redis_address:
        redis_client = redis.Redis.from_url(url=redis_address)
    else:
        redis_client = None
    return redis_client


def _heartbeat(redis_client,
               service_status: ServiceStatus
               ):
    # no need to send heart beat event if host_ip or redis_address missed
    if not redis_client or not service_status.host_ip:
        return
    if not service_status.node_accepted_tiers:
        logger.error(f'invalid node accepted tiers info: {service_status.node_accepted_tiers}')
    else:
        for accept in service_status.node_accepted_tiers:
            if not accept:
                logger.error(f'invalid node accepted tiers info: {service_status.node_accepted_tiers}')
                break

    data = {
        'status': service_status.state,
        'ip': service_status.host_ip,
        'port': service_status.server_port,
        'schema': 'http',
        'release_version': service_status.release_version,
        'mem_usage': {
            'total': service_status.memory_usage.total,
            'available': service_status.memory_usage.available,
            'percent': service_status.memory_usage.percent,
            'used': service_status.memory_usage.used,
            'free': service_status.memory_usage.free,
        },
        'current_task': service_status.current_task,
        'queued_tasks': service_status.queued_tasks,
        'restarted_count': service_status.service_restart_count,
        'finished_task_count': service_status.finished_task_count,
        'timestamps': {
            'deployed_at': service_status.system_deployed_at.strftime('%Y-%m-%d %H:%M:%S'),
            'restarted_at': service_status.service_restarted_at.strftime('%Y-%m-%d %H:%M:%S'),
            'idled_at': service_status.service_idled_at.strftime(
                '%Y-%m-%d %H:%M:%S') if service_status.service_idled_at else '',
            'pending_at': service_status.service_pending_at.strftime(
                '%Y-%m-%d %H:%M:%S') if service_status.service_pending_at else '',
        },
        'labels': {
            'node/accepted-tiers': service_status.node_accepted_tiers,
            'node/instance-name': service_status.node_name,
        }
    }

    instance_id = f'webui_be_{service_status.host_ip}:{service_status.server_port}'
    redis_client.set(
        name=instance_id,
        value=json.dumps(data, ensure_ascii=False, sort_keys=True),
        ex=cmd_opts.heartbeat_expiration
    )


def _get_service_status(session: requests.sessions.Session, service: Process, port: int, try_count: int = 3) -> str:
    remaining_try_count = try_count
    code = 200
    while remaining_try_count > 0:
        try:
            headers = {
                SECRET_HEADER_KEY: modules.shared.cmd_opts.system_monitor_api_secret
            }
            resp = session.get(f'http://localhost:{port}/daemon/v1/status',
                               headers=headers,
                               timeout=2)
            code = resp.status_code
            if 199 < code < 400:
                data = resp.json()
                return data.get('status', '')
        except Exception as e:
            logger.warning(f"get_service_status from 'http://localhost:{port}' failed, try again: {e.__str__()}")
        finally:
            remaining_try_count -= 1
        if not service.is_alive():
            logger.error('get_service_status: service is not alive, stop retry')
            break
        time.sleep(try_count - remaining_try_count)

    raise ServiceNotAvailableException(status_code=code, detail=f'set_service_status: failed')


def _set_service_status(session: requests.sessions.Session, port: int, status: str, try_count: int = 3):
    remaining_try_count = try_count
    code = 200
    while remaining_try_count > 0:
        try:
            headers = {
                SECRET_HEADER_KEY: modules.shared.cmd_opts.system_monitor_api_secret
            }
            resp = session.put(f'http://localhost:{port}/daemon/v1/status',
                               headers=headers,
                               json={
                                   'status': status,
                               },
                               timeout=1)
            code = resp.status_code
            if 199 < code < 400:
                return
        finally:
            remaining_try_count -= 1
        time.sleep(try_count - remaining_try_count)
    raise ServiceNotAvailableException(status_code=code, detail=f'set_service_status: failed')


def _get_service_pending_task_info(session: requests.sessions.Session, port: int, try_count: int = 3) -> dict:
    remaining_try_count = try_count
    code = 200
    while remaining_try_count > 0:
        try:
            headers = {
                SECRET_HEADER_KEY: modules.shared.cmd_opts.system_monitor_api_secret
            }
            resp = session.get(f'http://localhost:{port}/daemon/v1/pending-task-count',
                               headers=headers,
                               timeout=1)
            code = resp.status_code
            if 199 < code < 400:
                return resp.json()
        finally:
            remaining_try_count -= 1
        time.sleep(try_count - remaining_try_count)
    raise ServiceNotAvailableException(status_code=code, detail='get_service_pending_task_info: failed')


def _get_int_value_from_environment(key: str, default_value: int, min_value: Optional[int]) -> int:
    value = os.getenv(key, default=default_value)
    result = int(value)
    if min_value is not None and result < min_value:
        result = min_value

    return result
