import base64
import io
import logging
import time
import gradio as gr

from queue import Queue
from pydantic import BaseModel, Field

from modules.shared import opts

import modules.shared as shared

current_task = None
current_task_step = ''
pending_tasks = {}
finished_tasks = []
failed_tasks = []
recorded_results = []
recorded_results_limit = 2
finished_task_count = 0
failed_task_count = 0
consecutive_failed_task_count = 0

# this queue is just used for telling user where he/she is in the queue
# do not use it for any other purposes
_queued_tasks = Queue()

logger = logging.getLogger(__name__)


def get_task_queue_info():
    return current_task, pending_tasks, finished_tasks, finished_task_count, failed_task_count, consecutive_failed_task_count


def start_task(id_task):
    global current_task
    global current_task_step
    logger.info(f'start_task, current_task: {current_task}, new_task: {id_task}')

    current_task = id_task
    current_task_step = ''

    task_info = _pop_task_from_queue(id_task)
    task_info['started_at'] = time.time()

    return task_info


def set_current_task_step(step):
    global current_task_step
    current_task_step = step
    logger.info(f'set_current_task_step, current_task: {current_task}, current_task_step: {current_task_step}')


def finish_task(id_task, task_failed=False):
    global current_task
    global current_task_step
    global finished_task_count
    global failed_task_count
    global consecutive_failed_task_count
    global finished_tasks
    global failed_tasks
    logger.info(
        f'finish_task, id_task: {id_task}, current_task: {current_task}, current_task_step: {current_task_step}')

    # if a task was finished before start, we need pop it out from pending queue
    _pop_task_from_queue(id_task)

    if current_task == id_task:
        current_task = None
        current_task_step = ''

    if id_task not in finished_tasks:
        finished_tasks.append(id_task)
        if task_failed:
            failed_task_count += 1
            consecutive_failed_task_count += 1
            if id_task not in failed_tasks:
                failed_tasks.append(id_task)
        else:
            finished_task_count += 1
            consecutive_failed_task_count = 0

    if len(finished_tasks) > 600:
        finished_tasks.pop(0)

    if len(failed_tasks) > 600:
        failed_tasks.pop(0)


def is_task_failed(id_task: str) -> bool:
    return id_task in failed_tasks


def record_results(id_task, res):
    recorded_results.append((id_task, res))
    if len(recorded_results) > recorded_results_limit:
        recorded_results.pop(0)


def add_task_to_queue(id_job, job_info=None):
    logger.info(f'add_task_to_queue, id_task: {id_job}')

    task_was_added = False
    if id_job not in pending_tasks:
        task_info = {
            'added_at': time.time(),
            'last_accessed_at': time.time(),
        }
    else:
        task_was_added = True
        task_info = pending_tasks[id_job]

    if job_info:
        task_info.update(job_info)

    pending_tasks[id_job] = task_info
    if id_job and not task_was_added:
        try:
            _queued_tasks.put(id_job, block=True, timeout=1)
        except Exception as e:
            logger.error(f'put task to task_queue failed, task_id: {id_job}, error: {e.__str__()}')


def _pop_task_from_queue(id_task):
    task_info = pending_tasks.pop(id_task, {})

    # some times, start_task may get a id_task with None or not in _queued_tasks
    # in this case, do not pop task from _queued_tasks
    id_task_in_queue = False
    for task_id_in_queue in _queued_tasks.queue:
        if task_id_in_queue == id_task:
            id_task_in_queue = True
            break

    if id_task_in_queue:
        try:
            queued_task = _queued_tasks.get(block=True, timeout=1)
            if queued_task != id_task:
                logging.error(f'un-excepted task in start, want {id_task}, got {queued_task}')
        except Exception as e:
            logger.error(f'pop current task from queue failed, id_task: {id_task}, error: {e.__init__()}')
    return task_info


class ProgressRequest(BaseModel):
    id_task: str = Field(default=None, title="Task ID", description="id of the task to get progress for")
    id_live_preview: int = Field(default=-1, title="Live preview image ID", description="id of last received last preview image")
    live_preview: bool = Field(default=True, title="Include live preview", description="boolean flag indicating whether to include the live preview image")


class ProgressResponse(BaseModel):
    active: bool = Field(title="Whether the task is being worked on right now")
    queued: bool = Field(title="Whether the task is in queue")
    completed: bool = Field(title="Whether the task has already finished")
    progress: float = Field(default=None, title="Progress", description="The progress with a range of 0 to 1")
    eta: float = Field(default=None, title="ETA in secs")
    live_preview: str = Field(default=None, title="Live preview image", description="Current live preview; a data: uri")
    id_live_preview: int = Field(default=None, title="Live preview image ID",
                                 description="Send this together with next request to prevent receiving same image")
    textinfo: str = Field(default=None, title="Info text", description="Info text used by WebUI.")


def setup_progress_api(app):
    return app.add_api_route("/internal/progress", progressapi, methods=["POST"], response_model=ProgressResponse)


def progressapi(req: ProgressRequest):
    active = req.id_task == current_task
    queued = req.id_task in pending_tasks
    completed = req.id_task in finished_tasks
    logger.debug(
        f'progressapi, current_task: {current_task}, id_task: {req.id_task}, queued: {queued}, completed: {completed}')
    # log last access time for this task.
    # if there is no active task, and a queued task is not accessed for a long time, we should
    # consider to remove it from queue.
    if req.id_task in pending_tasks:
        pending_tasks[req.id_task]['last_accessed_at'] = time.time()

    if not active or shared.state.time_start is None:
        count_ahead = 0
        if queued:
            for task in _queued_tasks.queue:
                if task == req.id_task:
                    break
                count_ahead += 1
        # 8s is a estimate of inference time consumption
        eta = count_ahead * 8
        return ProgressResponse(active=active, queued=queued, completed=completed, id_live_preview=-1,
                                textinfo=f"In queue({count_ahead} ahead)... ETA: {eta}s" if queued else "Waiting...")

    if current_task_step == 'reload_model_weights':
        return ProgressResponse(active=active, queued=queued, completed=completed, id_live_preview=-1,
                                textinfo='Loading model weights... ETA: 8s')

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

    live_preview = None
    id_live_preview = req.id_live_preview

    if current_task_step == 'inference':
        shared.state.set_current_image()

    if opts.live_previews_enable and req.live_preview:
        shared.state.set_current_image()
        if shared.state.id_live_preview != req.id_live_preview:
            image = shared.state.current_image
            if image is not None:
                buffered = io.BytesIO()

                if opts.live_previews_image_format == "png":
                    # using optimize for large images takes an enormous amount of time
                    if max(*image.size) <= 256:
                        save_kwargs = {"optimize": True}
                    else:
                        save_kwargs = {"optimize": False, "compress_level": 1}

                else:
                    save_kwargs = {}

                image.save(buffered, format=opts.live_previews_image_format, **save_kwargs)
                base64_image = base64.b64encode(buffered.getvalue()).decode('ascii')
                live_preview = f"data:image/{opts.live_previews_image_format};base64,{base64_image}"
                id_live_preview = shared.state.id_live_preview

    # stop progress requests after prediction was interrupted
    if shared.state.interrupted:
        completed = True

    return ProgressResponse(active=active, queued=queued, completed=completed, progress=progress, eta=eta,
                            live_preview=live_preview, id_live_preview=id_live_preview, textinfo=shared.state.textinfo)


def restore_progress(id_task):
    start = time.time()
    while (id_task == current_task or id_task in pending_tasks) and (time.time() - start < 10):
        time.sleep(0.1)

    res = next(iter([x[1] for x in recorded_results if id_task == x[0]]), None)
    if res is not None:
        return res

    return gr.update(), gr.update(), gr.update(), f"Couldn't restore progress for {id_task}: results either have been discarded or never were obtained"
