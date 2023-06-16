import base64
import logging
import os
import pathlib
import sys

import gradio as gr

from modules.paths_internal import models_path, script_path, data_path, extensions_dir, extensions_builtin_dir

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
    def __init__(self, request: gr.Request | None):
        import hashlib
        user = modules.user.User.current_user(request)

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
        self._work_dir = base_dir.joinpath('workdir', *parents_path)
        if not self._work_dir.exists():
            self._work_dir.mkdir(parents=True, exist_ok=True)

        # model dir save user uploaded models
        self._model_dir = base_dir.joinpath('models', *parents_path)
        if not self._model_dir.exists():
            self._model_dir.mkdir(parents=True, exist_ok=True)

        # output dir save user generated files
        self._private_output_dir = base_dir.joinpath('workdir', *parents_path, 'outputs')
        if not user.tire or user.tire.lower() == 'free':
            # free users use same output dir
            self._output_dir = base_dir.joinpath('workdir', 'public', 'outputs')
        else:
            # other users use their own dir
            self._output_dir = self._private_output_dir
        self._fix_legacy_workdir(base_dir, user.uid)

        splits = user.uid.split('|')
        if len(splits) > 1:
            self._fix_legacy2_workdir(base_dir, splits[1])

    def _fix_legacy_workdir(self, base_dir: pathlib.Path, uid: str):
        splits = uid.split('|')
        if len(splits) > 1:
            legacy_uid = splits[1]
        else:
            legacy_uid = uid
        legacy_workdir = base_dir.joinpath('workdir', legacy_uid)
        if legacy_workdir.exists():
            self._move_files(legacy_workdir, self._work_dir)

        legacy_model_dir = base_dir.joinpath('models', legacy_uid)
        if legacy_model_dir.exists():
            self._move_files(legacy_model_dir, self._model_dir)

        legacy_output_dir = base_dir.joinpath('workdir', legacy_uid, 'outputs')
        if legacy_output_dir.exists():
            self._move_files(legacy_output_dir, self._output_dir)

    def _fix_legacy2_workdir(self, base_dir: pathlib.Path, legacy_uid: str):
        import hashlib
        # legacy_uid = uid
        # encode uid to avoid uid has path invalid character
        h = hashlib.sha256()
        h.update(legacy_uid.encode('utf-8'))
        encoded_user_path = h.hexdigest()
        # same user data in 4 level folders, to prevent a folder has too many subdir
        parents_path = (encoded_user_path[:2],
                        encoded_user_path[2:4],
                        encoded_user_path[4:6],
                        encoded_user_path)

        # work dir save user output files
        legacy_workdir = base_dir.joinpath('workdir', *parents_path)
        if legacy_workdir.exists():
            self._move_files(legacy_workdir, self._work_dir)

        # model dir save user uploaded models
        legacy_model_dir = base_dir.joinpath('models', *parents_path)
        if legacy_model_dir.exists():
            self._move_files(legacy_model_dir, self._model_dir)

        # other users use their own dir
        legacy_output_dir = base_dir.joinpath('workdir', *parents_path, 'outputs')
        if legacy_output_dir.exists():
            self._move_files(legacy_output_dir, self._output_dir)

    @staticmethod
    def _move_files(from_dir: pathlib.Path, to_dir: pathlib.Path):
        try:
            import shutil
            if from_dir.__str__() == to_dir.__str__():
                return
            if not from_dir.exists() or not to_dir.exists():
                return

            for item in from_dir.iterdir():
                item_name = item.name
                dst = to_dir.joinpath(item_name)
                if item.is_dir():
                    dst.mkdir(exist_ok=True)
                    Paths._move_files(item, dst)
                else:
                    if not dst.exists():
                        shutil.move(item, dst)
                    else:
                        item.unlink()

            from_dir.rmdir()
        except Exception as e:
            logging.error(f'paths: move_files failed: {e.__str__()}')
            pass

    @staticmethod
    def _check_dir(path):
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        return path

    def outdir(self):
        return self._check_dir(self._output_dir)

    def private_outdir(self):
        return self._check_dir(self._private_output_dir)

    # 'Output directory for txt2img images
    def outdir_txt2img_samples(self):
        return self._check_dir(self._output_dir.joinpath("txt2img", 'samples'))

    # Output directory for img2img images
    def outdir_img2img_samples(self):
        return self._check_dir(self._output_dir.joinpath("img2img", 'samples'))

    # Output directory for images from extras tab
    def outdir_extras_samples(self):
        return self._check_dir(self._output_dir.joinpath("extras", 'samples'))

    # Output directory for txt2img grids
    def outdir_txt2img_grids(self):
        return self._check_dir(self._output_dir.joinpath("txt2img", 'grids'))

    # Output directory for img2img grids
    def outdir_img2img_grids(self):
        return self._check_dir(self._output_dir.joinpath("img2img", 'grids'))

    # Directory for saving images using the Save button
    def outdir_save(self):
        return self._check_dir(self._work_dir.joinpath('save'))

    # filename to store user prompt styles
    def styles_filename(self) -> str:
        return str(self._work_dir.joinpath('styles.csv'))

    # dir to store logs and saved images and zips
    def save_dir(self):
        save_dir = self._work_dir.joinpath('log', 'images')
        return self._check_dir(save_dir)

    # dir to store user models
    def models_dir(self):
        return self._check_dir(self._model_dir)

    # dir to store user model previews
    def model_previews_dir(self):
        return self._check_dir(self._work_dir.joinpath("model_previews"))

    def save_image(self, filename: str):
        if self._private_output_dir == self._output_dir:
            # image file generated in private output dir, do nothing
            pass
        elif filename.startswith(str(self._work_dir)):
            # image file is already in work dir, do nothing
            pass
        else:
            # image is generated at public folder, make a symlink to src image
            src_path = pathlib.Path(filename)
            relative_to = src_path.relative_to(self._output_dir)
            # out_put_dir = src_path.parents[3]
            # dest_path = self._private_output_dir.joinpath(src_path.parts[-4],
            #                                               src_path.parts[-3],
            #                                               src_path.parts[-2],
            #                                               src_path.parts[-1])
            dest_path = self._private_output_dir.joinpath(relative_to)
            if not dest_path.parent.exists():
                dest_path.parent.mkdir(parents=True, exist_ok=True)
            dest_path.symlink_to(src_path)


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
