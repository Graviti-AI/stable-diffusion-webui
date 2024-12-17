import os
import pathlib
import shutil
import sys
from modules.paths_internal import models_path, script_path, data_path, workdir_path, binary_dir, model_dir_path, configs_dir, extensions_dir, extensions_builtin_dir, MODEL_CONTAINER_NAME, cwd  # noqa: F401

import modules.user

import gradio as gr

WORKDIR_NAME = os.getenv('WORKDIR_NAME', 'workdir')
COMFYUI_WORKDIR_NAME = os.getenv('COMFYUI_WORKDIR_NAME', WORKDIR_NAME)
workdir = pathlib.Path(workdir_path, WORKDIR_NAME)

sys.path.insert(0, script_path)

sd_path = os.path.dirname(__file__)

path_dirs = [
    (os.path.join(sd_path, '../repositories/BLIP'), 'models/blip.py', 'BLIP', []),
    (os.path.join(sd_path, '../packages_3rdparty'), 'gguf/quants.py', 'packages_3rdparty', []),
    # (os.path.join(sd_path, '../repositories/k-diffusion'), 'k_diffusion/sampling.py', 'k_diffusion', ["atstart"]),
    (os.path.join(sd_path, '../repositories/huggingface_guess'), 'huggingface_guess/detection.py', 'huggingface_guess', []),
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
    PRIVATE_IMAGE_ALLOWED_TIERS = {"basic", "plus", "pro", "api", "ltd s", "appsumo ltd tier 1", "appsumo ltd tier 2"}

    def __init__(self, request: gr.Request | None):
        import hashlib
        user = modules.user.User.current_user(request)
        self.user = user

        base_dir = pathlib.Path(workdir_path)

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
        # comfyui dir save user comfy output file
        self._comfyui_work_dir = base_dir.joinpath(COMFYUI_WORKDIR_NAME, *parents_path)
        if not self._comfyui_work_dir.exists():
            self._comfyui_work_dir.mkdir(parents=True, exist_ok=True)
        # deprecated ,model dir save user uploaded models
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

    def comfyui_favorites_dir(self) -> pathlib.Path:
        return self._check_dir(self._comfyui_work_dir.joinpath('favorites'))

    def public_outdir(self) -> pathlib.Path:
        return self._check_dir(pathlib.Path(workdir_path, WORKDIR_NAME, 'public', 'outputs'))

    def shared_outdir(self) -> pathlib.Path:
        return self._check_dir(pathlib.Path(workdir_path, WORKDIR_NAME, 'shared', 'outputs'))

    def private_outdir(self) -> pathlib.Path:
        return self._check_dir(self._private_output_dir)

    def private_comfyui_outdir(self) -> pathlib.Path:
        return self._check_dir(self._comfyui_work_dir.joinpath('output'))

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
