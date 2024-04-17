import html
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import traceback
import time
import functools
import json
from uuid import uuid4
import psutil
import asyncio
import pathlib
from datetime import datetime
from PIL import Image

import gradio.routes

import modules.system_monitor
from modules.system_monitor import (
    MonitorException,
    MonitorTierMismatchedException,
    copy_object_and_replace_images_with_path,
    monitor_call_context,
    generate_function_name)
from modules import shared, progress, errors, script_callbacks, devices, fifo_lock

from modules import sd_vae
from modules.timer import Timer
from modules.paths import Paths
from modules.model_info import DatabaseAllModelInfo, ModelInfo, AllModelInfo

gpu_worker_pool: ThreadPoolExecutor | None = None

logger = logging.getLogger(__name__)


def submit_to_gpu_worker(func: callable, timeout: int = 60) -> callable:
    def call_function_in_gpu_wroker(*args, **kwargs):
        if gpu_worker_pool is None:
            raise RuntimeError("GPU worker thread has not been initialized.")
        future_res = gpu_worker_pool.submit(
            func, *args, **kwargs)
        res = future_res.result(timeout=timeout)
        return res
    return call_function_in_gpu_wroker


def submit_to_gpu_worker_with_request(func: callable, timeout: int = 60) -> callable:
    def call_function_in_gpu_wroker(request: gradio.routes.Request, *args, **kwargs):
        if gpu_worker_pool is None:
            raise RuntimeError("GPU worker thread has not been initialized.")
        args = [request] + [arg for arg in args]
        future_res = gpu_worker_pool.submit(
            func, *args, **kwargs)
        res = future_res.result(timeout=timeout)
        return res
    return call_function_in_gpu_wroker




def get_private_tempdir(request: gradio.routes.Request) -> pathlib.Path:
    paths = Paths(request)
    return paths.private_tempdir()


class __FakeP:
    def __init__(self, req):
        self.request = req

    def get_request(self):
        return self.request


def extract_image_path_or_save_if_needed(request: gradio.routes.Request, image: Image.Image):
    if hasattr(image, 'already_saved_as') and image.already_saved_as:
        return image.already_saved_as
    else:
        image_dir = get_private_tempdir(request)
        image_id = str(uuid4())
        image_path = image_dir.joinpath(f'{image_id}.png')
        image.save(image_path)
        image.already_saved_as = str(image_path)

        params = modules.script_callbacks.ImageSaveParams(image, __FakeP(request), image_path, "")
        script_callbacks.image_saved_callback(params)
        return str(image_path)


def wrap_gpu_call(request: gradio.routes.Request, func, func_name, id_task, *args, **kwargs):
    assert shared.state, "shared.state is not initialized"
    monitor_log_id = None
    status = ''
    task_failed = True
    is_nsfw = False
    log_message = ''
    res = list()
    time_consumption = {}
    add_monitor_state = False
    if "add_monitor_state" in kwargs:
        add_monitor_state = kwargs.pop("add_monitor_state")
    extra_outputs = None
    if "extra_outputs" in kwargs:
        extra_outputs = kwargs.pop("extra_outputs")
    extra_outputs_array = extra_outputs
    if extra_outputs_array is None:
        extra_outputs_array = [None, '', '']
    exception_str = ''
    try:
        timer = Timer('gpu_call', func_name)

        # reset global state
        shared.state.begin(job=id_task, request=request)

        # start job process
        task_info = progress.start_task(id_task)

        # log all gpu calls with monitor, we should log it before task begin
        if func_name in ('txt2img', 'img2img'):
            raw_model_info = args[-2]
            if raw_model_info is None:
                logger.info("'model_info' is None, searching model by legacy logic")
                all_model_info = DatabaseAllModelInfo(request)
            else:
                all_model_info = AllModelInfo(raw_model_info)
                all_model_info.check_file_existence()

            model_title = args[-5]
        else:
            all_model_info = None
            model_title = ''

        task_info['model_title'] = model_title
        monitor_log_id = modules.system_monitor.on_task(request, func, task_info, *args, **kwargs)
        time_consumption['in_queue'] = time.time() - task_info.get('added_at', time.time())

        # reload model if necessary
        if all_model_info:
            progress.set_current_task_step('reload_model_weights')
            script_callbacks.state_updated_callback(shared.state)
            if not all_model_info.is_xyz_plot_enabled():
                _check_sd_model(
                    model_info=all_model_info.checkpoint_models[model_title],
                    embedding_model_info=all_model_info.embedding_models,
                )
        timer.record('load_models')

        # do gpu task
        progress.set_current_task_step('inference')
        res = func(request, *args, **kwargs)
        timer.record('inference')
        progress.set_current_task_step('done')

        # all done, clear status and log res
        time_consumption.update(timer.records)
        time_consumption['total'] = time.time() - task_info.get('added_at', time.time())
        logger.info(timer.summary())

        progress.record_results(id_task, res)
        status = 'finished'
        task_failed = False
    except MonitorException as e:
        logger.exception(f'task {id_task} failed: {e.__str__()}')
        exception_str = traceback.format_exc()
        res = extra_outputs_array + [repr(e)]
        status = 'failed'
        if add_monitor_state:
            match (e.status_code, e.code):
                case (402, "WEBUIFE-01010001"):
                    upgrade_info = {
                        "need_upgrade": True,
                        "reason": "INSUFFICIENT_CREDITS",
                    }
                case (402, "WEBUIFE-01010003"):
                    upgrade_info = {
                        "need_upgrade": True,
                        "reason": "INSUFFICIENT_DAILY_CREDITS",
                    }
                case (429, "WEBUIFE-01010004"):
                    upgrade_info = {
                        "need_upgrade": True,
                        "reason": "REACH_CONCURRENCY_LIMIT",
                    }
                case _:
                    logger.error(f"mismatched status_code({e.status_code}) and code({e.code}) in 'MonitorException'")
                    upgrade_info = {"need_upgrade": False}

            return res, json.dumps(upgrade_info)

        return res
    except MonitorTierMismatchedException as e:
        logger.exception(f'task {id_task} failed: {e.__str__()}')
        exception_str = traceback.format_exc()
        status = 'failed'
        res = extra_outputs_array + [_make_error_html(repr(e))]
        if add_monitor_state:
            return res, json.dumps({
                "need_upgrade": True,
                "message": f"This feature is available for {', '.join(e.allowed_tiers)} users, please upgrade to access it."})
        return res
    except Exception as e:
        logger.exception(f'task {id_task} failed: {e.__str__()}')
        if isinstance(e, MonitorException):
            task_failed = False
        status = 'failed'
        traceback.print_tb(e.__traceback__, file=sys.stderr)
        print(e, file=sys.stderr)
        error_message = f'{id_task}: {type(e).__name__}: {e}'
        if "MetadataIncompleteBuffer" in error_message:
            error_message = f"The model is probably corrupted, please contact us to delete it: {model_title}."
        res = extra_outputs_array + [_make_error_html(error_message)]
        exception_str = traceback.format_exc()
    finally:
        progress.finish_task(id_task, task_failed, exception_str or '')
        shared.state.end()
        if monitor_log_id:
            try:
                if task_failed:
                    log_message = exception_str
                else:
                    if len(res) > 0 and res[0] and len(res[0]) > 0 and isinstance(res[0][0], Image.Image):
                        # First element in res is gallery
                        is_nsfw = any(getattr(item, "is_nsfw", False) for item in res[0])
                        image_paths = [extract_image_path_or_save_if_needed(request, item) for item in res[0] if isinstance(item, Image.Image)]
                        log_message = json.dumps([image_paths] + list(res[1:]))
                    else:
                        log_message = json.dumps(res)
            except Exception as e:
                log_message = f'Fail to json serialize results: {str(e)}'
            try:
                modules.system_monitor.on_task_finished(request, monitor_log_id, status, log_message, time_consumption)
            except Exception as e:
                logging.warning(f'send task finished event to monitor failed: {str(e)}')

    if add_monitor_state:
        state = {"need_upgrade": False}
        if is_nsfw:
            state["is_nsfw"] = True

        return res, json.dumps(state)
    return res


queue_lock = fifo_lock.FIFOLock()

def wrap_queued_call(func):
    def f(*args, **kwargs):
        with queue_lock:
            res = func(*args, **kwargs)

def wrap_gradio_gpu_call(func, func_name: str = '', extra_outputs=None, add_monitor_state=False):
    @functools.wraps(func)
    def f(request: gradio.routes.Request, *args, **kwargs):
        assert shared.state, "shared.state is not initialized"
        predict_timeout = dict(request.headers).get('X-Predict-Timeout', shared.cmd_opts.predict_timeout)
        # if the first argument is a string that says "task(...)", it is treated as a job id
        if args and type(args[0]) == str and args[0].startswith("task(") and args[0].endswith(")"):
            id_task = args[0]
            if (id_task == progress.current_task) or (id_task in progress.finished_tasks):
                logger.error(f"got a duplicated predict task '{id_task}', ignore it")
                raise Exception(f"Duplicated predict request: '{id_task}'")

            progress.add_task_to_queue(
                id_task,
                {'job_type': func_name}
            )
        else:
            id_task = None

        try:
            res = submit_to_gpu_worker(
                functools.partial(
                    wrap_gpu_call,
                    request,
                    func,
                    func_name,
                    id_task,
                    add_monitor_state=add_monitor_state,
                    extra_outputs=extra_outputs,
                ),
                timeout=int(predict_timeout)
            )(*args, **kwargs)
        except TimeoutError:
            shared.state.interrupt()
            extra_outputs_array = extra_outputs
            if extra_outputs_array is None:
                extra_outputs_array = [None, '', '']
            if add_monitor_state:
                return extra_outputs_array + [f'Predict timeout: {predict_timeout}s'], json.dumps({"need_upgrade": False})
            return extra_outputs_array + [f'Predict timeout: {predict_timeout}s']

        return res

    return wrap_gradio_call(f, extra_outputs=extra_outputs, add_stats=True, add_monitor_state=add_monitor_state)


async def get_body(request: gradio.routes.Request):
    json_body = await request.json()
    return json_body


def _make_error_html(content: str) -> str:
    return f"<div class='error' style='user-select: text'>{html.escape(content)}</div>"


def wrap_gradio_call(func, extra_outputs=None, add_stats=False, add_monitor_state=False):
    @functools.wraps(func)
    def f(request: gradio.routes.Request, *args, extra_outputs_array=extra_outputs, **kwargs):
        assert shared.state, "shared.state is not initialized"
        task_id = None
        loop = asyncio.get_event_loop()
        request_body = loop.run_until_complete(get_body(request))
        for item in request_body["data"]:
            if isinstance(item, str) and item.startswith("task("):
                task_id = item.removeprefix("task(").removesuffix(")")
        current_datetime = datetime.now()
        print(f"{current_datetime.strftime('%Y-%m-%d %H:%M:%S')} task({task_id}) begins", file=sys.stderr)

        monitor_state = json.dumps({"need_upgrade": False})
        run_memmon = shared.opts.memmon_poll_rate > 0 and not shared.mem_mon.disabled and add_stats
        if run_memmon:
            shared.mem_mon.monitor()
        t = time.perf_counter()
        private_tempdir = get_private_tempdir(request)
        logger.info(f"Begin of task({task_id}) request")
        logger.info(f"url path: {request.url.path}")
        logger.info(f"headers: {json.dumps(dict(request.headers), ensure_ascii=False, sort_keys=True)}")
        logger.info(f"query params: {request.query_params}")
        logger.info(f"path params: {request.path_params}")
        logger.info(
            f"body: {json.dumps(copy_object_and_replace_images_with_path(request_body, str(private_tempdir)), ensure_ascii=False, sort_keys=True)}")
        logger.info(f"End of task({task_id}) request")
        task_start_system_memory = psutil.virtual_memory().used / 1024 / 1024 / 1024
        logger.info(f"task({task_id}) begin memory: {task_start_system_memory:.2f} GB")

        task_failed = False
        error_message = ''
        try:
            with monitor_call_context(
                    request,
                    generate_function_name(func),
                    generate_function_name(func),
                    task_id,
                    is_intermediate=False) as result_encoder:
                if add_monitor_state:
                    res, monitor_state = func(request, *args, **kwargs)
                    res = list(res)
                else:
                    res = list(func(request, *args, **kwargs))
                def save_image_if_not_saved_already(img_obj: Image.Image):
                    return extract_image_path_or_save_if_needed(request, img_obj)
                result_encoder(
                    copy_object_and_replace_images_with_path(
                        res,
                        str(private_tempdir),
                        save_image_callback=save_image_if_not_saved_already),
                    task_failed=progress.is_task_failed(f"task({task_id})" if task_id else ""))
            devices.torch_gc()
        except MonitorTierMismatchedException as e:
            task_failed = True
            error_message = f"This feature is available for {', '.join(e.allowed_tiers)} users, please upgrade to access it."

            shared.state.job = ""
            shared.state.job_count = 0
            if extra_outputs_array is None:
                extra_outputs_array = [None, '']
            res = extra_outputs_array + [_make_error_html(repr(e))]
            monitor_state = json.dumps({
                "need_upgrade": True,
                "message": error_message})
        except Exception as e:
            task_failed = True
            error_message = f'{type(e).__name__}: {e}'

            # When printing out our debug argument list, do not print out more than a MB of text
            max_debug_str_len = 131072  # (1024*1024)/8
            message = "Error completing request"
            print(message, file=sys.stderr)
            arg_str = f"Arguments: {args} {kwargs}"
            print(arg_str[:max_debug_str_len], file=sys.stderr)
            if len(arg_str) > max_debug_str_len:
                print(f"(Argument list truncated at {max_debug_str_len}/{len(arg_str)} characters)", file=sys.stderr)
            errors.report(f"{message}\n{arg_str}", exc_info=True)

            print(traceback.format_exc(), file=sys.stderr)

            shared.state.job = ""
            shared.state.job_count = 0

            if extra_outputs_array is None:
                extra_outputs_array = [None, '']

            res = extra_outputs_array + [_make_error_html(error_message)]
        finally:
            if task_failed and task_id:
                # NOTE: only report to progress after task_failed.
                progress.finish_task(task_id, task_failed, error_message)
            else:
                # the wrapped func will report to progress if not task_failed.
                pass

        shared.state.skipped = False
        shared.state.interrupted = False
        shared.state.stopping_generation = False
        shared.state.job_count = 0

        if isinstance(res[-1], str) and task_id:
            res[-1] = f"<p class='comments' style='user-select: text'>task({task_id})</p>" + res[-1]

        if not add_stats:
            task_end_system_memory = psutil.virtual_memory().used / 1024 / 1024 / 1024
            logger.info(f"task({task_id}) end memory: {task_end_system_memory:.2f} GB")
            logger.info(f"task({task_id}) task memory delta: {task_end_system_memory - task_start_system_memory:.2f} GB")
            current_datetime = datetime.now()
            print(f"{current_datetime.strftime('%Y-%m-%d %H:%M:%S')} task({task_id}) ends", file=sys.stderr)
            if add_monitor_state:
                return tuple(res + [monitor_state])
            return tuple(res)

        elapsed = time.perf_counter() - t
        elapsed_m = int(elapsed // 60)
        elapsed_s = elapsed % 60
        elapsed_text = f"{elapsed_s:.1f} sec."
        if elapsed_m > 0:
            elapsed_text = f"{elapsed_m} min. "+elapsed_text

        if run_memmon:
            mem_stats = {k: -(v//-(1024*1024)) for k, v in shared.mem_mon.stop().items()}
            active_peak = mem_stats['active_peak']
            reserved_peak = mem_stats['reserved_peak']
            sys_peak = mem_stats['system_peak']
            sys_total = mem_stats['total']
            sys_pct = sys_peak/max(sys_total, 1) * 100

            toltip_a = "Active: peak amount of video memory used during generation (excluding cached data)"
            toltip_r = "Reserved: total amout of video memory allocated by the Torch library "
            toltip_sys = "System: peak amout of video memory allocated by all running programs, out of total capacity"

            text_a = f"<abbr title='{toltip_a}'>A</abbr>: <span class='measurement'>{active_peak/1024:.2f} GB</span>"
            text_r = f"<abbr title='{toltip_r}'>R</abbr>: <span class='measurement'>{reserved_peak/1024:.2f} GB</span>"
            text_sys = f"<abbr title='{toltip_sys}'>Sys</abbr>: <span class='measurement'>{sys_peak/1024:.1f}/{sys_total/1024:g} GB</span> ({sys_pct:.1f}%)"

            vram_html = f"<p class='vram'>{text_a}, <wbr>{text_r}, <wbr>{text_sys}</p>"
        else:
            vram_html = ''

        # last item is always HTML
        res[-1] += f"<div class='performance'><p class='time'>Time taken: <wbr><span class='measurement'>{elapsed_text}</span></p>{vram_html}</div>"

        task_end_system_memory = psutil.virtual_memory().used / 1024 / 1024 / 1024
        logger.info(f"task({task_id}) end memory: {task_end_system_memory:.2f} GB")
        logger.info(f"task({task_id}) task memory delta: {task_end_system_memory - task_start_system_memory:.2f} GB")

        current_datetime = datetime.now()
        print(f"{current_datetime.strftime('%Y-%m-%d %H:%M:%S')} task({task_id}) ends", file=sys.stderr)
        if add_monitor_state:
            return tuple(res + [monitor_state])
        return tuple(res)

    return f


def _check_sd_model(model_info: ModelInfo, embedding_model_info: dict[str, ModelInfo]):
    shared.opts.sd_model_checkpoint = model_info.title

    if not shared.sd_model or shared.sd_model.sd_checkpoint_info.sha256 != model_info.sha256:
        import modules.sd_models
        # refresh model, unload it from memory to prevent OOM
        modules.sd_models.unload_model_weights()
        # checkpoint = modules.sd_models.get_closet_checkpoint_match(model_title)
        modules.sd_models.reload_model_weights(
            info=model_info, embedding_model_info=embedding_model_info
        )

    #if shared.sd_model:
    #    vae_file, vae_source = sd_vae.resolve_vae(shared.sd_model.sd_checkpoint_info.filename, vae_title)
    #    if sd_vae.loaded_vae_file != vae_file:
    #        sd_vae.load_vae(shared.sd_model, vae_file, vae_source)
