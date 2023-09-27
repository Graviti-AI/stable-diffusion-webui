from contextlib import closing
import gradio as gr

import modules.scripts
from modules import processing
from modules.generation_parameters_copypaste import create_override_settings_dict
from modules.shared import opts, cmd_opts
import modules.shared as shared
from modules.ui import plaintext_to_html
from modules.paths import Paths
from modules.system_monitor import (
    generate_function_name, monitor_call_context)


def _get_str(elements):
    if isinstance(elements, list) and len(elements) > 0:
        return elements[0]
    elif isinstance(elements, str):
        return elements
    else:
        return None


def txt2img(request: gr.Request, id_task: str, prompt: str, negative_prompt: str, prompt_styles, steps: int, sampler_name: str, n_iter: int, batch_size: int, cfg_scale: float, height: int, width: int, enable_hr: bool, denoising_strength: float, hr_scale: float, hr_upscaler: str, hr_second_pass_steps: int, hr_resize_x: int, hr_resize_y: int, hr_checkpoint_name: str, hr_sampler_name: str, hr_prompt: str, hr_negative_prompt, restore_faces: bool, override_settings_texts, *args):
    override_settings = create_override_settings_dict(override_settings_texts)

    hr_checkpoint_name = _get_str(hr_checkpoint_name)
    hr_sampler_name = _get_str(hr_sampler_name)
    paths = Paths(request)
    p = processing.StableDiffusionProcessingTxt2Img(
        sd_model=shared.sd_model,
        outpath_samples=paths.outdir_txt2img_samples(),
        outpath_grids=paths.outdir_txt2img_grids(),
        prompt=prompt,
        styles=prompt_styles,
        negative_prompt=negative_prompt,
        sampler_name=sampler_name,
        batch_size=batch_size,
        n_iter=n_iter,
        steps=steps,
        cfg_scale=cfg_scale,
        width=width,
        height=height,
        enable_hr=enable_hr,
        denoising_strength=denoising_strength if enable_hr else None,
        hr_scale=hr_scale,
        hr_upscaler=hr_upscaler,
        hr_second_pass_steps=hr_second_pass_steps,
        hr_resize_x=hr_resize_x,
        hr_resize_y=hr_resize_y,
        hr_checkpoint_name=None if hr_checkpoint_name == 'Use same checkpoint' else hr_checkpoint_name,
        hr_sampler_name=None if hr_sampler_name == 'Use same sampler' else hr_sampler_name,
        hr_prompt=hr_prompt,
        hr_negative_prompt=hr_negative_prompt,
        restore_faces=restore_faces,
        override_settings=override_settings,
    )
    p.set_request(request)

    p.scripts = modules.scripts.scripts_txt2img
    p.script_args = args

    p.user = request.username

    if cmd_opts.enable_console_prompts:
        print(f"\ntxt2img: {prompt}", file=shared.progress_print_out)

    with closing(p):
        with monitor_call_context(
                request,
                generate_function_name(txt2img),
                generate_function_name(txt2img),
                decoded_params=processing.build_decoded_params_from_processing(p)):
            processed = modules.scripts.scripts_txt2img.run(p, *args)

            if processed is None:
                processed = processing.process_images(p)

    shared.total_tqdm.clear()

    generation_info_js = processed.js()
    if opts.samples_log_stdout:
        print(generation_info_js)

    if opts.do_not_show_images:
        processed.images = []

    return processed.images, generation_info_js, plaintext_to_html(processed.info), plaintext_to_html(processed.comments, classname="comments")
