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
from modules.api.daemon_api import DAEMON_STATUS_DOWN, DAEMON_STATUS_PENDING, SECRET_HEADER_KEY, DAEMON_STATUS_UP
from modules.shared import cmd_opts


class ServiceNotAvailableException(HTTPException):
    def __init__(
            self,
            status_code: int,
            detail: Any = None,
            headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)


_restarted = 0
_started_at = datetime.datetime.now()


def start_with_daemon(service_func):
    import psutil

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

    session = requests.Session()

    # create service process at startup
    service, server_port, starting_flag = _renew_service(service, service_func, server_port)
    while True:
        try:
            # get service status
            status = _get_service_status(session, server_port, 6 if starting_flag else 1)
            starting_flag = False
            memory_usage = psutil.virtual_memory()
            pending_task_info = _get_service_pending_task_info(session, server_port)
            current_task = pending_task_info.get('current_task', '')
            queued_tasks = pending_task_info.get('queued_tasks', {})

            # not enough memory, BE should turn to pending (out-of-service)
            available_memory = memory_usage.available / (1024 * 1024 * 1024)
            if status != DAEMON_STATUS_DOWN and available_memory < cmd_opts.ram_size_to_pending:  # 5GB
                # convert timestamp to time str
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

                logging.warning(
                    f"insufficient ram: {available_memory:0.2f}/{cmd_opts.ram_size_to_pending:.2f}GB, current_task: '{current_task}', queued_tasks: {queued_tasks_list}"
                )
                status = DAEMON_STATUS_PENDING
                _set_service_status(session, server_port, status)

            # check if service should restart at once.
            if available_memory < cmd_opts.ram_size_to_restart:
                # service is OOM, force to restart it
                logging.warning(
                    f'service is out of memory: {available_memory:0.2f}/{cmd_opts.ram_size_to_restart:.2f}GB, restart it'
                )
                _heartbeat(redis_client,
                           host_ip,
                           server_port,
                           DAEMON_STATUS_DOWN,
                           memory_usage,
                           current_task,
                           queued_tasks)
                # renew service
                service, server_port, starting_flag = _renew_service(service, service_func, server_port)
                continue

            # send heartbeat event
            _heartbeat(redis_client,
                       host_ip,
                       server_port,
                       status,
                       memory_usage,
                       current_task,
                       queued_tasks)

            # handle idle
            if not current_task and len(queued_tasks) == 0:
                if status == DAEMON_STATUS_PENDING:
                    # try to restart BE if out-of-service no pending tasks
                    logging.warning(f'insufficient vram, restart service now')
                    # service is going to restart, no requests will be accepted anymore
                    _heartbeat(redis_client,
                               host_ip,
                               server_port,
                               DAEMON_STATUS_DOWN,
                               memory_usage,
                               current_task,
                               queued_tasks)
                    # renew service
                    service, server_port, starting_flag = _renew_service(service, service_func, server_port)
                elif status == DAEMON_STATUS_DOWN:
                    # service is going to down, exit main process
                    logging.warning(f'service is down, exit process now')
                    service.terminate()
                    service.join()
                    break
                else:
                    pass
        except ServiceNotAvailableException as e:
            # service process is not responding, kill it and relaunch
            logging.warning(f'service is not responding, kill it and relaunch')
            service, server_port, starting_flag = _renew_service(service, service_func, server_port)
            session = requests.Session()
        except Exception as e:
            logging.error(f'error in heartbeat: {e.__str__()}')
            time.sleep(3)
            session = requests.Session()
            redis_client = _get_redis_client()
        time.sleep(1)

    logging.info(f'exit')


def _make_time_str(t):
    return datetime.datetime.utcfromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S')


def _renew_service(service: Process | None, service_func, server_port):
    if service:
        logging.info('release current service process')
        service.terminate()
        service.join()
        service.close()
        # use a new port to launch service, since gradio may not able to release current port correctly
        server_port += 1

        global _restarted
        _restarted += 1

    logging.info(f'create new service process on port {server_port}')
    service = Process(target=service_func, args=(server_port,))
    service.start()
    time.sleep(3)
    return service, server_port, True


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
               ):
    # no need to send heart beat event if host_ip or redis_address missed
    if not redis_client or not host_ip:
        return
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
        'restarted': _restarted,
        'started_at': _started_at.strftime('%Y-%m-%d %H:%M:%S')
    }

    instance_id = f'webui_be_{host_ip}:{port}'
    redis_client.set(name=instance_id, value=json.dumps(data, ensure_ascii=False, sort_keys=True), ex=3)


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
            logging.warning(f"get_service_status from 'http://localhost:{port}' failed, try again: {e.__str__()}")
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
