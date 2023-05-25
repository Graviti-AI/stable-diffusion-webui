import html
import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import traceback
import time
import functools

import gradio.routes

import modules.system_monitor
from modules.system_monitor import MonitorException
from modules import shared, progress
from modules import sd_vae
from modules.timer import Timer

queue_lock = threading.Lock()

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


def wrap_gpu_call(request: gradio.routes.Request, func, func_name, id_task, *args, **kwargs):
    monitor_log_id = None
    status = ''
    log_message = ''
    res = list()
    time_consumption = {}
    try:
        timer = Timer('gpu_call', func_name)

        # reset global state
        shared.state.begin()

        # start job process
        task_info = progress.start_task(id_task)

        # log all gpu calls with monitor, we should log it before task begin
        monitor_log_id = modules.system_monitor.on_task(request, func, task_info, *args, **kwargs)
        time_consumption['in_queue'] = time.time() - task_info.get('added_at', time.time())

        # reload model if necessary
        if func_name in ('txt2img', 'img2img'):
            progress.set_current_task_step('reload_model_weights')
            _check_sd_model(model_title=args[-2], vae_title=args[-1])
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
        log_message = 'done'
    except Exception as e:
        status = 'failed'
        log_message = e.__str__()
        raise e
    finally:
        progress.finish_task(id_task)
        shared.state.end()
        if monitor_log_id:
            try:
                modules.system_monitor.on_task_finished(request, monitor_log_id, status, log_message, time_consumption)
            except Exception as e:
                logging.warning(f'send task finished event to monitor failed: {e.__str__()}')
    return res


def wrap_gradio_gpu_call(func, func_name: str = '', extra_outputs=None, add_monitor_state=False):
    def f(request: gradio.routes.Request, *args, **kwargs):

        # if the first argument is a string that says "task(...)", it is treated as a job id
        if len(args) > 0 and type(args[0]) == str and args[0][0:5] == "task(" and args[0][-1] == ")":
            id_task = args[0]
            progress.add_task_to_queue(
                id_task,
                {'job_type': func_name}
            )
        else:
            id_task = None

        try:
            res = submit_to_gpu_worker(
                functools.partial(wrap_gpu_call, request, func, func_name, id_task),
                timeout=shared.cmd_opts.predict_timeout
            )(*args, **kwargs)
        except MonitorException as e:
            extra_outputs_array = extra_outputs
            if extra_outputs_array is None:
                extra_outputs_array = [None, '', '']
            if add_monitor_state:
                return extra_outputs_array + [str(e)], e.status_code == 402
            return extra_outputs_array + [str(e)]

        if add_monitor_state:
            return res, False
        return res

    return wrap_gradio_call(f, extra_outputs=extra_outputs, add_stats=True, add_monitor_state=add_monitor_state)


def wrap_gradio_call(func, extra_outputs=None, add_stats=False, add_monitor_state=False):
    def f(request: gradio.routes.Request, *args, extra_outputs_array=extra_outputs, **kwargs):
        monitor_state = False
        run_memmon = shared.opts.memmon_poll_rate > 0 and not shared.mem_mon.disabled and add_stats
        if run_memmon:
            shared.mem_mon.monitor()
        t = time.perf_counter()

        try:
            if add_monitor_state:
                res, monitor_state = func(request, *args, **kwargs)
                res = list(res)
            else:
                res = list(func(request, *args, **kwargs))
        except Exception as e:
            # When printing out our debug argument list, do not print out more than a MB of text
            max_debug_str_len = 131072  # (1024*1024)/8

            print("Error completing request", file=sys.stderr)
            argStr = f"Arguments: {str(args)} {str(kwargs)}"
            print(argStr[:max_debug_str_len], file=sys.stderr)
            if len(argStr) > max_debug_str_len:
                print(f"(Argument list truncated at {max_debug_str_len}/{len(argStr)} characters)", file=sys.stderr)

            print(traceback.format_exc(), file=sys.stderr)

            shared.state.job = ""
            shared.state.job_count = 0

            if extra_outputs_array is None:
                extra_outputs_array = [None, '']

            res = extra_outputs_array + [f"<div class='error'>{html.escape(type(e).__name__+': '+str(e))}</div>"]

        shared.state.skipped = False
        shared.state.interrupted = False
        shared.state.job_count = 0

        if not add_stats:
            if add_monitor_state:
                return tuple(res + [monitor_state])
            return tuple(res)

        elapsed = time.perf_counter() - t
        elapsed_m = int(elapsed // 60)
        elapsed_s = elapsed % 60
        elapsed_text = f"{elapsed_s:.2f}s"
        if elapsed_m > 0:
            elapsed_text = f"{elapsed_m}m "+elapsed_text

        if run_memmon:
            mem_stats = {k: -(v//-(1024*1024)) for k, v in shared.mem_mon.stop().items()}
            active_peak = mem_stats['active_peak']
            reserved_peak = mem_stats['reserved_peak']
            sys_peak = mem_stats['system_peak']
            sys_total = mem_stats['total']
            sys_pct = round(sys_peak/max(sys_total, 1) * 100, 2)

            vram_html = f"<p class='vram'>Torch active/reserved: {active_peak}/{reserved_peak} MiB, <wbr>Sys VRAM: {sys_peak}/{sys_total} MiB ({sys_pct}%)</p>"
        else:
            vram_html = ''

        # last item is always HTML
        res[-1] += f"<div class='performance'><p class='time'>Time taken: <wbr>{elapsed_text}</p>{vram_html}</div>"

        if add_monitor_state:
            return tuple(res + [monitor_state])
        return tuple(res)

    return f


def _check_sd_model(model_title, vae_title):
    if not shared.sd_model or shared.sd_model.sd_checkpoint_info.title != model_title:
        import modules.sd_models
        # refresh model, unload it from memory to prevent OOM
        modules.sd_models.unload_model_weights()
        checkpoint = modules.sd_models.get_closet_checkpoint_match(model_title)
        modules.sd_models.reload_model_weights(info=checkpoint)

    if shared.sd_model:
        vae_file, vae_source = sd_vae.resolve_vae(shared.sd_model.sd_checkpoint_info.filename, vae_title)
        if sd_vae.loaded_vae_file != vae_file:
            sd_vae.load_vae(shared.sd_model, vae_file, vae_source)
