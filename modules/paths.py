import os
import pathlib
import shutil
import sys
from modules.paths_internal import models_path, script_path, data_path, binary_dir, configs_dir, extensions_dir, extensions_builtin_dir, MODEL_CONTAINER_NAME  # noqa: F401

import modules.safe  # noqa: F401
import modules.user

import gradio as gr

WORKDIR_NAME = os.getenv('WORKDIR_NAME', 'workdir')
workdir = pathlib.Path(data_path, WORKDIR_NAME)

def mute_sdxl_imports():
    """create fake modules that SDXL wants to import but doesn't actually use for our purposes"""

    class Dummy:
        pass

    module = Dummy()
    module.LPIPS = None
    sys.modules['taming.modules.losses.lpips'] = module

    module = Dummy()
    module.StableDataModuleFromConfig = None
    sys.modules['sgm.data'] = module


# data_path = cmd_opts_pre.data
sys.path.insert(0, script_path)

# search for directory of stable diffusion in following places
sd_path = None
possible_sd_paths = [os.path.join(script_path, 'repositories/stable-diffusion-stability-ai'), '.', os.path.dirname(script_path)]
for possible_sd_path in possible_sd_paths:
    if os.path.exists(os.path.join(possible_sd_path, 'ldm/models/diffusion/ddpm.py')):
        sd_path = os.path.abspath(possible_sd_path)
        break

assert sd_path is not None, f"Couldn't find Stable Diffusion in any of: {possible_sd_paths}"

mute_sdxl_imports()

path_dirs = [
    (sd_path, 'ldm', 'Stable Diffusion', []),
    (os.path.join(sd_path, '../generative-models'), 'sgm', 'Stable Diffusion XL', ["sgm"]),
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
        elif "sgm" in options:
            # Stable Diffusion XL repo has scripts dir with __init__.py in it which ruins every extension's scripts dir, so we
            # import sgm and remove it from sys.path so that when a script imports scripts.something, it doesbn't use sgm's scripts dir.

            sys.path.insert(0, d)
            import sgm  # noqa: F401
            sys.path.pop(0)
        else:
            sys.path.append(d)
        paths[what] = d


class Paths:
    def __init__(self, request: gr.Request | None):
        import hashlib
        user = modules.user.User.current_user(request)
        self.user = user

        base_dir = pathlib.Path(data_path)

        # encode uid to avoid uid has path invalid character
        h = hashlib.sha256()
        h.update(user.uid.encode('utf-8'))
        encoded_user_path = h.hexdigest()
        # same user data in 4 level folders, to prevent a folder has too many subdir
        parents_path = (encoded_user_path[:2],
                        encoded_user_path[2:4],
                        encoded_user_path[4:6],
                        encoded_user_path)

        # work dir save user output files
        self._work_dir = base_dir.joinpath(WORKDIR_NAME, *parents_path)
        if not self._work_dir.exists():
            self._work_dir.mkdir(parents=True, exist_ok=True)

        # model dir save user uploaded models
        self._model_dir = base_dir.joinpath(MODEL_CONTAINER_NAME, *parents_path)
        if not self._model_dir.exists():
            self._model_dir.mkdir(parents=True, exist_ok=True)

        # output dir save user generated files
        self._private_output_dir = self._work_dir.joinpath('outputs')
        self._output_dir = self._private_output_dir

        # favorite dir
        self._favorite_dir = self._work_dir.joinpath('favorites')

    @staticmethod
    def _check_dir(path: pathlib.Path):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        return path

    def workdir(self) -> pathlib.Path:
        return self._check_dir(self._work_dir)

    def outdir(self, force_to_private=False) -> pathlib.Path:
        return self._get_output_dir(force_to_private)

    def favorites_dir(self) -> pathlib.Path:
        return self._check_dir(self._favorite_dir)

    def public_outdir(self) -> pathlib.Path:
        return self._check_dir(pathlib.Path(data_path).joinpath(WORKDIR_NAME, 'public', 'outputs'))

    def shared_outdir(self) -> pathlib.Path:
        return self._check_dir(pathlib.Path(data_path).joinpath(WORKDIR_NAME, 'shared', 'outputs'))

    def private_outdir(self) -> pathlib.Path:
        return self._check_dir(self._private_output_dir)

    def private_tempdir(self) -> pathlib.Path:
        return self._check_dir(self._work_dir.joinpath('temp'))

    def _get_output_dir(self, force_to_private):
        return self._private_output_dir if force_to_private else self._output_dir

    # 'Output directory for txt2img images
    def outdir_txt2img_samples(self, force_to_private=False):
        return self._check_dir(self._get_output_dir(force_to_private).joinpath("txt2img", 'samples'))

    # Output directory for img2img images
    def outdir_img2img_samples(self, force_to_private=False):
        return self._check_dir(self._get_output_dir(force_to_private).joinpath("img2img", 'samples'))

    # Output directory for images from extras tab
    def outdir_extras_samples(self, force_to_private=False):
        return self._check_dir(self._get_output_dir(force_to_private).joinpath("extras", 'samples'))

    # 'Output directory for txt2img images
    def favorite_dir_txt2img_samples(self) -> pathlib.Path:
        return self._check_dir(self._favorite_dir.joinpath("txt2img", 'samples'))

    # Output directory for img2img images
    def favorite_dir_img2img_samples(self) -> pathlib.Path:
        return self._check_dir(self._favorite_dir.joinpath("img2img", 'samples'))

    # Output directory for images from extras tab
    def favorite_dir_extras_samples(self) -> pathlib.Path:
        return self._check_dir(self._favorite_dir.joinpath("extras", 'samples'))

    # Output directory for txt2img grids
    def outdir_txt2img_grids(self, force_to_private=False) -> pathlib.Path:
        return self._check_dir(self._get_output_dir(force_to_private).joinpath("txt2img", 'grids'))

    # Output directory for img2img grids
    def outdir_img2img_grids(self, force_to_private=False) -> pathlib.Path:
        return self._check_dir(self._get_output_dir(force_to_private).joinpath("img2img", 'grids'))

    # Directory for saving images using the Save button
    def outdir_save(self) -> pathlib.Path:
        return self._check_dir(self._work_dir.joinpath('save'))

    # filename to store user prompt styles
    def styles_filename(self) -> str:
        return str(self._work_dir.joinpath('styles.csv'))

    # dir to store logs and saved images and zips
    def save_dir(self) -> pathlib.Path:
        save_dir = self._work_dir.joinpath('log', 'images')
        return self._check_dir(save_dir)

    # dir to store user models
    def models_dir(self) -> pathlib.Path:
        return self._check_dir(self._model_dir)

    # dir to store user model previews
    def model_previews_dir(self) -> pathlib.Path:
        return self._check_dir(self._work_dir.joinpath("model_previews"))

    def save_image(self, filename: str):
        # copy the generated image to public dir if user is free tier.
        if not self.user.tire or self.user.tire.lower() == 'free':
            src_path = pathlib.Path(filename)

            if not src_path.is_relative_to(self._output_dir):
                return

            relative_to = src_path.relative_to(self._output_dir)
            dst_path = self.public_outdir().joinpath(relative_to)
            if not dst_path.parent.exists():
                dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_path, dst_path)


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


def get_binary_path(sha256: str) -> pathlib.Path:
    sha256 = sha256.lower()
    return pathlib.Path(binary_dir) / sha256[:2] / sha256[2:4] / sha256[4:6] / sha256


def get_config_path(sha256: str) -> pathlib.Path:
    sha256 = sha256.lower()
    return pathlib.Path(configs_dir) / sha256
