import os
import tempfile
import time
import uuid
import logging
import json
import requests

import gradio as gr

import modules.user
import modules.shared

logger = logging.getLogger(__name__)


class MonitorException(Exception):
    def __init__(self, status_code, msg):
        self.status_code = status_code
        self._msg = msg

    def __repr__(self) -> str:
        return self._msg


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
    elif func_name in ('modules.postprocessing.run_postprocessing',):
        result['type'] = 'extras'

        extras_mode = named_args.get('extras_mode', 0)
        source_image_folder = named_args.get('image_folder', [])
        source_image = named_args.get('image', {})
        if source_image:
            source_img_size = source_image.get('size', (512, 512))
        else:
            source_img_size = (1, 1)
        scale_type = args[4]  # 0: scale by, 1: scale to
        scale_by = args[5]
        scale_to = {
            'width': args[6],
            'height': args[7],
        }
        if extras_mode == 0:  # single image
            if scale_type == 0:  # scale by, resultSize is srcSize * scaleBy
                result['scale'] = scale_by
                result['image_sizes'].append({
                    'width': source_img_size[0],
                    'height': source_img_size[1],
                })
            else:  # scale to, resultSize is provided in request
                result['image_sizes'].append({
                    'width': scale_to['width'],
                    'height': scale_to['height'],
                })
        elif extras_mode == 1:  # batch process
            from PIL import Image
            image_count = len(source_image_folder)
            if scale_type == 0:  # scale by, need calculate resultSize for every image particularly
                result['scale'] = scale_by
                for img in source_image_folder:
                    source_img = Image.open(os.path.abspath(img['name']))
                    result['image_sizes'].append({
                        'width': source_img.width,
                        'height': source_img.height,
                    })
            else:  # scale to, every image will be scaled to same size
                result['image_sizes'] = [{'width': scale_to['width'], 'height': scale_to['height']} for _ in range(image_count)]

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


def on_task(request: gr.Request, func, task_info, *args, **kwargs):
    monitor_addr = modules.shared.cmd_opts.system_monitor_addr
    system_monitor_api_secret = modules.shared.cmd_opts.system_monitor_api_secret
    if not monitor_addr or not system_monitor_api_secret:
        logger.error('system_monitor_addr or system_monitor_api_secret is not present')
        return None

    monitor_log_id = _extract_task_id(*args)
    # inspect func args
    import inspect
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
    fund_module_name = module.__name__

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
    monitor_addr = modules.shared.cmd_opts.system_monitor_addr
    system_monitor_api_secret = modules.shared.cmd_opts.system_monitor_api_secret
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
