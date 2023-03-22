import os
import importlib.util
import sys

from modules import errors


def load_module(path):
    module_name = os.path.basename(path).strip(".py")
    module_spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    sys.modules[module_name] = module
    return module


def preload_extensions(extensions_dir, parser, extension_list=None):
    if not os.path.isdir(extensions_dir):
        return

    extensions = extension_list if extension_list is not None else os.listdir(extensions_dir)
    for dirname in sorted(extensions):
        preload_script = os.path.join(extensions_dir, dirname, "preload.py")
        if not os.path.isfile(preload_script):
            continue

        try:
            module = load_module(preload_script)
            if hasattr(module, 'preload'):
                module.preload(parser)

        except Exception:
            errors.report(f"Error running preload() for {preload_script}", exc_info=True)
