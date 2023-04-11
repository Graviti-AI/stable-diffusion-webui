import json
import logging
import multiprocessing
import os
import time
from multiprocessing import Process
from typing import Any, Dict, Optional

import psutil
import redis.client
import requests
from fastapi import HTTPException

import modules.shared
from modules.api.daemon_api import DAEMON_STATUS_DOWN, DAEMON_STATUS_PENDING, SECRET_HEADER_KEY
from modules.shared import cmd_opts


class ServiceNotAvailableException(HTTPException):
    def __init__(
            self,
            status_code: int,
            detail: Any = None,
            headers: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)


def start_with_daemon(service_func):
    # set multiprocessing to start service process in spawn mode, to fix CUDA complain 'To use CUDA
    # with multiprocessing, you must use the ‘spawn‘ start method'
    multiprocessing.set_start_method('spawn')

    # server info
    host_ip = os.getenv('HOST_IP', default='')
    port = cmd_opts.port if cmd_opts.port else 7860

    # redis for heart beat
    redis_client = _get_redis_client()

    # use a sub-process to run service
    service: Process | None = None
    starting_flag = True

    session = requests.Session()
    while True:
        try:
            if service is None:
                service = Process(target=service_func)
                service.start()
                # at startup time, get service status may fail, need retry
                starting_flag = True

            # get service status
            status = _get_service_status(session, port, 5 if starting_flag else 1)
            memory_usage = psutil.virtual_memory()
            memory_used_percent = memory_usage.percent
            pending_task_info = _get_service_pending_task_info(session, port)

            # not enough memory, BE should turn to out-of-service
            available_memory = memory_usage.available / (1024 * 1024 * 1024)
            if status != DAEMON_STATUS_DOWN and available_memory < cmd_opts.minimum_ram_size:  # 5GB
                logging.warning(
                    f'insufficient vram: {available_memory:0.2f}/{cmd_opts.minimum_ram_size:.2f}GB, pending_task: {pending_task_info}'
                )
                status = DAEMON_STATUS_PENDING
                _set_service_status(session, port, status)

            # heartbeat
            if host_ip and redis_client is not None:
                # no need to send heart beat event if host_ip or redis_address missed
                _heartbeat(redis_client, host_ip, port, status, memory_used_percent, pending_task_info)

            # handle idle
            if not pending_task_info.get('current_task', '') and pending_task_info.get('pending_task_count', 0) == 0:
                if status == DAEMON_STATUS_PENDING:
                    # try to restart BE if out-of-service no pending tasks
                    logging.warning(f'insufficient vram, restart service now')
                    service.terminate()
                    service = None
                elif status == DAEMON_STATUS_DOWN:
                    # service is going to down, exit main process
                    logging.warning(f'service is down, exit process now')
                    service.terminate()
                    service = None
                    break
                else:
                    pass
        except ServiceNotAvailableException as e:
            # service process is not responding, kill it and relaunch
            logging.warning(f'service is not responding, kill it and relaunch')
            service.terminate()
            service = None
            session = requests.Session()
        except Exception as e:
            logging.error(f'error in heartbeat: {e.__str__()}')
            time.sleep(3)
            session = requests.Session()
            redis_client = _get_redis_client()
        starting_flag = False
        time.sleep(1)

    logging.info(f'exit')


def _get_redis_client():
    redis_address = os.getenv('REDIS_ADDRESS', default='')
    if redis_address:
        redis_client = redis.Redis.from_url(url=redis_address)
    else:
        redis_client = None
    return redis_client


def _heartbeat(redis_client: redis.Redis,
               host_ip: str,
               port: int,
               status: str,
               memory_used_percent: float,
               pending_task_info: dict):
    data = {
        'status': status,
        'mem_usage_percentage': memory_used_percent,
        'pending_task_count': pending_task_info.get('pending_task_count', 0),
    }

    service_addr = f'http://{host_ip}:{port}'
    redis_client.set(name=service_addr, value=json.dumps(data, ensure_ascii=False, sort_keys=True), ex=3)


def _get_service_status(session: requests.sessions.Session, port: int, try_count: int = 1) -> str:
    code = 200
    while try_count > 0:
        try:
            headers = {
                SECRET_HEADER_KEY: modules.shared.cmd_opts.system_monitor_api_secret
            }
            resp = session.get(f'http://localhost:{port}/daemon/v1/status', headers=headers)
            code = resp.status_code
            if 199 < code < 400:
                data = resp.json()
                return data.get('status', '')
        finally:
            try_count -= 1
        time.sleep(1)

    raise ServiceNotAvailableException(status_code=code, detail='failed to get service status')


def _set_service_status(session: requests.sessions.Session, port: int, status: str, try_count: int = 3):
    code = 200
    while try_count > 0:
        try:
            headers = {
                SECRET_HEADER_KEY: modules.shared.cmd_opts.system_monitor_api_secret
            }
            resp = session.put(f'http://localhost:{port}/daemon/v1/status', headers=headers, json={
                'status': status,
            })
            code = resp.status_code
        finally:
            try_count -= 1
        time.sleep(1)
    raise ServiceNotAvailableException(status_code=code, detail='failed to get service status')


def _get_service_pending_task_info(session: requests.sessions.Session, port: int, try_count: int = 3) -> dict:
    code = 200
    while try_count > 0:
        try:
            headers = {
                SECRET_HEADER_KEY: modules.shared.cmd_opts.system_monitor_api_secret
            }
            resp = session.get(f'http://localhost:{port}/daemon/v1/pending-task-count', headers=headers)
            code = resp.status_code
            if 199 < code < 400:
                return resp.json()
        finally:
            try_count -= 1
        time.sleep(1)
    raise ServiceNotAvailableException(status_code=code, detail='failed to get service task count')


def _get_int_value_from_environment(key: str, default_value: int, min_value: int | None) -> int:
    value = os.getenv(key, default=default_value)
    result = int(value)
    if min_value is not None and result < min_value:
        result = min_value

    return result
