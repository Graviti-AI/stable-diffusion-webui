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

_node_accepted_tiers = os.getenv('ACCEPTED_TIERS', '').split(',')


class ServiceNotAvailableException(HTTPException):
    def __init__(
            self,
            status_code: int,
            detail: Any = None,
            headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)


_service_restart_count = 0


def start_with_daemon(service_func):
    import psutil
    _system_started_at = datetime.datetime.now()

    # set multiprocessing to start service process in spawn mode, to fix CUDA complain 'To use CUDA
    # with multiprocessing, you must use the ‘spawn‘ start method'
    multiprocessing.set_start_method('spawn')

    # server info
    host_ip = os.getenv('HOST_IP', default='')
    server_port = cmd_opts.port if cmd_opts.port else 7860

    # redis for heart beat
    redis_client = _get_redis_client()

    # use a sub-process to run service
    service: Process | None = None

    # request session for getting service status
    session = requests.Session()

    # create service process at startup
    starting_flag = True
    service, server_port, starting_flag, _service_pending_from, previous_service_status = _renew_service(
        service,
        service_func,
        server_port,
        starting_flag)

    while True:
        try:
            # get service status
            current_service_status = _get_service_status(session, server_port, 6 if starting_flag else 3)
            starting_flag = False
            memory_usage = psutil.virtual_memory()
            pending_task_info = _get_service_pending_task_info(session, server_port)
            current_task = pending_task_info.get('current_task', '')
            queued_tasks = pending_task_info.get('queued_tasks', {})
            finished_task_count = pending_task_info.get('finished_task_count', 0)

            # not enough memory, BE should turn to pending (out-of-service)
            available_memory = memory_usage.available / (1024 * 1024 * 1024)
            if current_service_status != DAEMON_STATUS_DOWN and available_memory < cmd_opts.ram_size_to_pending:
                # convert timestamp to time str
                queued_tasks_list = _fix_time_str_for_queued_tasks(queued_tasks)
                logger.warning(
                    f"insufficient ram: {available_memory:0.2f}/{cmd_opts.ram_size_to_pending:.02f}GB, current_task: '{current_task}', queued_tasks: {queued_tasks_list}"
                )
                current_service_status = DAEMON_STATUS_PENDING
                _set_service_status(session, server_port, current_service_status)

            # check if service should restart at once.
            if available_memory < cmd_opts.ram_size_to_restart:
                # service is OOM, force to restart it
                logger.warning(
                    f'service is out of memory: {available_memory:0.2f}/{cmd_opts.ram_size_to_restart:.2f}GB, restart it'
                )
                # renew service
                service, server_port, starting_flag, _service_pending_from, previous_service_status = _renew_service(
                    service,
                    service_func,
                    server_port,
                    starting_flag)
                continue

            # send heartbeat event
            _heartbeat(redis_client,
                       host_ip,
                       server_port,
                       current_service_status,
                       memory_usage,
                       current_task,
                       queued_tasks,
                       _system_started_at,
                       finished_task_count)

            # calculate service pending duration
            if previous_service_status != current_service_status:
                previous_service_status = current_service_status
                if current_service_status in (
                        DAEMON_STATUS_DOWN, DAEMON_STATUS_PENDING
                ) and _service_pending_from is None:
                    logger.warning(
                        f"service status turned into {current_service_status}"
                    )
                    _service_pending_from = datetime.datetime.now()

            if _service_pending_from:
                pending_duration = (datetime.datetime.now() - _service_pending_from).total_seconds()
                logger.warning(f"service is {current_service_status} for {pending_duration:0.2f}s")
            else:
                pending_duration = 0

            # service should restart or shutdown if idle or pending for more than 60 seconds
            if not current_task and pending_duration > cmd_opts.maximum_system_pending_time:
                if current_service_status == DAEMON_STATUS_PENDING:
                    # restart BE if out-of-service
                    logger.warning(
                        f'insufficient vram, restart service now, pending_duration: {pending_duration:0.2f}s, queued_tasks_len: {len(queued_tasks)}'
                    )
                    # renew service
                    service, server_port, starting_flag, _service_pending_from, previous_service_status = _renew_service(
                        service,
                        service_func,
                        server_port,
                        starting_flag)
                elif current_service_status == DAEMON_STATUS_DOWN:
                    # service is going to down, exit main process
                    logger.warning(f'service is down, exit process now')
                    service.terminate()
                    service.join()
                    break
                else:
                    pass
        except ServiceNotAvailableException as e:
            logger.warning(f'service is not responding')
            session = requests.Session()
            if starting_flag:
                # service process is not responding, kill it and relaunch
                # it may happened at startup due to port inuse
                logger.warning(f'service is not responding, kill at restart it')
                service, server_port, starting_flag, _service_pending_from, previous_service_status = _renew_service(
                    service,
                    service_func,
                    server_port,
                    starting_flag)
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


def _renew_service(service: Process | None, service_func, server_port, starting_flag):
    if service:
        logger.info('release current service process')
        service.terminate()
        service.join()
        service.close()
        # use a new port to launch service, since gradio may not able to release current port correctly
        server_port += 1

        if not starting_flag:
            global _service_restart_count
            _service_restart_count += 1

    logger.info(f'create new service process on port {server_port}')
    service = Process(target=service_func, args=(server_port,))
    service.start()
    time.sleep(5)
    return service, server_port, True, None, ''


def _get_redis_client():
    import redis.client
    redis_address = os.getenv('REDIS_ADDRESS', default='')
    if redis_address:
        redis_client = redis.Redis.from_url(url=redis_address)
    else:
        redis_client = None
    return redis_client


def _heartbeat(redis_client,
               host_ip: str,
               port: int,
               status: str,
               memory_usage,
               current_task: str,
               queued_tasks: dict,
               system_started_at,
               finished_task_count: int,
               ):
    # no need to send heart beat event if host_ip or redis_address missed
    if not redis_client or not host_ip:
        return
    if not _node_accepted_tiers:
        logger.error(f'invalid node accepted tiers info: {_node_accepted_tiers}')
    else:
        for accept in _node_accepted_tiers:
            if not accept:
                logger.error(f'invalid node accepted tiers info: {_node_accepted_tiers}')
                break

    data = {
        'status': status,
        'mem_usage': {
            'total': memory_usage.total,
            'available': memory_usage.available,
            'percent': memory_usage.percent,
            'used': memory_usage.used,
            'free': memory_usage.free,
        },
        'current_task': current_task,
        'queued_tasks': queued_tasks,
        'ip': host_ip,
        'port': port,
        'schema': 'http',
        'restarted': _service_restart_count,
        'started_at': system_started_at.strftime('%Y-%m-%d %H:%M:%S'),
        'finished_task_count': finished_task_count,
        'labels': {
            'node/accepted-tiers': _node_accepted_tiers
        }
    }

    instance_id = f'webui_be_{host_ip}:{port}'
    redis_client.set(
        name=instance_id,
        value=json.dumps(data, ensure_ascii=False, sort_keys=True),
        ex=cmd_opts.heartbeat_expiration
    )


def _get_service_status(session: requests.sessions.Session, port: int, try_count: int = 3) -> str:
    remaining_try_count = try_count
    code = 200
    while remaining_try_count > 0:
        try:
            headers = {
                SECRET_HEADER_KEY: modules.shared.cmd_opts.system_monitor_api_secret
            }
            resp = session.get(f'http://localhost:{port}/daemon/v1/status',
                               headers=headers,
                               timeout=1)
            code = resp.status_code
            if 199 < code < 400:
                data = resp.json()
                return data.get('status', '')
        except Exception as e:
            logger.warning(f"get_service_status from 'http://localhost:{port}' failed, try again: {e.__str__()}")
        finally:
            remaining_try_count -= 1
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


def _get_int_value_from_environment(key: str, default_value: int, min_value: int | None) -> int:
    value = os.getenv(key, default=default_value)
    result = int(value)
    if min_value is not None and result < min_value:
        result = min_value

    return result
