from fastapi import FastAPI, Depends, Request, HTTPException

from modules.api.models import GetTaskCountResponse, GetDaemonStatusResponse, UpdateStatusRequest
from modules.progress import current_task, pending_tasks
import modules.shared

DAEMON_STATUS_UP = 'up'
DAEMON_STATUS_PENDING = 'pending'

SECRET_HEADER_KEY = 'Api-Secret'


class DaemonApi:

    def __init__(self, app: FastAPI):
        self._app = app
        self._secret = modules.shared.cmd_opts.system_monitor_api_secret
        self._status = DAEMON_STATUS_UP

        self._add_api_route("/daemon/v1/status", self.get_status, methods=["GET"], response_model=GetDaemonStatusResponse)
        self._add_api_route("/daemon/v1/status", self.set_status, methods=["PUT"])
        self._add_api_route("/daemon/v1/pending-task-count", self.get_task_count, methods=["GET"], response_model=GetTaskCountResponse)

    def get_status(self):
        return GetDaemonStatusResponse(status=self._status)

    def set_status(self, request: UpdateStatusRequest):
        status = request.status
        if status != DAEMON_STATUS_PENDING and status != DAEMON_STATUS_UP:
            raise HTTPException(status_code=400, detail="invalid status")

        self._status = request.status
        return GetDaemonStatusResponse(status=self._status)

    def get_task_count(self):
        return GetTaskCountResponse(current_task=current_task is not None, pending_task_count=len(pending_tasks))

    def _add_api_route(self, path: str, endpoint, **kwargs):
        return self._app.add_api_route(path, endpoint, dependencies=[Depends(self._auth)], **kwargs)

    def _auth(self, request: Request):
        secret = request.headers.get(SECRET_HEADER_KEY, '')
        if secret == self._secret:
            return True

        raise HTTPException(status_code=401, detail="invalid API secret")
