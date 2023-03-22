import inspect
import warnings
from typing import Any, Callable, List

import gradio as gr


def special_args(
        fn: Callable,
        inputs: List[Any] | None = None,
        request: gr.Request | None = None,
):
    """
    Checks if function has special arguments Request.
    If inputs is provided, these values will be loaded into the inputs array.
    Parameters:
        fn: function to check.
        inputs: array to load special arguments into.
        request: request to load into inputs.
    Returns:
        updated inputs
    """
    signature = inspect.signature(fn)
    positional_args = []
    for i, param in enumerate(signature.parameters.values()):
        if param.kind not in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
            break
        positional_args.append(param)
    for i, param in enumerate(positional_args):
        if param.annotation == gr.Request:
            if inputs is not None:
                inputs.insert(i, request)
    if inputs is not None:
        while len(inputs) < len(positional_args):
            i = len(inputs)
            param = positional_args[i]
            if param.default == param.empty:
                warnings.warn("Unexpected argument. Filling with None.")
                inputs.append(None)
            else:
                inputs.append(param.default)
    return inputs or []


def check_insecure_calls():
    import modules.shared
    assert modules.shared.cmd_opts.enable_insecure_calls, "forbidden"
