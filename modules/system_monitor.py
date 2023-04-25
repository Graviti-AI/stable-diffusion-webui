import os
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
    def __init__(self, msg):
        self._msg = msg

    def __repr__(self) -> str:
        return self._msg


def _calculate_image_unit(width, height):
    return max(round((width * height) / (768 * 768)), 1)


def _calculate_step_unit(steps):
    return int(int(steps - 1) / 50 + 1)


def _calculate_consume_unit(func_name, named_args, *args, **kwargs):
    """
    Calculate how many unit the GPU func will consume.
    One unit means generate one image in (512 x 512) pixels

    Args:
        func_name: the gpu_call func name
        named_args: func args that has a name
        *args: func args that has no name
        **kwargs: kwargs

    Returns: consume unit
    """
    if func_name in ('modules.txt2img.txt2img', 'modules.img2img.img2img'):
        width = named_args.get('width', 512)
        height = named_args.get('height', 512)
        n_iter = named_args.get('n_iter', 1)
        batch_size = named_args.get('batch_size', 1)
        steps = named_args.get('steps', 20)
        enable_hr = named_args.get('enable_hr', False)
        if enable_hr:
            hr_scale = named_args.get('hr_scale', 2)
        else:
            hr_scale = 1

        # calculate consume unit
        image_unit = _calculate_image_unit(width * hr_scale, height * hr_scale)
        step_unit = _calculate_step_unit(steps)
        result = image_unit * batch_size * n_iter * step_unit
        return int(result)
    elif func_name in ('modules.postprocessing.run_postprocessing',):
        scale_type = args[3]  # 0: scale by, 1: scale to
        extras_mode = named_args.get('extras_mode', 0)

        if extras_mode == 0:  # single image
            image_count = 1
            if scale_type == 0:  # scale by, resultSize is srcSize * scaleBy
                scale = args[4]
                source_img_size = named_args.get('image', {}).get('size', (512, 512))

                width = source_img_size[0] * scale
                height = source_img_size[1] * scale
            else:  # scale to, resultSize is provided in request
                width = args[5]
                height = args[6]
            image_unit = _calculate_image_unit(width, height)
            result = image_unit * image_count
        elif extras_mode == 1:  # batch process
            from PIL import Image
            image_folder = args[2]
            image_count = len(image_folder)
            if scale_type == 0:  # scale by, need calculate resultSize for every image particularly
                result = 0
                for img in image_folder:
                    scale = args[4]
                    source_img = Image.open(img)
                    width = source_img.width * scale
                    height = source_img.width * scale

                    image_unit = _calculate_image_unit(width, height)
                    result += image_unit
            else:  # scale to, every image will be scaled to same size
                width = args[5]
                height = args[6]
                image_unit = _calculate_image_unit(width, height)
                result = image_count * image_unit
        else:
            result = 0
        return int(result)

    return 0


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
    obj_type = type(obj)
    if obj_type in (str, int, float, True, False, None):
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
        logger.error(f'system_monitor_addr or system_monitor_api_secret is not present')
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
        'consume': _calculate_consume_unit(api_name, func_args, *args, **kwargs),
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

    if resp.status_code == 402:
        raise MonitorException(
            f"<div class='error'>billing error: check <a href='/user' class='billing'>here</a> for more information.</div>"
        )
    else:
        raise MonitorException(
            f"<div class='error'>system error, please join our Discord <a href='https://discord.gg/darTYpt2Yh' class='support'>#support</a> channel to get more help.</div>"
        )


def on_task_finished(request: gr.Request, monitor_log_id: str, status: str, message: str, time_consumption: dict):
    monitor_addr = modules.shared.cmd_opts.system_monitor_addr
    system_monitor_api_secret = modules.shared.cmd_opts.system_monitor_api_secret
    if not monitor_addr or not system_monitor_api_secret:
        logger.error(f'system_monitor_addr or system_monitor_api_secret is not present')
        return
    request_url = f'{monitor_addr}/{monitor_log_id}'
    resp = requests.post(request_url,
                         headers={
                             'Api-Secret': system_monitor_api_secret,
                         },
                         json={
                             'status': status,
                             'message': message,
                             'time_consumption': time_consumption
                         })

    # log the response if request failed
    if resp.status_code < 200 or resp.status_code > 299:
        logger.error(
            f'update monitor log failed, status: monitor_log_id: {monitor_log_id}, {resp.status_code}, message: {resp.text[:1000]}')
