import os
import pathlib
import sys
from modules.paths_internal import models_path, script_path, data_path, extensions_dir, extensions_builtin_dir

import starlette.requests

import modules.safe
import modules.user


# data_path = cmd_opts_pre.data
sys.path.insert(0, script_path)

# search for directory of stable diffusion in following places
sd_path = None
possible_sd_paths = [os.path.join(script_path, 'repositories/stable-diffusion-stability-ai'), '.', os.path.dirname(script_path)]
for possible_sd_path in possible_sd_paths:
    if os.path.exists(os.path.join(possible_sd_path, 'ldm/models/diffusion/ddpm.py')):
        sd_path = os.path.abspath(possible_sd_path)
        break

assert sd_path is not None, "Couldn't find Stable Diffusion in any of: " + str(possible_sd_paths)

path_dirs = [
    (sd_path, 'ldm', 'Stable Diffusion', []),
    (os.path.join(sd_path, '../taming-transformers'), 'taming', 'Taming Transformers', []),
    (os.path.join(sd_path, '../CodeFormer'), 'inference_codeformer.py', 'CodeFormer', []),
    (os.path.join(sd_path, '../BLIP'), 'models/blip.py', 'BLIP', []),
    (os.path.join(sd_path, '../k-diffusion'), 'k_diffusion/sampling.py', 'k_diffusion', ["atstart"]),
]

paths = {}

for d, must_exist, what, options in path_dirs:
    must_exist_path = os.path.abspath(os.path.join(script_path, d, must_exist))
    if not os.path.exists(must_exist_path):
        print(f"Warning: {what} not found at path {must_exist_path}", file=sys.stderr)
    else:
        d = os.path.abspath(d)
        if "atstart" in options:
            sys.path.insert(0, d)
        else:
            sys.path.append(d)
        paths[what] = d


class Paths:
    @classmethod
    def paths(cls, request: starlette.requests):
        user = modules.user.User.current_user(request)
        work_dir = pathlib.Path(data_path).joinpath('workdir').joinpath(user.uid)
        if not work_dir.exists():
            work_dir.mkdir(parents=True)

        model_dir = pathlib.Path(data_path).joinpath('models').joinpath(user.uid)
        if not work_dir.exists():
            work_dir.mkdir(parents=True)

        return Paths(work_dir, model_dir)

    def __init__(self, work_dir, model_dir):
        self._work_dir = work_dir
        self._model_dir = model_dir

    # dir to store generated images
    def generate_dir(self, object_type: str):
        output = self._work_dir.joinpath('generated').joinpath(object_type)
        if not output.exists():
            output.mkdir(parents=True)
        return str(output)

    # filename to store user prompt styles
    def styles_filename(self) -> str:
        return str(self._work_dir.joinpath('styles.csv'))

    # dir to store logs and saved images and zips
    def save_dir(self):
        save_dir = self._work_dir.joinpath('log').joinpath('images')
        if not save_dir.exists():
            save_dir.mkdir(parents=True)
        return str(save_dir)

    # dir to store user models
    def models_dir(self):
        return self._model_dir


class Prioritize:
    def __init__(self, name):
        self.name = name
        self.path = None

    def __enter__(self):
        self.path = sys.path.copy()
        sys.path = [paths[self.name]] + sys.path

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.path = self.path
        self.path = None
