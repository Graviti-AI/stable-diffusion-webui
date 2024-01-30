from fastapi import FastAPI, Depends, Request, HTTPException

from modules.api.models import GetTaskCountResponse
import modules.progress
import modules.shared

# service is able to serve any requests
DAEMON_STATUS_UP = 'up'
# service is able to server pending requests only
DAEMON_STATUS_PENDING = 'pending'
# but not able to serve new request, and going to be died
DAEMON_STATUS_DOWN = 'down'

SECRET_HEADER_KEY = 'Api-Secret'


class DaemonApi:

    def __init__(self, app: FastAPI):
        self._app = app
        self._secret = modules.shared.cmd_opts.system_monitor_api_secret

        self._add_api_route("/daemon/v1/health/check", self.health_check, methods=["GET"])
        self._add_api_route("/daemon/v1/pending-task-count", self.get_task_count, methods=["GET"],
                            response_model=GetTaskCountResponse)

    @staticmethod
    def get_task_count():
        current_task, pending_tasks, _, finished_task_count, failed_task_count, consecutive_failed_task_count = modules.progress.get_task_queue_info()
        return GetTaskCountResponse(
            current_task=current_task if current_task else '',
            queued_tasks=pending_tasks,
            finished_task_count=finished_task_count,
            failed_task_count=failed_task_count,
            consecutive_failed_task_count=consecutive_failed_task_count,
        )

    def _add_api_route(self, path: str, endpoint, **kwargs):
        return self._app.add_api_route(path, endpoint, dependencies=[Depends(self._auth)], **kwargs)

    def _auth(self, request: Request):
        secret = request.headers.get(SECRET_HEADER_KEY, '')
        if secret == self._secret:
            return True

        raise HTTPException(status_code=401, detail="invalid API secret")

    @staticmethod
    def health_check() -> str:
        return 'OK'
