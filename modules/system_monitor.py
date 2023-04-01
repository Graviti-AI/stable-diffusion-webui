import requests

import gradio as gr

import modules.user
import modules.shared


class MonitorException(Exception):
    def __init__(self, msg):
        self._msg = msg

    def __repr__(self) -> str:
        return self._msg


def _calculate_image_unit(width, height):
    return int((int((width - 1) / 512) + 1) * (int((height - 1) / 512) + 1))


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
        batch_count = named_args.get('n_iter', 1)
        batch_size = named_args.get('batch_size', 1)
        steps = named_args.get('steps', 20)

        # calculate consume unit
        image_unit = _calculate_image_unit(width, height)
        step_count = _calculate_step_unit(steps)
        result = image_unit * batch_size * batch_count * step_count
        return int(result)
    elif func_name in ('modules.postprocessing.run_postprocessing',):
        scale_type = args[6]  # 0: scale by, 1: scale to
        extras_mode = named_args.get('extras_mode', 0)

        if extras_mode == 0:  # single image
            image_count = 1
            if scale_type == 0:  # scale by, resultSize is srcSize * scaleBy
                scale = args[7]
                source_img_size = named_args.get('image', {}).get('size', (512, 512))

                width = source_img_size[0] * scale
                height = source_img_size[1] * scale
            else:  # scale to, resultSize is provided in request
                width = args[8]
                height = args[9]
            image_unit = _calculate_image_unit(width, height)
            result = image_unit * image_count
        elif extras_mode == 1:  # batch process
            from PIL import Image
            image_folder = args[2]
            image_count = len(image_folder)
            if scale_type == 0:  # scale by, need calculate resultSize for every image particularly
                result = 0
                for img in image_folder:
                    scale = args[7]
                    source_img = Image.open(img)
                    width = source_img.width * scale
                    height = source_img.width * scale

                    image_unit = _calculate_image_unit(width, height)
                    result += image_unit
            else:  # scale to, every image will be scaled to same size
                width = args[8]
                height = args[9]
                image_unit = _calculate_image_unit(width, height)
                result = image_count * image_unit
        else:
            result = 1
        return int(result)

    return 1


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


def on_task(request: gr.Request, func, *args, **kwargs):
    monitor_addr = modules.shared.cmd_opts.system_monitor_addr
    system_monitor_api_secret = modules.shared.cmd_opts.system_monitor_api_secret
    if not monitor_addr or not system_monitor_api_secret:
        return

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
        'user': modules.user.User.current_user(request).uid,
        'args': func_args,
        'extra_args': _serialize_object(args[named_args_count + 1:]) if named_args_count + 1 < len(args) else [],
        'consume': _calculate_consume_unit(api_name, func_args, *args, **kwargs)
    }
    resp = requests.post(monitor_addr,
                         headers={
                             'Api-Secret': system_monitor_api_secret,
                         },
                         json=request_data)

    # check response, raise exception if status code is not 2xx
    if 199 < resp.status_code < 300:
        return
    elif resp.status_code == 402:
        raise MonitorException(
            f"<div class='error'>billing error: check <a href='/user' class='billing'>here</a> for more information.</div>"
        )
    else:
        raise MonitorException(
            f"<div class='error'>system error, please join our Discord <a href='https://discord.gg/darTYpt2Yh' class='support'>#support</a> channel to get more help.</div>"
        )
