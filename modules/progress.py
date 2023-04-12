import base64
import io
import time

import gradio as gr
from pydantic import BaseModel, Field

from modules.shared import opts

import modules.shared as shared


current_task = None
current_task_step = ''
pending_tasks = {}
finished_tasks = []


def get_task_queue_info():
    return current_task, pending_tasks, finished_tasks


def start_task(id_task):
    global current_task
    global current_task_step

    current_task = id_task
    current_task_step = ''

    pending_tasks.pop(id_task, None)


def set_current_task_step(step):
    global current_task_step
    current_task_step = step


def finish_task(id_task):
    global current_task
    global current_task_step

    if current_task == id_task:
        current_task = None
        current_task_step = ''

    finished_tasks.append(id_task)
    if len(finished_tasks) > 16:
        finished_tasks.pop(0)


def add_task_to_queue(id_job, job_info=None):
    task_info = {
        'added_at': time.time(),
        'last_accessed_at': time.time(),
    }
    if job_info:
        task_info.update(job_info)

    pending_tasks[id_job] = task_info


class ProgressRequest(BaseModel):
    id_task: str = Field(default=None, title="Task ID", description="id of the task to get progress for")
    id_live_preview: int = Field(default=-1, title="Live preview image ID", description="id of last received last preview image")


class ProgressResponse(BaseModel):
    active: bool = Field(title="Whether the task is being worked on right now")
    queued: bool = Field(title="Whether the task is in queue")
    completed: bool = Field(title="Whether the task has already finished")
    progress: float = Field(default=None, title="Progress", description="The progress with a range of 0 to 1")
    eta: float = Field(default=None, title="ETA in secs")
    live_preview: str = Field(default=None, title="Live preview image", description="Current live preview; a data: uri")
    id_live_preview: int = Field(default=None, title="Live preview image ID", description="Send this together with next request to prevent receiving same image")
    textinfo: str = Field(default=None, title="Info text", description="Info text used by WebUI.")


def setup_progress_api(app):
    return app.add_api_route("/internal/progress", progressapi, methods=["POST"], response_model=ProgressResponse)


def progressapi(req: ProgressRequest):
    active = req.id_task == current_task
    queued = req.id_task in pending_tasks
    completed = req.id_task in finished_tasks

    # log last access time for this task.
    # if there is no active task, and a queued task is not accessed for a long time, we should
    # consider to remove it from queue.
    if req.id_task in pending_tasks:
        pending_tasks[req.id_task]['last_accessed_at'] = time.time()

    if not active:
        return ProgressResponse(active=active, queued=queued, completed=completed, id_live_preview=-1, textinfo="In queue..." if queued else "Waiting...")

    if current_task_step == 'reload_model_weights':
        return ProgressResponse(active=active, queued=queued, completed=completed, id_live_preview=-1, textinfo='Reloading model weights...')

    progress = 0

    job_count, job_no = shared.state.job_count, shared.state.job_no
    sampling_steps, sampling_step = shared.state.sampling_steps, shared.state.sampling_step

    if job_count > 0:
        progress += job_no / job_count
    if sampling_steps > 0 and job_count > 0:
        progress += 1 / job_count * sampling_step / sampling_steps

    progress = min(progress, 1)

    elapsed_since_start = time.time() - shared.state.time_start
    predicted_duration = elapsed_since_start / progress if progress > 0 else None
    eta = predicted_duration - elapsed_since_start if predicted_duration is not None else None

    id_live_preview = req.id_live_preview
    shared.state.set_current_image()
    if opts.live_previews_enable and shared.state.id_live_preview != req.id_live_preview:
        image = shared.state.current_image
        if image is not None:
            buffered = io.BytesIO()
            image.save(buffered, format="png")
            live_preview = 'data:image/png;base64,' + base64.b64encode(buffered.getvalue()).decode("ascii")
            id_live_preview = shared.state.id_live_preview
        else:
            live_preview = None
    else:
        live_preview = None

    return ProgressResponse(active=active, queued=queued, completed=completed, progress=progress, eta=eta, live_preview=live_preview, id_live_preview=id_live_preview, textinfo=shared.state.textinfo)

