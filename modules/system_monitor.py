import json
import gradio as gr
import modules.user


class MonitorException(Exception):
    def __init__(self, msg):
        self._msg = msg

    def __repr__(self) -> str:
        return self._msg


class SystemMonitor:
    """ A remote SystemMonitorService client, the remote server can monitor and record GPU calls """

    def __init__(self):
        pass

    def on_task(self, request: gr.Request, func, *args, **kwargs):
        # get func args and fun name
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
            func_args[positional_args[i].name] = args[i]
        module = inspect.getmodule(func)

        func_args.update(**kwargs)
        func_name = func.__name__
        fund_module_name = module.__name__
        print(json.dumps({
            'api': f'{fund_module_name}.{func_name}',
            'user': modules.user.User.current_user(request).uid,
            'args': func_args,
            'extra_args': args[named_args_count + 1:] if named_args_count + 1 < len(args) else []
        }))
        e = MonitorException("<div class='error'>billing error</div>")
        print(e.__str__())
