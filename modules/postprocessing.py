import os

import gradio as gr
from PIL import Image
import json

from modules import shared, images, devices, scripts, scripts_postprocessing, ui_common, infotext_utils
from modules.shared import opts
from modules.nsfw import nsfw_blur
from modules_forge.forge_util import prepare_free_memory



def run_postprocessing(
        request: gr.Request, id_task, extras_mode, image, image_folder, input_dir, output_dir, show_extras_results, *args, save_output: bool = True):
    prepare_free_memory(True)
    devices.torch_gc()

    shared.state.begin(job="extras")

    outputs = []
    caption_results = []

    def get_images(extras_mode, image, image_folder, input_dir):
        if extras_mode == 1:
            for img in image_folder:
                if isinstance(img, Image.Image):
                    image = img
                    fn = ''
                else:
                    image = Image.open(os.path.abspath(img.name))
                    fn = os.path.splitext(img.orig_name)[0]
                yield image, fn
        elif extras_mode == 2:
            import modules.call_utils
            modules.call_utils.check_insecure_calls()
            assert not shared.cmd_opts.hide_ui_dir_config, '--hide-ui-dir-config option must be disabled'
            assert input_dir, 'input directory not selected'

            image_list = shared.listfiles(input_dir)
            for filename in image_list:
                yield filename, filename
        else:
            assert image, 'image not selected'
            yield image, None

    if extras_mode == 2 and output_dir != '':
        outpath = output_dir
    else:
        from modules.paths import Paths
        outpath = Paths(request).outdir_extras_samples()

    infotext = ''

    data_to_process = list(get_images(extras_mode, image, image_folder, input_dir))
    shared.state.job_count = len(data_to_process)

    for image_placeholder, name in data_to_process:
        shared.state.nextjob()
        shared.state.textinfo = name
        shared.state.skipped = False

        if shared.state.interrupted:
            break

        if isinstance(image_placeholder, str):
            try:
                image_data = Image.open(image_placeholder)
            except Exception:
                continue
        else:
            image_data = image_placeholder

        if image_data.width > 2048 or image_data.height > 2048:
            raise Exception(f'image oversize: maximum weight/height is 2048')

        shared.state.assign_current_image(image_data)

        parameters, existing_pnginfo = images.read_info_from_image(image_data)
        if parameters:
            existing_pnginfo["parameters"] = parameters

        initial_pp = scripts_postprocessing.PostprocessedImage(image_data.convert("RGB"))
        initial_pp.set_request(request)

        scripts.scripts_postproc.run(initial_pp, args)

        if shared.state.skipped:
            continue

        used_suffixes = {}
        for pp in [initial_pp, *initial_pp.extra_images]:
            suffix = pp.get_suffix(used_suffixes)

            if opts.use_original_name_batch and name is not None:
                basename = os.path.splitext(os.path.basename(name))[0]
                forced_filename = basename + suffix
            else:
                basename = ''
                forced_filename = None

            infotext = ", ".join([k if k == v else f'{k}: {infotext_utils.quote(v)}' for k, v in pp.info.items() if v is not None])

            if opts.enable_pnginfo:
                pp.image.info = existing_pnginfo
                pp.image.info["extras"] = infotext

            shared.state.assign_current_image(pp.image)

            if save_output:
                from modules.processing import get_fixed_seed
                # we make a StableDiffusionProcessing here to let on_image_saved script can get request from it
                from modules.processing import StableDiffusionProcessing

                p = StableDiffusionProcessing()
                p.set_request(request)
                p.feature = "EXTRAS"

                pp.image, nsfw_result = nsfw_blur(pp.image, None, p)

                if not getattr(pp.image, "is_nsfw", False):
                    fullfn, _ = images.save_image(pp.image, path=outpath, basename=basename, seed=get_fixed_seed(-1), extension=opts.samples_format, info=infotext, short_filename=False, no_prompt=True, grid=False, pnginfo_section_name="extras", existing_info=existing_pnginfo, forced_filename=forced_filename, suffix=suffix, p=p, save_to_dirs=True, nsfw_result=nsfw_result)

                if pp.caption and False:
                    caption_filename = os.path.splitext(fullfn)[0] + ".txt"
                    existing_caption = ""
                    try:
                        with open(caption_filename, encoding="utf8") as file:
                            existing_caption = file.read().strip()
                    except FileNotFoundError:
                        pass

                    action = shared.opts.postprocessing_existing_caption_action
                    if action == 'Prepend' and existing_caption:
                        caption = f"{existing_caption} {pp.caption}"
                    elif action == 'Append' and existing_caption:
                        caption = f"{pp.caption} {existing_caption}"
                    elif action == 'Keep' and existing_caption:
                        caption = existing_caption
                    else:
                        caption = pp.caption

                    caption = caption.strip()
                    if caption:
                        with open(caption_filename, "w", encoding="utf8") as file:
                            file.write(caption)

            if extras_mode != 2 or show_extras_results:
                outputs.append(pp.image)
                if pp.caption:
                    caption_lines = [ui_common.plaintext_to_html(f"{key}:\n{value}") for key, value in pp.caption.items()]
                    caption_results.append("".join(caption_lines))
                else:
                    caption_results.append(None)

        image_data.close()

    devices.torch_gc()
    shared.state.end()

    infotext_html = ui_common.plaintext_to_html(infotext)
    infotext_result = infotext_html
    if caption_results and caption_results[0] is not None:
        infotext_result += caption_results[0]

    return outputs, json.dumps({"info": infotext_html, "captions": caption_results}), infotext_result, ''


def run_postprocessing_webui(request: gr.Request, id_task, *args, **kwargs):
    return run_postprocessing(request, id_task, *args, **kwargs)


def monitor_extras_params(component, name: str, extractor: str | None = None) -> None:
    js = (
        f"monitorThisParam('tab_extras', 'modules.extras', '{name}')"
        if not extractor else
        f"monitorThisParam('tab_extras', 'modules.extras', '{name}', extractor = {extractor})"
    )

    component.change(None, inputs=[], outputs=[component], _js=js)


def run_extras(request: gr.Request, id_task, extras_mode, resize_mode, image, image_folder, input_dir, output_dir, show_extras_results, gfpgan_visibility, codeformer_visibility, codeformer_weight, upscaling_resize, upscaling_resize_w, upscaling_resize_h, upscaling_crop, extras_upscaler_1, extras_upscaler_2, extras_upscaler_2_visibility, upscale_first: bool, save_output: bool = True):
    """old handler for API"""

    args = scripts.scripts_postproc.create_args_for_run({
        "Upscale": {
            "upscale_mode": resize_mode,
            "upscale_by": upscaling_resize,
            "upscale_to_width": upscaling_resize_w,
            "upscale_to_height": upscaling_resize_h,
            "upscale_crop": upscaling_crop,
            "upscaler_1_name": extras_upscaler_1,
            "upscaler_2_name": extras_upscaler_2,
            "upscaler_2_visibility": extras_upscaler_2_visibility,
        },
        "GFPGAN": {
            "enable": True,
            "gfpgan_visibility": gfpgan_visibility,
        },
        "CodeFormer": {
            "enable": True,
            "codeformer_visibility": codeformer_visibility,
            "codeformer_weight": codeformer_weight,
        },
    })

    return run_postprocessing(request, id_task, extras_mode, image, image_folder, input_dir, output_dir, show_extras_results, *args, save_output=save_output)
