import os
import tempfile
import time
import uuid
import logging
import json
import requests
import functools
import inspect
import base64
import io
import imghdr
from PIL import Image
import numpy as np

from typing import Optional, Protocol, Union, Any, Callable
from contextlib import contextmanager

import gradio as gr
import torch

import modules.user
import modules.shared

logger = logging.getLogger(__name__)


class MonitorException(Exception):
    def __init__(self, status_code, msg):
        self.status_code = status_code
        self._msg = msg

    def __repr__(self) -> str:
        return self._msg


class MonitorTierMismatchedException(Exception):
    def __init__(self, msg, current_tier, allowed_tiers):
        self._msg = msg
        self.current_tier = current_tier
        self.allowed_tiers = allowed_tiers

    def __repr__(self) -> str:
        return self._msg


def remove_schema(base64_str: str) -> str:
    if "base64," in base64_str:
        base64_str = base64_str.split("base64,")[1]
    return base64_str


def is_base64_image(img_str: str, supress_exception: bool = True) -> tuple[bool, str, int | None, int | None, str | None]:
    """
    Check if a string is a base64 encoded image and return its dimensions and MIME type.

    :param str s: a string to check
    :return: tuple (is_image, removed_schema_str, width, height, mime) or (False, img_str, None, None, None) if the string is not a valid image
    """
    try:
        mime = None
        # Check if the string has the embedded schema and remove it
        removed_schema_str = img_str
        if ";base64," in img_str:
            mime, removed_schema_str = img_str.split(";base64,")
            mime = mime.split(":")[1] if "data:" in mime else None

        # Decode the base64 string
        decoded = base64.b64decode(removed_schema_str)

        # Open the image and get its size
        image = Image.open(io.BytesIO(decoded))
        width, height = image.size

        # If mime type is not available in the string, guess it using imghdr
        if mime is None:
            mime = imghdr.what(None, h=decoded)
            mime = "image/" + mime if mime else None

        return True, removed_schema_str, width, height, mime
    except Exception as e:
        if not supress_exception:
            logger.exception(f"Failed to check if the string ({img_str[:100]}) is a valid image: {e}")
        return False, img_str, None, None, None


def save_base64_image_to_file(encoded_image: str, output_path: str) -> str:
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    decoded_image = base64.b64decode(remove_schema(encoded_image))
    with open(output_path, 'wb') as f:
        f.write(decoded_image)
    return output_path


def copy_object_and_replace_images_with_path(
        obj: Any, output_dir: str, save_image_callback: Optional[Callable] = None):
    if isinstance(obj, dict):
        copied_obj = {}
        for key, value in obj.items():
            copied_obj[key] = copy_object_and_replace_images_with_path(value, output_dir, save_image_callback)
        return copied_obj
    elif isinstance(obj, list) or isinstance(obj, tuple):
        return [copy_object_and_replace_images_with_path(item, output_dir, save_image_callback) for item in obj]
    elif isinstance(obj, str):
        if len(obj) < 200:
            return obj
        is_image, removed_schema_str, _, _, mime = is_base64_image(obj)
        if is_image:
            ext = mime.split('/')[1] if mime else 'jpg'
            return save_base64_image_to_file(
                removed_schema_str, os.path.join(output_dir, f"{str(uuid.uuid4())}.{ext}"))
    elif isinstance(obj, (Image.Image, np.ndarray)):
        if isinstance(obj, np.ndarray):
            obj = Image.fromarray(obj)
        if save_image_callback:
            return save_image_callback(obj)
        ext = 'jpg'
        output_path = os.path.join(output_dir, f"{str(uuid.uuid4())}.{ext}")
        obj.save(output_path)
        return output_path
    return obj


def _make_gpu_consumption(func_name, named_args, *args, **kwargs) -> dict:
    """
    Make the object which will be used to calculate the consume by FE.

    Args:
        func_name: the gpu_call func name
        named_args: func args that has a name
        *args: func args that has no name
        **kwargs: kwargs

    Returns: dict
    """
    result = {
        'type': '',
        'batch_count': 0,
        'batch_size': 0,
        'steps': 0,
        'scale': 1,
        'enable_hr': False,
        'hr_scale': 1,
        'hr_second_pass_steps': 0,
        'image_sizes': [],
    }

    if func_name in ('modules.txt2img.txt2img', 'modules.img2img.img2img'):
        result['type'] = func_name.split('.')[-1]
        result['image_sizes'].append({
            'width': named_args.get('width', 512),
            'height': named_args.get('height', 512),
        })
        result['batch_count'] = named_args.get('n_iter', 1)
        result['batch_size'] = named_args.get('batch_size', 1)
        result['steps'] = named_args.get('steps', 20)

        # enable_hr is a str, not bool
        enable_hr = named_args.get('enable_hr', False)
        if enable_hr:
            result['enable_hr'] = True
            result['scale'] = named_args.get('hr_scale', 2)
            result['hr_scale'] = named_args.get('hr_scale', 2)
            result['hr_second_pass_steps'] = named_args.get('hr_second_pass_steps', 30)
            if result['hr_second_pass_steps'] == 0:
                result['hr_second_pass_steps'] = result['steps']

    return result


def _serialize_object(obj):
    """
    +-------------------+---------------+
    | Python            | JSON          |
    +===================+===============+
    | dict              | object        |
    +-------------------+---------------+
    | list, tuple       | array         |
    +-------------------+---------------+
    | str               | string        |
    +-------------------+---------------+
    | int, float        | number        |
    +-------------------+---------------+
    | True              | true          |
    +-------------------+---------------+
    | False             | false         |
    +-------------------+---------------+
    | None              | null          |
    +-------------------+---------------+
    | Image             | object        |
    +-------------------+---------------+
    | Others            | string        |
    +-------------------+---------------+
    """
    from PIL import Image
    import types
    obj_type = type(obj)
    if obj_type in (str, int, float, bool, types.NoneType):
        return obj
    elif obj_type in (list, tuple):
        result = []
        for element in obj:
            result.append(_serialize_object(element))
        return result
    elif obj_type is dict:
        result = {}
        for key, value in obj.items():
            result[key] = _serialize_object(value)
        return result
    elif obj_type is Image.Image:
        return {
            'size': obj.size
        }
    elif obj_type is tempfile._TemporaryFileWrapper:
        return {
            'name': obj.name,
            'orig_name': obj.orig_name
        }
    else:
        return str(obj)


def _extract_task_id(*args):
    if len(args) > 0 and type(args[0]) == str and args[0][0:5] == "task(" and args[0][-1] == ")":
        return args[0][5:-1]
    else:
        return uuid.uuid4().hex


def _get_system_monitor_config(request: gr.Request):
    headers = dict(request.headers)

    # take per-task config as priority instead of global config
    monitor_addr = headers.get('x-diffus-system-monitor-url', '') or headers.get('X-Diffus-System-Monitor-Url', '')
    system_monitor_api_secret = headers.get('x-diffus-system-monitor-api-secret', '') or headers.get('X-Diffus-System-Monitor-Api-Secret', '')
    if not monitor_addr or not system_monitor_api_secret:
        monitor_addr = modules.shared.cmd_opts.system_monitor_addr
        system_monitor_api_secret = modules.shared.cmd_opts.system_monitor_api_secret
    return monitor_addr, system_monitor_api_secret


def on_task(request: gr.Request, func, task_info, *args, **kwargs):
    monitor_addr, system_monitor_api_secret = _get_system_monitor_config(request)
    if not monitor_addr or not system_monitor_api_secret:
        logger.error('system_monitor_addr or system_monitor_api_secret is not present')
        return None

    monitor_log_id = _extract_task_id(*args)
    # inspect func args
    signature = inspect.signature(func)
    positional_args = []
    for i, param in enumerate(signature.parameters.values()):
        if param.kind not in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
            break
        positional_args.append(param)

    positional_args = positional_args[1:]
    func_args = {}
    named_args_count = min(len(positional_args), len(args))

    for i in range(named_args_count):
        arg_name = positional_args[i].name
        arg_value = args[i]
        # values need to be converted to json serializable
        func_args[arg_name] = _serialize_object(arg_value)

    # get func name
    module = inspect.getmodule(func)
    func_args.update(**kwargs)
    func_name = func.__name__
    fund_module_name = module.__name__ if module else ""

    # send call info to monitor server
    api_name = f'{fund_module_name}.{func_name}'
    request_data = {
        'api': api_name,
        'task_id': monitor_log_id,
        'user': modules.user.User.current_user(request).uid,
        'args': func_args,
        'extra_args': _serialize_object(args[named_args_count + 1:]) if named_args_count + 1 < len(args) else [],
        'gpu_consumption': _make_gpu_consumption(api_name, func_args, *args, **kwargs),
        'node': os.getenv('HOST_IP', default=''),
        'added_at': task_info.get('added_at', time.time()),
        'model_title': task_info.get('model_title', ''),
    }
    resp = requests.post(monitor_addr,
                         headers={
                             'Api-Secret': system_monitor_api_secret,
                         },
                         json=request_data)
    logger.info(json.dumps(request_data, ensure_ascii=False, sort_keys=True))

    # check response, raise exception if status code is not 2xx
    if 199 < resp.status_code < 300:
        return monitor_log_id

    # log the response if request failed
    logger.error(f'create monitor log failed, status: {resp.status_code}, message: {resp.text[:1000]}')
    raise MonitorException(resp.status_code, resp.text)


def on_task_finished(request: gr.Request, monitor_log_id: str, status: str, message: str, time_consumption: dict):
    monitor_addr, system_monitor_api_secret = _get_system_monitor_config(request)
    if not monitor_addr or not system_monitor_api_secret:
        logger.error('system_monitor_addr or system_monitor_api_secret is not present')
        return

    request_url = f'{monitor_addr}/{monitor_log_id}'
    resp = requests.post(request_url,
                         headers={
                             'Api-Secret': system_monitor_api_secret,
                         },
                         json={
                             'status': status,
                             'result': message,
                             'time_consumption': time_consumption
                         })

    # log the response if request failed
    if resp.status_code < 200 or resp.status_code > 299:
        logger.error((f'update monitor log failed, status: monitor_log_id: {monitor_log_id}, {resp.status_code}, '
                      f'message: {resp.text[:1000]}'))


def before_task_started(
        request: gr.Request,
        api_name: str,
        function_name: str,
        job_id: Optional[str] = None,
        decoded_params: Optional[dict] = None,
        is_intermediate: bool = False,
        refund_if_task_failed: bool = True,
        only_available_for: Optional[list[str]] = None) -> Optional[str]:
    if job_id is None:
        job_id = str(uuid.uuid4())
    monitor_addr, system_monitor_api_secret = _get_system_monitor_config(request)
    if not monitor_addr or not system_monitor_api_secret:
        logger.error(f'{job_id}: system_monitor_addr or system_monitor_api_secret is not present')
        return None

    header_dict = dict(request.headers)
    session_hash = header_dict.get('x-session-hash', None)
    if not session_hash:
        logger.error(f'{job_id}: x-session-hash does not presented in headers')
        return None
    task_id = header_dict.get('x-task-id', None)
    if not task_id:
        logger.error(f'{job_id}: x-task-id does not presented in headers')
        return None
    if not is_intermediate and task_id != job_id:
        logger.error(f'x-task-id ({task_id}) and job_id ({job_id}) are not equal')
    deduct_flag = header_dict.get('x-deduct-credits', None)
    deduct_flag = not (deduct_flag == 'false')
    if only_available_for:
        user_tier = header_dict.get('user-tire', None) or header_dict.get('user-tier', None)
        if not user_tier or user_tier.lower() not in [item.lower() for item in only_available_for]:
            raise MonitorTierMismatchedException(
                f'This feature is available for {only_available_for} only. The current user tier is {user_tier}.',
                user_tier,
                only_available_for)

    request_data = {
        'api': api_name,
        'initiator': function_name,
        'user': modules.user.User.current_user(request).uid,
        'started_at': time.time(),
        'session_hash': session_hash,
        'skip_charge': not deduct_flag,
        'refund_if_task_failed': refund_if_task_failed,
        'node': os.getenv('HOST_IP', default=''),
    }
    if is_intermediate:
        request_data['step_id'] = job_id
        request_data['task_id'] = task_id
    else:
        request_data['task_id'] = job_id
    if decoded_params:
        request_data['decoded_params'] = decoded_params
    resp = requests.post(monitor_addr,
                         headers={
                             'Api-Secret': system_monitor_api_secret,
                         },
                         json=request_data)
    logger.info(json.dumps(request_data, ensure_ascii=False, sort_keys=True))

    # check response, raise exception if status code is not 2xx
    if 199 < resp.status_code < 300:
        return job_id

    # log the response if request failed
    logger.error(f'create monitor log failed, status: {resp.status_code}, message: {resp.text[:1000]}')
    raise MonitorException(resp.status_code, resp.text)


def after_task_finished(
        request: gr.Request,
        job_id: Optional[str],
        status: str,
        message: Optional[str] = None,
        is_intermediate: bool = False,
        refund_if_failed: bool = False):
    if job_id is None:
        logger.error('task_id is not present in after_task_finished, there might be error occured in before_task_started.')
        return
    monitor_addr, system_monitor_api_secret = _get_system_monitor_config(request)
    if not monitor_addr or not system_monitor_api_secret:
        logger.error(f'{job_id}: system_monitor_addr or system_monitor_api_secret is not present')
        return

    header_dict = dict(request.headers)
    session_hash = header_dict.get('x-session-hash', None)
    if not session_hash:
        logger.error(f'{job_id}: x-session-hash does not presented in headers')
        return None
    task_id = header_dict.get('x-task-id', None)
    if not task_id:
        logger.error(f'{job_id}: x-task-id does not presented in headers')
        return None

    request_url = f'{monitor_addr}/{job_id}'
    request_body = {
        'status': status,
        'result': message if message else "{}",
        'finished_at': time.time(),
        'session_hash': session_hash,
        'refund_if_failed': refund_if_failed,
    }
    if is_intermediate:
        request_body['step_id'] = job_id
        request_body['task_id'] = task_id
    else:
        request_body['task_id'] = job_id
    resp = requests.post(request_url,
                         headers={
                             'Api-Secret': system_monitor_api_secret,
                         },
                         json=request_body)

    # log the response if request failed
    if resp.status_code < 200 or resp.status_code > 299:
        logger.error((f'update monitor log failed, status: monitor_log_id: {job_id}, {resp.status_code}, '
                      f'message: {resp.text[:1000]}'))


def generate_function_name(func) -> str:
    module = inspect.getmodule(func)
    func_name = func.__name__
    func_name = f'{module.__name__}.{func_name}' if module else func_name
    return func_name


class RequestGetter(Protocol):
    def get_request(self) -> gr.Request:
        ...


def monitor_this_call(
        api_name: Optional[str] = None,
        initiator: Optional[str] = None,
        is_intermediate: bool = False,
        param_list: Optional[list] = None,
        extract_task_id: bool = False,
        refund_if_task_failed: bool = True,
        refund_if_failed: bool = False,
        only_available_for: Optional[list[str]] = None
):
    def function_wrapper(func):
        @functools.wraps(func)
        def wrapper(request: Union[gr.Request, RequestGetter], *args, **kwargs):
            task_id = None
            if extract_task_id:
                for item in args:
                    if isinstance(item, str) and item.startswith('task(') and item.endswith(')'):
                        task_id = item[5:-1]
                        break
            if not task_id:
                task_id = str(uuid.uuid4())
            if isinstance(request, gr.Request):
                request_obj = request
            else:
                request_obj = request.get_request()
            status = 'unknown'
            message = ''
            # get func name
            func_name = generate_function_name(func)
            nonlocal api_name, initiator
            if not api_name:
                api_name = func_name
            if not initiator:
                initiator = func_name
            # get all parameters
            signature = inspect.signature(func)
            decoded_params = dict()
            if param_list:
                signature_params = signature.parameters
                signature_params_keys = list(signature_params.keys())
                for arg in param_list:
                    if arg in signature_params:
                        if signature_params[arg].default == inspect.Parameter.empty:
                            decoded_params[arg] = args[signature_params_keys.index(arg) - 1]
                        else:
                            decoded_params[arg] = kwargs[arg]
                    else:
                        logger.error(
                            f'system_monitor function {func_name} param {arg} is not in the signature')
            try:
                task_id = before_task_started(
                    request_obj, api_name, initiator, task_id, decoded_params, is_intermediate, refund_if_task_failed, only_available_for)
                result = func(request, *args, **kwargs)
                status = 'finished'
                try:
                    message = json.dumps(result, ensure_ascii=False, sort_keys=True)
                except Exception as e:
                    logger.error(f'{task_id}: Json encode result failed {str(e)}.')
            except Exception as e:
                status = 'failed'
                message = f'{type(e).__name__}: {str(e)}'
                raise e
            finally:
                after_task_finished(request_obj, task_id, status, message, is_intermediate, refund_if_failed)
            return result

        return wrapper
    return function_wrapper


@contextmanager
def monitor_call_context(
        request: gr.Request,
        api_name: str,
        function_name: str,
        task_id: Optional[str] = None,
        decoded_params: Optional[dict] = None,
        is_intermediate: bool = True,
        refund_if_task_failed: bool = True,
        refund_if_failed: bool = False,
        only_available_for: Optional[list[str]] = None):
    status = 'unknown'
    message = ''
    task_is_failed = False
    def result_encoder(result, task_failed=False):
        try:
            nonlocal message
            nonlocal task_is_failed
            message = json.dumps(result, ensure_ascii=False, sort_keys=True)
            task_is_failed = task_failed
        except Exception as e:
            logger.error(f'{task_id}: Json encode result failed {str(e)}.')
    try:
        task_id = before_task_started(
            request, api_name, function_name, task_id, decoded_params, is_intermediate, refund_if_task_failed, only_available_for)
        logger.info(f"before step {function_name}: {task_id} Free VRAM: %.2f MB, Total VRAM: %.2f MB" % tuple(number / 1e6 for number in torch.cuda.mem_get_info()))
        yield result_encoder
        if task_is_failed:
            status = 'failed'
        else:
            status = 'finished'
        logger.info(f"after step {function_name}: {task_id} {status} Free VRAM: %.2f MB, Total VRAM: %.2f MB" % tuple(number / 1e6 for number in torch.cuda.mem_get_info()))
    except Exception as e:
        status = 'failed'
        message = f'{type(e).__name__}: {str(e)}'
        raise e
    finally:
        after_task_finished(request, task_id, status, message, is_intermediate, refund_if_failed)
