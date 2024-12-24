import datetime
import mimetypes
import os
import sys
from functools import reduce
import warnings
import inspect
import json
from typing import Optional, List, Callable
from contextlib import ExitStack

import gradio as gr
import gradio.utils
from gradio.components.image_editor import Brush
from PIL import Image, PngImagePlugin  # noqa: F401
from modules.call_queue import wrap_gradio_gpu_call, wrap_queued_call, wrap_gradio_call, wrap_gradio_call_no_job # noqa: F401

from modules import gradio_extensions, sd_schedulers  # noqa: F401
from modules import sd_hijack, sd_models, script_callbacks, ui_extensions, deepbooru, extra_networks, ui_common, ui_postprocessing, progress, ui_loadsave, shared_items, ui_settings, timer, sysinfo, ui_checkpoint_merger, scripts, sd_samplers, processing, ui_extra_networks, ui_toprow, launch_utils
from modules import localization, ui_prompt_styles
from modules.model_info import AllModelInfo, MODEL_INFO_KEY
from modules.ui_components import FormRow, FormGroup, ToolButton, FormHTML, InputAccordion, ResizeHandleRow
from modules.paths import script_path, Paths
from modules.ui_common import create_refresh_button
from modules.ui_gradio_extensions import reload_javascript

from modules.shared import opts, cmd_opts

import modules.infotext_utils as parameters_copypaste
import modules.shared as shared
import modules.images
import modules.styles
from modules import prompt_parser
from modules.infotext_utils import image_from_url_text, PasteField
from modules_forge.forge_canvas.canvas import ForgeCanvas, canvas_head
from modules_forge import main_entry, forge_space
import modules.processing_scripts.comments as comments


from modules.call_queue import submit_to_gpu_worker_with_request
from modules.system_monitor import monitor_call_context
from modules_forge.utils import prepare_free_memory

create_setting_component = ui_settings.create_setting_component

warnings.filterwarnings("default" if opts and opts.show_warnings else "ignore", category=UserWarning)
warnings.filterwarnings("default" if opts and opts.show_gradio_deprecation_warnings else "ignore", category=gradio_extensions.GradioDeprecationWarning)

# this is a fix for Windows users. Without it, javascript files will be served with text/html content-type and the browser will not show any UI
mimetypes.init()
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('application/javascript', '.mjs')

# Likewise, add explicit content-type header for certain missing image types
mimetypes.add_type('image/webp', '.webp')
mimetypes.add_type('image/avif', '.avif')

if not cmd_opts.share and not cmd_opts.listen:
    # fix gradio phoning home
    gradio.utils.version_check = lambda: None
    gradio.utils.get_local_ip_address = lambda: '127.0.0.1'

if cmd_opts.ngrok is not None:
    import modules.ngrok as ngrok
    print('ngrok authtoken detected, trying to connect...')
    ngrok.connect(
        cmd_opts.ngrok,
        cmd_opts.port if cmd_opts.port is not None else 7860,
        cmd_opts.ngrok_options
        )


def gr_show(visible=True):
    return {"visible": visible, "__type__": "update"}


sample_img2img = "assets/stable-samples/img2img/sketch-mountains-input.jpg"
sample_img2img = sample_img2img if os.path.exists(sample_img2img) else None

# Using constants for these since the variation selector isn't visible.
# Important that they exactly match script.js for tooltip to work.
random_symbol = '\U0001f3b2\ufe0f'  # 🎲️
reuse_symbol = '\u267b\ufe0f'  # ♻️
paste_symbol = '\u2199\ufe0f'  # ↙
refresh_symbol = '\U0001f504'  # 🔄
save_style_symbol = '\U0001f4be'  # 💾
apply_style_symbol = '\U0001f4cb'  # 📋
clear_prompt_symbol = '\U0001f5d1\ufe0f'  # 🗑️
extra_networks_symbol = '\U0001F3B4'  # 🎴
switch_values_symbol = '\U000021C5' # ⇅
restore_progress_symbol = '\U0001F300' # 🌀
detect_image_size_symbol = '\U0001F4D0'  # 📐


plaintext_to_html = ui_common.plaintext_to_html


def send_gradio_gallery_to_image(x):
    if len(x) == 0:
        return None
    return image_from_url_text(x[0])


def calc_resolution_hires(request: gr.Request, enable, width, height, hr_scale, hr_resize_x, hr_resize_y):

    if not enable:
        return ""

    p = processing.StableDiffusionProcessingTxt2Img(width=width, height=height, enable_hr=True, hr_scale=hr_scale, hr_resize_x=hr_resize_x, hr_resize_y=hr_resize_y)
    p.calculate_target_resolution()
    p.set_request(request)

    new_width = p.hr_resize_x or p.hr_upscale_to_x
    new_height = p.hr_resize_y or p.hr_upscale_to_y
    
    new_width -= new_width % 8        #   note: hardcoded latent size 8
    new_height -= new_height % 8

    return f"from <span class='resolution'>{p.width}x{p.height}</span> to <span class='resolution'>{new_width}x{new_height}</span>"


def resize_from_to_html(width, height, scale_by):
    if width * scale_by > 4096 or height * scale_by > 4096:
        target_width = 4096
        target_height = 4096
        return f"<span class='resolution' style='color: red'>Maximum Size {target_width}x{target_height}</span>"

    target_width = int(float(width) * scale_by)
    target_height = int(float(height) * scale_by)

    if not target_width or not target_height:
        return "no image selected"

    target_width -= target_width % 8        #   note: hardcoded latent size 8
    target_height -= target_height % 8

    return f"resize: from <span class='resolution'>{width}x{height}</span> to <span class='resolution'>{target_width}x{target_height}</span>"


def apply_styles(request: gr.Request, prompt, prompt_neg, styles):
    prompt = shared.prompt_styles(request).apply_styles_to_prompt(prompt, styles)
    prompt_neg = shared.prompt_styles(request).apply_negative_styles_to_prompt(prompt_neg, styles)

    return [gr.Textbox.update(value=prompt), gr.Textbox.update(value=prompt_neg), gr.Dropdown.update(value=[])]


def interrogate_processor_getter(interrogation_function):
    def processor(request: gr.Request, id_task, *args):
        def monitored_interrogation_function(image):
            with monitor_call_context(
                request,
                "extras.caption",
                "extras.caption",
                decoded_params={
                    "width": image.width,
                    "height": image.height,
                    "option_number": 1,
                },
            ):
                return interrogation_function(image)

        results = process_interrogate(monitored_interrogation_function, *args)
        if not results:
            return None

        return results + [""]

    return processor


def process_interrogate(interrogation_function, mode, ii_input_dir, ii_output_dir, *ii_singles):
    prepare_free_memory(True)

    mode = int(mode)
    if mode in (0, 1, 3, 4):
        return [interrogation_function(ii_singles[mode]), None]
    elif mode == 2:
        return [interrogation_function(ii_singles[mode]), None]
    elif mode == 5:
        assert not shared.cmd_opts.hide_ui_dir_config, "Launched with --hide-ui-dir-config, batch img2img disabled"
        images = shared.listfiles(ii_input_dir)
        print(f"Will process {len(images)} images.")
        if ii_output_dir != "":
            os.makedirs(ii_output_dir, exist_ok=True)
        else:
            ii_output_dir = ii_input_dir

        for image in images:
            img = Image.open(image)
            filename = os.path.basename(image)
            left, _ = os.path.splitext(filename)
            print(interrogation_function(img), file=open(os.path.join(ii_output_dir, f"{left}.txt"), 'a', encoding='utf-8'))

        return [gr.update(), None]


def interrogate(image):
    if shared.interrogator is None:
        raise ValueError("Interrogator not initialized")
    prompt = shared.interrogator.interrogate(image.convert("RGB"))
    return gr.update() if prompt is None else prompt


def interrogate_deepbooru(image):
    prompt = deepbooru.model.tag(image)
    return gr.update() if prompt is None else prompt


def connect_clear_prompt(button):
    """Given clear button, prompt, and token_counter objects, setup clear prompt button click event"""
    button.click(
        _js="clear_prompt",
        fn=None,
        inputs=[],
        outputs=[],
    )


def update_token_counter(request: gr.Request, text, steps, styles, *, is_positive=True):
    params = script_callbacks.BeforeTokenCounterParams(text, steps, styles, is_positive=is_positive)
    script_callbacks.before_token_counter_callback(params)
    text = params.prompt
    steps = params.steps
    styles = params.styles
    is_positive = params.is_positive

    if shared.opts.include_styles_into_token_counters and styles:
        prompt_styles = shared.prompt_styles(request)

        apply_styles = prompt_styles.apply_styles_to_prompt if is_positive else prompt_styles.apply_negative_styles_to_prompt
        text = apply_styles(text, styles)
    else:
        text = comments.strip_comments(text).strip()

    try:
        text, _ = extra_networks.parse_prompt(text)

        if is_positive:
            _, prompt_flat_list, _ = prompt_parser.get_multicond_prompt_list([text])
        else:
            prompt_flat_list = [text]

        prompt_schedules = prompt_parser.get_learned_conditioning_prompt_schedules(prompt_flat_list, steps)

    except Exception:
        # a parsing error can happen here during typing, and we don't want to bother the user with
        # messages related to it in console
        prompt_schedules = [[[steps, text]]]

    try:
        get_prompt_lengths_on_ui = sd_models.model_data.sd_model.get_prompt_lengths_on_ui
        assert get_prompt_lengths_on_ui is not None
    except Exception:
        return f"<span class='gr-box gr-text-input'>?/?</span>"

    flat_prompts = reduce(lambda list1, list2: list1+list2, prompt_schedules)
    prompts = [prompt_text for step, prompt_text in flat_prompts]
    token_count, max_length = max([get_prompt_lengths_on_ui(prompt) for prompt in prompts], key=lambda args: args[0])
    return f"<span class='gr-box gr-text-input'>{token_count}/{max_length}</span>"


def update_negative_prompt_token_counter(*args):
    return update_token_counter(*args, is_positive=False)


def setup_progressbar(*args, **kwargs):
    pass


def apply_setting(key, value):
    assert opts is not None, "opts is not initialized"
    if value is None:
        return gr.update()

    if shared.cmd_opts.freeze_settings:
        return gr.update()

    # dont allow model to be swapped when model hash exists in prompt
    if key == "sd_model_checkpoint" and opts.disable_weights_auto_swap:
        return gr.update()

    if key == "sd_model_checkpoint":
        ckpt_info = sd_models.get_closet_checkpoint_match(value)

        if ckpt_info is not None:
            value = ckpt_info.title
        else:
            return gr.update()

    comp_args = opts.data_labels[key].component_args
    if comp_args and isinstance(comp_args, dict) and comp_args.get('visible') is False:
        return

    valtype = type(opts.data_labels[key].default)
    oldval = opts.data.get(key, None)
    opts.data[key] = valtype(value) if valtype != type(None) else value
    if oldval != value and opts.data_labels[key].onchange is not None:
        opts.data_labels[key].onchange()

    opts.save(shared.config_filename)
    return getattr(opts, key)


def create_output_panel(tabname, outdir, toprow=None):
    return ui_common.create_output_panel(tabname, outdir, toprow)


def ordered_ui_categories():
    assert opts is not None, "opts is not initialized"
    user_order = {x.strip(): i * 2 + 1 for i, x in enumerate(opts.ui_reorder_list)}

    for _, category in sorted(enumerate(shared_items.ui_reorder_categories()), key=lambda x: user_order.get(x[1], x[0] * 2 + 0)):
        yield category


def create_override_settings_dropdown(tabname, row):
    dropdown = gr.Dropdown([], label="Override settings", visible=False, elem_id=f"{tabname}_override_settings", multiselect=True)

    dropdown.change(
        fn=lambda x: gr.Dropdown.update(visible=bool(x)),
        inputs=[dropdown],
        outputs=[dropdown],
    )

    return dropdown


def build_function_signature(
        func: Callable,
        script_runner: scripts.ScriptRunner | None = None,
        extras: Optional[list] = None,
        start_from: int = 0):
    signature_args = inspect.getfullargspec(func)[0][start_from:]  # remove the first 'request'
    default_length = len(signature_args)
    default_values = list()
    if script_runner is None:
        extension_scripts = []
    else:
        extension_scripts = script_runner.alwayson_scripts + script_runner.selectable_scripts

    for extension_script in extension_scripts:
        extension_name = extension_script.title()
        if extension_name is None:
            script_name_concat = extension_script.filename
        else:
            script_name_concat = extension_name
        index_start = extension_script.args_from
        index_end = extension_script.args_to
        if index_start is None or index_end is None:
            continue
        if len(signature_args) < default_length + index_end:
            signature_args += ["undefined" for _ in range(default_length + index_end - len(signature_args))]
        if len(default_values) < default_length + index_end:
            default_values += ["" for _ in range(default_length + index_end - len(default_values))]
        if extension_script.api_info is not None:
            for idx, each_arg in enumerate(extension_script.api_info.args):
                arg_elem_id = ""
                if isinstance(script_runner.inputs[index_start + idx], gr.components.Component):
                    if script_runner.inputs[index_start + idx]:
                        arg_elem_id = script_runner.inputs[index_start + idx].elem_id
                    if arg_elem_id is None:
                        arg_elem_id = ""
                each_arg_label = f"{script_name_concat}:{each_arg.label}:{arg_elem_id}"
                signature_args[default_length + index_start + idx] = each_arg_label
                default_values[default_length + index_start + idx] = each_arg.value
    if extras:
        signature_args += extras
        default_values += ["" for _ in range(len(extras))]
    if len(signature_args) > default_length:
        signature_args[default_length] = "Script:script_list:"
    return signature_args, default_values


def return_signature_str_from_list(args: list) -> str:
    return f"signature({json.dumps(args)})"


def get_default_values_from_components(components: list, args: list[str], default_values: list) -> list:
    for idx, label in enumerate(args):
        value = components[idx].value
        if isinstance(components[idx], gr.Dropdown):
            value = value if value else []
        if not default_values[idx]:
            default_values[idx] = value
        if value != default_values[idx]:
            print(f"{label} default value mistmatch: {default_values[idx]} != {value}")
    return default_values


txt2img_signature_args: list = list()
txt2img_suffix_outputs: list = list()
txt2img_params_default_values: list = list()
txt2img_function_index: int | None = None

txt2img_upscale_signature_args: list = list()

img2img_signature_args: list = list()
img2img_suffix_outputs: list = list()
img2img_params_default_values: list = list()
img2img_function_index: int | None = None
interface_function_indicies: dict[str, dict] = dict()


def create_ui():
    assert opts is not None, "opts is not initialized"
    import modules.img2img
    import modules.txt2img

    reload_javascript()

    parameters_copypaste.reset()

    settings = ui_settings.UiSettings()
    settings.register_settings()

    scripts.scripts_current = scripts.scripts_txt2img
    scripts.scripts_txt2img.initialize_scripts(is_img2img=False)

    with gr.Blocks(analytics_enabled=False, head=canvas_head) as txt2img_interface:
        toprow = ui_toprow.Toprow(is_img2img=False, is_compact=shared.opts.compact_prompt_box)
        upgrade_info = gr.JSON(value={}, visible=False)
        txt2img_signature = gr.Textbox(value="", interactive=False, visible=False, elem_id="txt2img_signature")
        txt2img_upscale_signature = gr.Textbox(value="", interactive=False, visible=False, elem_id="txt2img_upscale_signature")
        txt2img_fn_index_component = gr.Textbox(value="", interactive=False, visible=False, elem_id="txt2img_function_index")
        txt2img_model_title = toprow.model_title
        txt2img_prompt_styles = toprow.ui_styles.dropdown
        txt2img_prompt_selections = toprow.ui_styles.selection

        dummy_component = gr.Textbox(visible=False)

        extra_tabs = gr.Tabs(elem_id="txt2img_extra_tabs", elem_classes=["extra-networks"])
        extra_tabs.__enter__()

        with gr.Tab("Generation", id="txt2img_generation") as txt2img_generation_tab, ResizeHandleRow(equal_height=False):
            with ExitStack() as stack:
                if shared.opts.txt2img_settings_accordion:
                    stack.enter_context(gr.Accordion("Open for Settings", open=False))
                stack.enter_context(gr.Column(variant='compact', elem_id="txt2img_settings"))

                scripts.scripts_txt2img.prepare_ui()

                for category in ordered_ui_categories():
                    if category == "prompt":
                        toprow.create_inline_toprow_prompts()

                    elif category == "dimensions":
                        with FormRow():
                            with gr.Column(elem_id="txt2img_column_size", scale=4):
                                width = gr.Slider(minimum=64, maximum=2048, step=8, label="Width", value=512, elem_id="txt2img_width")
                                height = gr.Slider(minimum=64, maximum=2048, step=8, label="Height", value=512, elem_id="txt2img_height")
                                width.change(
                                    None,
                                    inputs=[],
                                    outputs=[width],
                                    _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'width')")
                                height.change(
                                    None,
                                    inputs=[],
                                    outputs=[height],
                                    _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'height')")

                            with gr.Column(elem_id="txt2img_dimensions_row", scale=1, elem_classes="dimensions-tools"):
                                res_switch_btn = ToolButton(value=switch_values_symbol, elem_id="txt2img_res_switch_btn", tooltip="Switch width/height")

                            if opts.dimensions_and_batch_together:
                                with gr.Column(elem_id="txt2img_column_batch"):
                                    batch_count = gr.Slider(minimum=1, maximum=4, step=1, label='Batch count', value=1, elem_id="txt2img_batch_count")
                                    batch_size = gr.Slider(minimum=1, maximum=4, step=1, label='Batch size', value=4, elem_id="txt2img_batch_size")
                                    batch_count.change(
                                        None,
                                        inputs=[],
                                        outputs=[batch_count],
                                        _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'n_iter')")
                                    batch_size.change(
                                        None,
                                        inputs=[],
                                        outputs=[batch_size],
                                        _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'batch_size')")

                    elif category == "cfg":
                        with gr.Row():
                            distilled_cfg_scale = gr.Slider(minimum=0.0, maximum=30.0, step=0.1, label='Distilled CFG Scale', value=3.5, elem_id="txt2img_distilled_cfg_scale")
                            cfg_scale = gr.Slider(minimum=1.0, maximum=30.0, step=0.1, label='CFG Scale', value=7.0, elem_id="txt2img_cfg_scale")
                            cfg_scale.change(lambda x: gr.update(interactive=(x != 1)), inputs=[cfg_scale], outputs=[toprow.negative_prompt], queue=False, show_progress=False)

                    elif category == "checkboxes":
                        with FormRow(elem_classes="checkboxes-row", variant="compact"):
                            restore_faces = gr.Checkbox(label='Restore faces', value=False, visible=len(shared.face_restorers) > 1, elem_id="txt2img_restore_faces")
                            restore_faces.change(
                                None,
                                inputs=[],
                                outputs=[restore_faces],
                                _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'restore_faces')")

                    elif category == "accordions":
                        with gr.Row(elem_id="txt2img_accordions", elem_classes="accordions"):
                            with InputAccordion(False, label="Hires. fix", elem_id="txt2img_hr") as enable_hr:
                                enable_hr.change(
                                    None,
                                    inputs=[],
                                    outputs=[enable_hr],
                                    _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'enable_hr')")
                                with enable_hr.extra():
                                    hr_final_resolution = FormHTML(value="", elem_id="txtimg_hr_finalres", label="Upscaled resolution")

                                with FormRow(elem_id="txt2img_hires_fix_row1", variant="compact"):
                                    hr_upscaler = gr.Dropdown(label="Upscaler", elem_id="txt2img_hr_upscaler", choices=[*shared.latent_upscale_modes, *[x.name for x in shared.sd_upscalers]], value=shared.latent_upscale_default_mode)
                                    hr_second_pass_steps = gr.Slider(minimum=0, maximum=150, step=1, label='Hires steps', value=0, elem_id="txt2img_hires_steps")
                                    denoising_strength = gr.Slider(minimum=0.0, maximum=1.0, step=0.01, label='Denoising strength', value=0.7, elem_id="txt2img_denoising_strength")
                                    hr_second_pass_steps.change(
                                        None,
                                        inputs=[],
                                        outputs=[hr_second_pass_steps],
                                        _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'hr_second_pass_steps')")

                                with FormRow(elem_id="txt2img_hires_fix_row2", variant="compact"):
                                    hr_scale = gr.Slider(minimum=1.0, maximum=4.0, step=0.05, label="Upscale by", value=2.0, elem_id="txt2img_hr_scale")
                                    hr_resize_x = gr.Slider(minimum=0, maximum=2048, step=8, label="Resize width to", value=0, elem_id="txt2img_hr_resize_x")
                                    hr_resize_y = gr.Slider(minimum=0, maximum=2048, step=8, label="Resize height to", value=0, elem_id="txt2img_hr_resize_y")
                                    hr_scale.change(
                                        None,
                                        inputs=[],
                                        outputs=[hr_scale],
                                        _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'hr_scale')")
                                    hr_resize_x.change(
                                        None,
                                        inputs=[],
                                        outputs=[hr_resize_x],
                                        _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'hr_resize_x')")
                                    hr_resize_y.change(
                                        None,
                                        inputs=[],
                                        outputs=[hr_resize_y],
                                        _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'hr_resize_y')")

                                with FormRow(elem_id="txt2img_hires_fix_row_cfg", variant="compact"):
                                    hr_distilled_cfg = gr.Slider(minimum=0.0, maximum=30.0, step=0.1, label="Hires Distilled CFG Scale", value=3.5, elem_id="txt2img_hr_distilled_cfg")
                                    hr_cfg = gr.Slider(minimum=1.0, maximum=30.0, step=0.1, label="Hires CFG Scale", value=7.0, elem_id="txt2img_hr_cfg")
   
                                with FormRow(elem_id="txt2img_hires_fix_row3", variant="compact", visible=shared.opts.hires_fix_show_sampler) as hr_checkpoint_container:
                                    hr_checkpoint_name = gr.Dropdown(label='Hires Checkpoint', elem_id="hr_checkpoint", choices=["Use same checkpoint"], value="Use same checkpoint", scale=2, multiselect=False)

                                    hr_checkpoint_refresh = ToolButton(value=refresh_symbol)

                                    def get_additional_modules():
                                        modules_list = ['Use same choices']
                                        if main_entry.module_list == {}:
                                            _, modules = main_entry.refresh_models()
                                            modules_list += list(modules)
                                        else:
                                            modules_list += list(main_entry.module_list.keys())
                                        return modules_list
                                        
                                    modules_list = get_additional_modules()

                                    def refresh_model_and_modules():
                                        modules_list = get_additional_modules()
                                        return gr.update(choices=["Use same checkpoint"] + modules.sd_models.checkpoint_tiles(use_short=True)), gr.update(choices=modules_list)

                                    hr_additional_modules = gr.Dropdown(label='Hires VAE / Text Encoder', elem_id="hr_vae_te", choices=modules_list, value=["Use same choices"], multiselect=True, scale=3)

                                    hr_checkpoint_refresh.click(fn=refresh_model_and_modules, outputs=[hr_checkpoint_name, hr_additional_modules], show_progress=False)

                                with FormRow(elem_id="txt2img_hires_fix_row3b", variant="compact", visible=shared.opts.hires_fix_show_sampler) as hr_sampler_container:
                                    hr_sampler_name = gr.Dropdown(label='Hires sampling method', elem_id="hr_sampler", choices=["Use same sampler"] + sd_samplers.visible_sampler_names(), value="Use same sampler")
                                    hr_scheduler = gr.Dropdown(label='Hires schedule type', elem_id="hr_scheduler", choices=["Use same scheduler"] + [x.label for x in sd_schedulers.schedulers], value="Use same scheduler")

                                with FormRow(elem_id="txt2img_hires_fix_row4", variant="compact", visible=shared.opts.hires_fix_show_prompts) as hr_prompts_container:
                                    with gr.Column():
                                        hr_prompt = gr.Textbox(label="Hires prompt", elem_id="hires_prompt", show_label=False, lines=3, placeholder="Prompt for hires fix pass.\nLeave empty to use the same prompt as in first pass.", elem_classes=["prompt"])
                                    with gr.Column():
                                        hr_negative_prompt = gr.Textbox(label="Hires negative prompt", elem_id="hires_neg_prompt", show_label=False, lines=3, placeholder="Negative prompt for hires fix pass.\nLeave empty to use the same negative prompt as in first pass.", elem_classes=["prompt"])

                                hr_cfg.change(lambda x: gr.update(interactive=(x != 1)), inputs=[hr_cfg], outputs=[hr_negative_prompt], queue=False, show_progress=False)

                            scripts.scripts_txt2img.setup_ui_for_section(category)

                    elif category == "batch":
                        if not opts.dimensions_and_batch_together:
                            with FormRow(elem_id="txt2img_column_batch"):
                                batch_count = gr.Slider(minimum=1, maximum=4, step=1, label='Batch count', value=1, elem_id="txt2img_batch_count")
                                batch_size = gr.Slider(minimum=1, maximum=4, step=1, label='Batch size', value=1, elem_id="txt2img_batch_size")
                                batch_count.change(
                                    None,
                                    inputs=[],
                                    outputs=[batch_count],
                                    _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'n_iter')")
                                batch_size.change(
                                    None,
                                    inputs=[],
                                    outputs=[batch_size],
                                    _js="monitorThisParam('tab_txt2img', 'modules.txt2img.txt2img', 'batch_size')")

                    elif category == "override_settings":
                        with FormRow(elem_id="txt2img_override_settings_row") as row:
                            override_settings = create_override_settings_dropdown('txt2img', row)

                    elif category == "scripts":
                        with FormGroup(elem_id="txt2img_script_container"):
                            custom_inputs = scripts.scripts_txt2img.setup_ui()

                    if category not in {"accordions"}:
                        scripts.scripts_txt2img.setup_ui_for_section(category)

            hr_resolution_preview_inputs = [enable_hr, width, height, hr_scale, hr_resize_x, hr_resize_y]

            for component in hr_resolution_preview_inputs:
                event = component.release if isinstance(component, gr.Slider) else component.change

                event(
                    fn=calc_resolution_hires,
                    inputs=hr_resolution_preview_inputs,
                    outputs=[hr_final_resolution],
                    show_progress="hidden",
                )
                event(
                    None,
                    _js="onCalcResolutionHires",
                    inputs=hr_resolution_preview_inputs,
                    outputs=[],
                    show_progress="hidden",
                )

            output_panel = create_output_panel("txt2img", Paths(None).outdir_txt2img_samples(), toprow)

            txt2img_inputs = [
                dummy_component,
                toprow.prompt,
                toprow.negative_prompt,
                toprow.ui_styles.dropdown,
                batch_count,
                batch_size,
                cfg_scale,
                distilled_cfg_scale,
                height,
                width,
                enable_hr,
                denoising_strength,
                hr_scale,
                hr_upscaler,
                hr_second_pass_steps,
                hr_resize_x,
                hr_resize_y,
                hr_checkpoint_name,
                hr_additional_modules,
                hr_sampler_name,
                hr_scheduler,
                hr_prompt,
                hr_negative_prompt,
                hr_cfg,
                hr_distilled_cfg,
                restore_faces,
                override_settings,
            ] + custom_inputs + [
                txt2img_model_title,
                toprow.vae_model_title,
                dummy_component,
                dummy_component,
                txt2img_signature
            ]

            txt2img_outputs = [
                output_panel.gallery,
                output_panel.generation_info,
                output_panel.infotext,
                output_panel.html_log,
                upgrade_info,
            ]


            global txt2img_signature_args
            global txt2img_params_default_values
            txt2img_signature_args, txt2img_params_default_values = build_function_signature(
                modules.txt2img.txt2img_create_processing,
                scripts.scripts_txt2img,
                extras=["model_title", "vae_title", "all_style_info", "all_model_info"],
                start_from=1)  # Start from 1 to remove request
            txt2img_args = dict(
                fn=wrap_gradio_gpu_call(
                    modules.txt2img.txt2img, func_name='txt2img', extra_outputs=[None, '', ''], add_monitor_state=True),
                _js="submit",
                inputs=txt2img_inputs,
                outputs=txt2img_outputs,
                show_progress=False,
            )
            global txt2img_suffix_outputs
            txt2img_suffix_outputs = [[], "", "", "", False]
            txt2img_params_default_values = get_default_values_from_components(
                txt2img_args["inputs"], txt2img_signature_args, txt2img_params_default_values)

            toprow.prompt.submit(**txt2img_args)
            toprow.submit.click(**txt2img_args)
            txt2img_gradio_function_index = max(txt2img_interface.fns)
            txt2img_gradio_function = txt2img_interface.fns[txt2img_gradio_function_index]

            global txt2img_upscale_signature_args
            txt2img_upscale_signature_args, _ = build_function_signature(
                modules.txt2img.txt2img_upscale,
                start_from=1, # Start from 1 to remove request
            )
            txt2img_upscale_signature_args += txt2img_signature_args[1:]

            def select_gallery_image(index):
                index = int(index)
                if getattr(shared.opts, 'hires_button_gallery_insert', False):
                    index += 1
                return gr.update(selected_index=index)
            
            txt2img_upscale_inputs = txt2img_inputs[0:1] + [output_panel.gallery, dummy_component, output_panel.generation_info] + txt2img_inputs[1:-1] + [txt2img_upscale_signature]

            output_panel.button_upscale.click(
                fn=wrap_gradio_gpu_call(
                    modules.txt2img.txt2img_upscale,
                    func_name='txt2img_upscale',
                    extra_outputs=[None, '', ''],
                    add_monitor_state=True,
                ),
                _js="submit_txt2img_upscale",
                inputs=txt2img_upscale_inputs,
                outputs=txt2img_outputs,
                show_progress=False,
            ).then(fn=select_gallery_image, js="selected_gallery_index", inputs=[dummy_component], outputs=[output_panel.gallery])

            upgrade_info.change(None, [upgrade_info], None, _js="upgradeCheck")
            res_switch_btn.click(fn=None, _js="function(){switchWidthHeight('txt2img')}", inputs=None, outputs=None, show_progress=False)

            toprow.restore_progress_button.click(
                fn=progress.restore_progress,
                _js="restoreProgressTxt2img",
                inputs=[dummy_component],
                outputs=[
                    output_panel.gallery,
                    output_panel.generation_info,
                    output_panel.infotext,
                    output_panel.html_log,
                ],
                show_progress=False,
            )

            txt2img_paste_fields = [
                PasteField(toprow.prompt, "Prompt", api="prompt"),
                PasteField(toprow.negative_prompt, "Negative prompt", api="negative_prompt"),
                PasteField(cfg_scale, "CFG scale", api="cfg_scale"),
                PasteField(distilled_cfg_scale, "Distilled CFG Scale", api="distilled_cfg_scale"),
                PasteField(width, "Size-1", api="width"),
                PasteField(height, "Size-2", api="height"),
                PasteField(batch_size, "Batch size", api="batch_size"),
                PasteField(toprow.ui_styles.dropdown, lambda d: d["Styles array"] if isinstance(d.get("Styles array"), list) else gr.update(), api="styles"),
                PasteField(denoising_strength, "Denoising strength", api="denoising_strength"),
                PasteField(enable_hr, lambda d: "Denoising strength" in d and ("Hires upscale" in d or "Hires upscaler" in d or "Hires resize-1" in d), api="enable_hr"),
                PasteField(hr_scale, "Hires upscale", api="hr_scale"),
                PasteField(hr_upscaler, "Hires upscaler", api="hr_upscaler"),
                PasteField(hr_second_pass_steps, "Hires steps", api="hr_second_pass_steps"),
                PasteField(hr_resize_x, "Hires resize-1", api="hr_resize_x"),
                PasteField(hr_resize_y, "Hires resize-2", api="hr_resize_y"),
                PasteField(hr_checkpoint_name, "Hires checkpoint", api="hr_checkpoint_name"),
                PasteField(hr_additional_modules, "Hires VAE/TE", api="hr_additional_modules"),
                PasteField(hr_sampler_name, sd_samplers.get_hr_sampler_from_infotext, api="hr_sampler_name"),
                PasteField(hr_scheduler, sd_samplers.get_hr_scheduler_from_infotext, api="hr_scheduler"),
                PasteField(hr_sampler_container, lambda d: gr.update(visible=True) if d.get("Hires sampler", "Use same sampler") != "Use same sampler" or d.get("Hires checkpoint", "Use same checkpoint") != "Use same checkpoint" or d.get("Hires schedule type", "Use same scheduler") != "Use same scheduler" else gr.update()),
                PasteField(hr_prompt, "Hires prompt", api="hr_prompt"),
                PasteField(hr_negative_prompt, "Hires negative prompt", api="hr_negative_prompt"),
                PasteField(hr_cfg, "Hires CFG Scale", api="hr_cfg"),
                PasteField(hr_distilled_cfg, "Hires Distilled CFG Scale", api="hr_distilled_cfg"),
                PasteField(hr_prompts_container, lambda d: gr.update(visible=True) if d.get("Hires prompt", "") != "" or d.get("Hires negative prompt", "") != "" else gr.update()),
                PasteField(restore_faces, "Face restoration", api="restore_faces"),
                *scripts.scripts_txt2img.infotext_fields
            ]
            parameters_copypaste.add_paste_fields("txt2img", None, txt2img_paste_fields, override_settings)
            parameters_copypaste.register_paste_params_button(parameters_copypaste.ParamBinding(
                paste_button=toprow.paste, tabname="txt2img", source_text_component=toprow.prompt, source_image_component=None,
            ))

            steps = scripts.scripts_txt2img.script('Sampler').steps

            toprow.ui_styles.dropdown.change(fn=wrap_queued_call(update_token_counter), inputs=[toprow.prompt, steps, toprow.ui_styles.dropdown], outputs=[toprow.token_counter])
            toprow.ui_styles.dropdown.change(fn=wrap_queued_call(update_negative_prompt_token_counter), inputs=[toprow.negative_prompt, steps, toprow.ui_styles.dropdown], outputs=[toprow.negative_token_counter])
            toprow.token_button.click(
                fn=submit_to_gpu_worker_with_request(update_token_counter, timeout=60 * 30),
                inputs=[toprow.prompt, steps, toprow.ui_styles.dropdown],
                outputs=[toprow.token_counter]
            )
            toprow.negative_token_button.click(
                fn=submit_to_gpu_worker_with_request(update_negative_prompt_token_counter, timeout=60 * 30),
                inputs=[toprow.negative_prompt, steps, toprow.ui_styles.dropdown],
                outputs=[toprow.negative_token_counter]
            )

        extra_tabs.__exit__()

    scripts.scripts_current = scripts.scripts_img2img
    scripts.scripts_img2img.initialize_scripts(is_img2img=True)

    with gr.Blocks(analytics_enabled=False, head=canvas_head) as img2img_interface:
        toprow = ui_toprow.Toprow(is_img2img=True, is_compact=shared.opts.compact_prompt_box)
        img2img_signature = gr.Textbox(value="", interactive=False, visible=False, elem_id="img2img_signature")
        img2img_fn_index_component = gr.Textbox(value="", interactive=False, visible=False, elem_id="img2img_function_index")
        img2img_model_title = toprow.model_title
        img2img_prompt_styles = toprow.ui_styles.dropdown
        img2img_prompt_selections = toprow.ui_styles.selection


        extra_tabs = gr.Tabs(elem_id="img2img_extra_tabs", elem_classes=["extra-networks"])
        extra_tabs.__enter__()

        with gr.Tab("Generation", id="img2img_generation") as img2img_generation_tab, ResizeHandleRow(equal_height=False):
            with ExitStack() as stack:
                if shared.opts.img2img_settings_accordion:
                    stack.enter_context(gr.Accordion("Open for Settings", open=False))
                stack.enter_context(gr.Column(variant='compact', elem_id="img2img_settings"))

                copy_image_buttons = []
                copy_image_destinations = {}

                def add_copy_image_controls(tab_name, elem):
                    with gr.Row(variant="compact", elem_id=f"img2img_copy_to_{tab_name}"):
                        for title, name in zip(['to img2img', 'to sketch', 'to inpaint', 'to inpaint sketch'], ['img2img', 'sketch', 'inpaint', 'inpaint_sketch']):
                            if name == tab_name:
                                gr.Button(title, interactive=False)
                                copy_image_destinations[name] = elem
                                continue

                            button = gr.Button(title)
                            copy_image_buttons.append((button, name, elem))

                scripts.scripts_img2img.prepare_ui()

                for category in ordered_ui_categories():
                    if category == "prompt":
                        toprow.create_inline_toprow_prompts()

                    if category == "image":
                        with gr.Tabs(elem_id="mode_img2img"):
                            img2img_selected_tab = gr.Number(value=0, visible=False)

                            with gr.TabItem('img2img', id='img2img', elem_id="img2img_img2img_tab") as tab_img2img:
                                init_img = ForgeCanvas(elem_id="img2img_image", height=512, no_scribbles=True)
                                add_copy_image_controls('img2img', init_img)

                            with gr.TabItem('Sketch', id='img2img_sketch', elem_id="img2img_img2img_sketch_tab") as tab_sketch:
                                sketch = ForgeCanvas(elem_id="img2img_sketch", height=512, scribble_color=opts.img2img_sketch_default_brush_color)
                                add_copy_image_controls('sketch', sketch)

                            with gr.TabItem('Inpaint', id='inpaint', elem_id="img2img_inpaint_tab") as tab_inpaint:
                                init_img_with_mask = ForgeCanvas(elem_id="img2maskimg", height=512, contrast_scribbles=opts.img2img_inpaint_mask_high_contrast, scribble_color=opts.img2img_inpaint_mask_brush_color, scribble_color_fixed=True, scribble_alpha_fixed=True, scribble_softness_fixed=True)
                                add_copy_image_controls('inpaint', init_img_with_mask)

                            with gr.TabItem('Inpaint sketch', id='inpaint_sketch', elem_id="img2img_inpaint_sketch_tab") as tab_inpaint_color:
                                inpaint_color_sketch = ForgeCanvas(elem_id="inpaint_sketch", height=512, scribble_color=opts.img2img_inpaint_sketch_default_brush_color)
                                add_copy_image_controls('inpaint_sketch', inpaint_color_sketch)

                            with gr.TabItem('Inpaint upload', id='inpaint_upload', elem_id="img2img_inpaint_upload_tab") as tab_inpaint_upload:
                                init_img_inpaint = gr.Image(label="Image for img2img", show_label=False, source="upload", interactive=True, type="pil", elem_id="img_inpaint_base")
                                init_mask_inpaint = gr.Image(label="Mask", source="upload", interactive=True, type="pil", image_mode="RGBA", elem_id="img_inpaint_mask")

                            with gr.TabItem('Batch', id='batch', elem_id="img2img_batch_tab") as tab_batch:
                                with gr.Tabs(elem_id="img2img_batch_source"):
                                    img2img_batch_source_type = gr.Textbox(visible=False, value="upload")
                                    with gr.TabItem('Upload', id='batch_upload', elem_id="img2img_batch_upload_tab") as tab_batch_upload:
                                        img2img_batch_upload = gr.Files(label="Files", interactive=True, elem_id="img2img_batch_upload")
                                    with gr.TabItem('From directory', id='batch_from_dir', elem_id="img2img_batch_from_dir_tab") as tab_batch_from_dir:
                                        hidden = '<br>Disabled when launched with --hide-ui-dir-config.' if shared.cmd_opts.hide_ui_dir_config else ''
                                        gr.HTML(
                                            "<p style='padding-bottom: 1em;' class=\"text-gray-500\">Process images in a directory on the same machine where the server is running." +
                                            "<br>Use an empty output directory to save pictures normally instead of writing to the output directory." +
                                            f"<br>Add inpaint batch mask directory to enable inpaint batch processing."
                                            f"{hidden}</p>"
                                        )
                                        img2img_batch_input_dir = gr.Textbox(label="Input directory", **shared.hide_dirs, elem_id="img2img_batch_input_dir")
                                        img2img_batch_output_dir = gr.Textbox(label="Output directory", **shared.hide_dirs, elem_id="img2img_batch_output_dir")
                                        img2img_batch_inpaint_mask_dir = gr.Textbox(label="Inpaint batch mask directory (required for inpaint batch processing only)", **shared.hide_dirs, elem_id="img2img_batch_inpaint_mask_dir")
                                tab_batch_upload.select(fn=lambda: "upload", inputs=[], outputs=[img2img_batch_source_type])
                                tab_batch_from_dir.select(fn=lambda: "from dir", inputs=[], outputs=[img2img_batch_source_type])
                                with gr.Accordion("PNG info", open=False):
                                    img2img_batch_use_png_info = gr.Checkbox(label="Append png info to prompts", elem_id="img2img_batch_use_png_info")
                                    img2img_batch_png_info_dir = gr.Textbox(label="PNG info directory", **shared.hide_dirs, placeholder="Leave empty to use input directory", elem_id="img2img_batch_png_info_dir")
                                    img2img_batch_png_info_props = gr.CheckboxGroup(["Prompt", "Negative prompt", "Seed", "CFG scale", "Sampler", "Steps", "Model hash"], label="Parameters to take from png info", info="Prompts from png info will be appended to prompts set in ui.")

                            img2img_tabs = [tab_img2img, tab_sketch, tab_inpaint, tab_inpaint_color, tab_inpaint_upload, tab_batch]

                            for i, tab in enumerate(img2img_tabs):
                                tab.select(fn=lambda tabnum=i: tabnum, inputs=[], outputs=[img2img_selected_tab])

                        def copyCanvas_img2img (background, foreground, source):
                            if source == 1 or source == 3: #   1 is sketch, 3 is Inpaint sketch
                                bg = Image.alpha_composite(background, foreground)
                                return bg, None
                            return background, None

                        for button, name, elem in copy_image_buttons:
                            button.click(
                                fn=copyCanvas_img2img,
                                inputs=[elem.background, elem.foreground, img2img_selected_tab],
                                outputs=[copy_image_destinations[name].background, copy_image_destinations[name].foreground],
                            )
                            button.click(
                                fn=None,
                                _js=f"switch_to_{name.replace(' ', '_')}",
                                inputs=[],
                                outputs=[],
                            )

                        with FormRow():
                            resize_mode = gr.Radio(label="Resize mode", elem_id="resize_mode", choices=["Just resize", "Crop and resize", "Resize and fill", "Just resize (latent upscale)"], type="index", value="Just resize")

                    elif category == "dimensions":
                        with FormRow():
                            with gr.Column(elem_id="img2img_column_size", scale=4):
                                selected_scale_tab = gr.Number(value=0, visible=False)

                                with gr.Tabs(elem_id="img2img_tabs_resize"):
                                    with gr.Tab(label="Resize to", id="to", elem_id="img2img_tab_resize_to") as tab_scale_to:
                                        with FormRow():
                                            with gr.Column(elem_id="img2img_column_size", scale=4):
                                                width = gr.Slider(minimum=64, maximum=2048, step=8, label="Width", value=512, elem_id="img2img_width")
                                                height = gr.Slider(minimum=64, maximum=2048, step=8, label="Height", value=512, elem_id="img2img_height")
                                                width.change(
                                                    None,
                                                    inputs=[],
                                                    outputs=[width, height],
                                                    _js="monitorThisParam('tab_img2img', 'modules.img2img.img2img', ['width', 'height'])")
                                                height.change(
                                                    None,
                                                    inputs=[],
                                                    outputs=[width, height],
                                                    _js="monitorThisParam('tab_img2img', 'modules.img2img.img2img', ['width', 'height'])")
                                            with gr.Column(elem_id="img2img_dimensions_row", scale=1, elem_classes="dimensions-tools"):
                                                res_switch_btn = ToolButton(value=switch_values_symbol, elem_id="img2img_res_switch_btn", tooltip="Switch width/height")
                                                detect_image_size_btn = ToolButton(value=detect_image_size_symbol, elem_id="img2img_detect_image_size_btn", tooltip="Auto detect size from img2img")

                                    with gr.Tab(label="Resize by", id="by", elem_id="img2img_tab_resize_by") as tab_scale_by:
                                        scale_by = gr.Slider(minimum=0.05, maximum=4.0, step=0.01, label="Scale", value=1.0, elem_id="img2img_scale")
                                        scale_by.change(
                                            None,
                                            inputs=[],
                                            outputs=[scale_by],
                                            _js="""monitorThisParam(
                                                    'tab_img2img',
                                                    'modules.img2img.img2img',
                                                    ['width', 'height'],
                                                    extractor = (scale_by) => {
                                                        let [imgWidth, imgHeight, scaleBy] = currentImg2imgSourceResolution(512, 512, scale_by);
                                                        return [Math.floor(imgWidth * scale_by), Math.floor(imgHeight * scale_by)];
                                                    })"""
                                        )

                                        with FormRow():
                                            scale_by_html = FormHTML(resize_from_to_html(0, 0, 0.0), elem_id="img2img_scale_resolution_preview")
                                            gr.Slider(label="Unused", elem_id="img2img_unused_scale_by_slider")
                                            button_update_resize_to = gr.Button(visible=False, elem_id="img2img_update_resize_to")

                                    on_change_args = dict(
                                        fn=resize_from_to_html,
                                        _js="currentImg2imgSourceResolution",
                                        inputs=[dummy_component, dummy_component, scale_by],
                                        outputs=scale_by_html,
                                        show_progress=False,
                                    )

                                    scale_by.change(**on_change_args)
                                    button_update_resize_to.click(**on_change_args)

                                    def updateWH (img, w, h):
                                        if img and shared.opts.img2img_autosize == True:
                                            return img.size[0], img.size[1]
                                        else:
                                            return w, h

                                    img_sources = [init_img.background, sketch.background, init_img_with_mask.background, inpaint_color_sketch.background, init_img_inpaint]
                                    for i in img_sources:
                                        i.change(fn=updateWH, inputs=[i, width, height], outputs=[width, height], show_progress='hidden')
                                        i.change(**on_change_args)

                            tab_scale_to.select(fn=lambda: 0, inputs=[], outputs=[selected_scale_tab])
                            tab_scale_by.select(fn=lambda: 1, inputs=[], outputs=[selected_scale_tab])

                            if opts.dimensions_and_batch_together:
                                with gr.Column(elem_id="img2img_column_batch"):
                                    batch_count = gr.Slider(minimum=1, maximum=4, step=1, label='Batch count', value=1, elem_id="img2img_batch_count")
                                    batch_size = gr.Slider(minimum=1, maximum=4, step=1, label='Batch size', value=1, elem_id="img2img_batch_size")
                                    batch_count.change(
                                        None,
                                        inputs=[],
                                        outputs=[batch_count],
                                        _js="monitorThisParam('tab_img2img', 'modules.img2img.img2img', 'n_iter')")
                                    batch_size.change(
                                        None,
                                        inputs=[],
                                        outputs=[batch_size],
                                        _js="monitorThisParam('tab_img2img', 'modules.img2img.img2img', 'batch_size')")

                    elif category == "denoising":
                        denoising_strength = gr.Slider(minimum=0.0, maximum=1.0, step=0.01, label='Denoising strength', value=0.75, elem_id="img2img_denoising_strength")

                    elif category == "cfg":
                        with gr.Row():
                            distilled_cfg_scale = gr.Slider(minimum=0.0, maximum=30.0, step=0.1, label='Distilled CFG Scale', value=3.5, elem_id="img2img_distilled_cfg_scale")
                            cfg_scale = gr.Slider(minimum=1.0, maximum=30.0, step=0.1, label='CFG Scale', value=7.0, elem_id="img2img_cfg_scale")
                            image_cfg_scale = gr.Slider(minimum=0, maximum=3.0, step=0.05, label='Image CFG Scale', value=1.5, elem_id="img2img_image_cfg_scale", visible=False)
                            cfg_scale.change(lambda x: gr.update(interactive=(x != 1)), inputs=[cfg_scale], outputs=[toprow.negative_prompt], queue=False, show_progress=False)

                    elif category == "checkboxes":
                        with FormRow(elem_classes="checkboxes-row", variant="compact"):
                            restore_faces = gr.Checkbox(label='Restore faces', value=False, visible=len(shared.face_restorers) > 1, elem_id="img2img_restore_faces")
                            restore_faces.change(
                                None,
                                inputs=[],
                                outputs=[restore_faces],
                                _js="monitorThisParam('tab_img2img', 'modules.img2img.img2img', 'restore_faces')")

                    elif category == "accordions":
                        with gr.Row(elem_id="img2img_accordions", elem_classes="accordions"):
                            scripts.scripts_img2img.setup_ui_for_section(category)

                    elif category == "batch":
                        if not opts.dimensions_and_batch_together:
                            with FormRow(elem_id="img2img_column_batch"):
                                batch_count = gr.Slider(minimum=1, maximum=4, step=1, label='Batch count', value=1, elem_id="img2img_batch_count")
                                batch_size = gr.Slider(minimum=1, maximum=4, step=1, label='Batch size', value=4, elem_id="img2img_batch_size")
                                batch_count.change(
                                    None,
                                    inputs=[],
                                    outputs=[batch_count],
                                    _js="monitorThisParam('tab_img2img', 'modules.img2img.img2img', 'n_iter')")
                                batch_size.change(
                                    None,
                                    inputs=[],
                                    outputs=[batch_size],
                                    _js="monitorThisParam('tab_img2img', 'modules.img2img.img2img', 'batch_size')")

                    elif category == "override_settings":
                        with FormRow(elem_id="img2img_override_settings_row") as row:
                            override_settings = create_override_settings_dropdown('img2img', row)

                    elif category == "scripts":
                        with FormGroup(elem_id="img2img_script_container"):
                            custom_inputs = scripts.scripts_img2img.setup_ui()

                    elif category == "inpaint":
                        with FormGroup(elem_id="inpaint_controls", visible=False) as inpaint_controls:
                            with FormRow():
                                mask_blur = gr.Slider(label='Mask blur', minimum=0, maximum=64, step=1, value=4, elem_id="img2img_mask_blur")
                                mask_alpha = gr.Slider(label="Mask transparency", visible=False, elem_id="img2img_mask_alpha")

                            with FormRow():
                                inpainting_mask_invert = gr.Radio(label='Mask mode', choices=['Inpaint masked', 'Inpaint not masked'], value='Inpaint masked', type="index", elem_id="img2img_mask_mode")

                            with FormRow():
                                inpainting_fill = gr.Radio(label='Masked content', choices=['fill', 'original', 'latent noise', 'latent nothing'], value='original', type="index", elem_id="img2img_inpainting_fill")

                            with FormRow():
                                with gr.Column():
                                    inpaint_full_res = gr.Radio(label="Inpaint area", choices=["Whole picture", "Only masked"], type="index", value="Whole picture", elem_id="img2img_inpaint_full_res")

                                with gr.Column(scale=4):
                                    inpaint_full_res_padding = gr.Slider(label='Only masked padding, pixels', minimum=0, maximum=256, step=4, value=32, elem_id="img2img_inpaint_full_res_padding")

                    if category not in {"accordions"}:
                        scripts.scripts_img2img.setup_ui_for_section(category)

            def select_img2img_tab(tab):
                return gr.update(visible=tab in [2, 3, 4]), gr.update(visible=tab == 3),

            for i, elem in enumerate(img2img_tabs):
                elem.select(
                    fn=lambda tab=i: select_img2img_tab(tab),
                    inputs=[],
                    outputs=[inpaint_controls, mask_alpha],
                )

            output_panel = create_output_panel("img2img", Paths(None).outdir_img2img_samples(), toprow)

            toprow.prompt_img.change(
                fn=modules.images.image_data,
                inputs=[
                    toprow.prompt_img
                ],
                outputs=[
                    toprow.prompt,
                    toprow.prompt_img
                ],
                show_progress=False,
            )

            global img2img_signature_args
            global img2img_params_default_values
            img2img_signature_args, img2img_params_default_values = build_function_signature(
                modules.img2img.img2img,
                modules.scripts.scripts_img2img,
                extras=["model_title", "vae_title", "all_style_info", "all_model_info"],
                start_from=1)  # Start from 1 to remove request

            submit_img2img_inputs = [
                dummy_component,
                img2img_selected_tab,
                toprow.prompt,
                toprow.negative_prompt,
                toprow.ui_styles.dropdown,
                init_img.background,
                sketch.background,
                sketch.foreground,
                init_img_with_mask.background,
                init_img_with_mask.foreground,
                inpaint_color_sketch.background,
                inpaint_color_sketch.foreground,
                init_img_inpaint,
                init_mask_inpaint,
                mask_blur,
                mask_alpha,
                inpainting_fill,
                batch_count,
                batch_size,
                cfg_scale,
                distilled_cfg_scale,
                image_cfg_scale,
                denoising_strength,
                selected_scale_tab,
                height,
                width,
                scale_by,
                resize_mode,
                inpaint_full_res,
                inpaint_full_res_padding,
                inpainting_mask_invert,
                img2img_batch_input_dir,
                img2img_batch_output_dir,
                img2img_batch_inpaint_mask_dir,
                restore_faces,
                override_settings,
                img2img_batch_use_png_info,
                img2img_batch_png_info_props,
                img2img_batch_png_info_dir,
                img2img_batch_source_type,
                img2img_batch_upload,
            ] + custom_inputs + [
                img2img_model_title,
                toprow.vae_model_title,
                dummy_component,
                dummy_component,
                img2img_signature,
            ]

            img2img_args = dict(
                fn=wrap_gradio_gpu_call(
                    modules.img2img.img2img, func_name='img2img', extra_outputs=[None, '', ''], add_monitor_state=True),
                _js="submit_img2img",
                inputs=submit_img2img_inputs,
                outputs=[
                    output_panel.gallery,
                    output_panel.generation_info,
                    output_panel.infotext,
                    output_panel.html_log,
                    upgrade_info,
                ],
                show_progress=False,
            )
            global img2img_suffix_outputs
            img2img_suffix_outputs = [[], "", "", "", False]

            interrogate_args = dict(
                _js="get_img2img_tab_index",
                inputs=[
                    dummy_component,
                    dummy_component,
                    img2img_batch_input_dir,
                    img2img_batch_output_dir,
                    init_img.background,
                    sketch.background,
                    init_img_with_mask.background,
                    inpaint_color_sketch.background,
                    init_img_inpaint,
                ],
                outputs=[toprow.prompt, dummy_component, dummy_component, upgrade_info],
            )
            img2img_params_default_values = get_default_values_from_components(
                img2img_args["inputs"], img2img_signature_args, img2img_params_default_values)

            toprow.prompt.submit(**img2img_args)
            toprow.submit.click(**img2img_args)
            img2img_gradio_function_index = max(txt2img_interface.fns)
            img2img_gradio_function = img2img_interface.fns[img2img_gradio_function_index]

            res_switch_btn.click(lambda w, h: (h, w), inputs=[width, height], outputs=[width, height], show_progress=False)

            detect_image_size_btn.click(
                fn=lambda w, h: (w or gr.update(), h or gr.update()),
                _js="currentImg2imgSourceResolution",
                inputs=[dummy_component, dummy_component],
                outputs=[width, height],
                show_progress=False,
            )

            toprow.restore_progress_button.click(
                fn=progress.restore_progress,
                _js="restoreProgressImg2img",
                inputs=[dummy_component],
                outputs=[
                    output_panel.gallery,
                    output_panel.generation_info,
                    output_panel.infotext,
                    output_panel.html_log,
                ],
                show_progress=False,
            )

            assert toprow.button_interrogate is not None, "button_interrogate has not yet been created"
            toprow.button_interrogate.click(
                fn=wrap_gradio_gpu_call(
                    interrogate_processor_getter(interrogate),
                    extra_outputs=["", None],
                    add_monitor_state=True
                ),
                **interrogate_args,
            )

            assert toprow.button_deepbooru is not None, "button_deepbooru has not yet been created"
            toprow.button_deepbooru.click(
                fn=wrap_gradio_gpu_call(
                    interrogate_processor_getter(interrogate_deepbooru),
                    extra_outputs=["", None],
                    add_monitor_state=True
                ),
                **interrogate_args,
            )

            steps = scripts.scripts_img2img.script('Sampler').steps

            toprow.ui_styles.dropdown.change(fn=wrap_queued_call(update_token_counter), inputs=[toprow.prompt, steps, toprow.ui_styles.dropdown], outputs=[toprow.token_counter])
            toprow.ui_styles.dropdown.change(fn=wrap_queued_call(update_negative_prompt_token_counter), inputs=[toprow.negative_prompt, steps, toprow.ui_styles.dropdown], outputs=[toprow.negative_token_counter])
            toprow.token_button.click(
                fn=submit_to_gpu_worker_with_request(update_token_counter, timeout=60 * 30),
                inputs=[toprow.prompt, steps, toprow.ui_styles.dropdown],
                outputs=[toprow.token_counter]
            )
            toprow.negative_token_button.click(
                fn=submit_to_gpu_worker_with_request(update_token_counter, timeout=60 * 30),
                inputs=[toprow.negative_prompt, steps, toprow.ui_styles.dropdown],
                outputs=[toprow.negative_token_counter]
            )

            img2img_paste_fields = [
                (toprow.prompt, "Prompt"),
                (toprow.negative_prompt, "Negative prompt"),
                (cfg_scale, "CFG scale"),
                (distilled_cfg_scale, "Distilled CFG Scale"),
                (image_cfg_scale, "Image CFG scale"),
                (width, "Size-1"),
                (height, "Size-2"),
                (batch_size, "Batch size"),
                (toprow.ui_styles.dropdown, lambda d: d["Styles array"] if isinstance(d.get("Styles array"), list) else gr.update()),
                (denoising_strength, "Denoising strength"),
                (mask_blur, "Mask blur"),
                (inpainting_mask_invert, 'Mask mode'),
                (inpainting_fill, 'Masked content'),
                (inpaint_full_res, 'Inpaint area'),
                (inpaint_full_res_padding, 'Masked area padding'),
                (restore_faces, "Face restoration"),
                *scripts.scripts_img2img.infotext_fields
            ]
            parameters_copypaste.add_paste_fields("img2img", init_img.background, img2img_paste_fields, override_settings)
            parameters_copypaste.add_paste_fields("inpaint", init_img_with_mask.background, img2img_paste_fields, override_settings)
            parameters_copypaste.register_paste_params_button(parameters_copypaste.ParamBinding(
                paste_button=toprow.paste, tabname="img2img", source_text_component=toprow.prompt, source_image_component=None,
            ))

        extra_tabs.__exit__()

    with gr.Blocks(analytics_enabled=False, head=canvas_head) as space_interface:
        forge_space.main_entry()

    scripts.scripts_current = None

    with gr.Blocks(analytics_enabled=False, head=canvas_head) as extras_interface:
        ui_postprocessing.create_ui()

    with gr.Blocks(analytics_enabled=False, head=canvas_head) as pnginfo_interface:
        with ResizeHandleRow(equal_height=False):
            with gr.Column(variant='panel'):
                image = gr.Image(elem_id="pnginfo_image", label="Source", source="upload", interactive=True, type="pil")

            with gr.Column(variant='panel'):
                html = gr.HTML()
                generation_info = gr.Textbox(visible=False, elem_id="pnginfo_generation_info")
                html2 = gr.HTML()
                with gr.Row():
                    buttons = parameters_copypaste.create_buttons(["txt2img", "img2img", "inpaint", "extras"])

                for tabname, button in buttons.items():
                    parameters_copypaste.register_paste_params_button(parameters_copypaste.ParamBinding(
                        paste_button=button, tabname=tabname, source_text_component=generation_info, source_image_component=image,
                    ))

        image.change(
            fn=wrap_gradio_call_no_job(modules.extras.run_pnginfo),
            inputs=[image],
            outputs=[html, generation_info, html2],
        )

    # modelmerger_ui = ui_checkpoint_merger.UiCheckpointMerger()

    loadsave = ui_loadsave.UiLoadsave(cmd_opts.ui_config_file)
    ui_settings_from_file = loadsave.ui_settings.copy()

    settings.create_ui(loadsave, dummy_component)

    interfaces = [
        (txt2img_interface, "Txt2img", "txt2img"),
        (img2img_interface, "Img2img", "img2img"),
        (space_interface, "Spaces", "space"),
        (extras_interface, "Extras", "extras"),
        (pnginfo_interface, "PNG Info", "pnginfo"),
        # (modelmerger_ui.blocks, "Checkpoint Merger", "modelmerger"),
    ]

    interfaces += script_callbacks.ui_tabs_callback()
    interfaces += [(settings.interface, "Settings", "settings")]

    extensions_interface = ui_extensions.create_ui()
    interfaces += [(extensions_interface, "Extensions", "extensions")]

    shared.tab_names = []
    for _interface, label, _ifid in interfaces:
        shared.tab_names.append(label)

    with gr.Blocks(theme=shared.gradio_theme, analytics_enabled=False, head=canvas_head) as demo:
        with gr.Row():
             with gr.Column(elem_id="user-setting", min_width=500, scale=2):
                gr.HTML(
                    value="<div class='user-content'>"
                            "<div class='right-content'>"
                            "<div id='one_click_boost_button' class='one_click_boost_button_area' style='display: none'></div>"
                            "<div id='discord' class='discord-icon'>"
                              "<a class='discord-link' style='height: 100%; align-items: center; display: flex;' title='Join Discord' href='https://discord.gg/QfBbBYqQ7z'>"
                                "<img src='/public/image/discord.png' />"
                              "</a>"
                            "</div>"
                            "<div style='gap: 5px; display: flex; flex-direction: column; padding-bottom: 10px;'>"
                              "<div style='display: flex;'>"
                                "<div id='sign' title='' class='upgrade-content' style='display: none'><a><img /><span></span></a></div>"
                                "<div id='package' title='Credits Package' class='upgrade-content' style='display: none'><a><img src='/public/image/package.png' /><span></span></a></div>"
                                "<div id='upgrade' title='Unlock more credits' class='upgrade-content' style='display: none'><a href='/app/pricing-table'><img src='/public/image/lightning.png'/><span>Upgrade</span></a></div>"
                                "<div id='affiliate' title='Affiliate' class='upgrade-content' style='display: flex'><a href='/affiliate/everyone' target='_blank'><span class='mdi mdi-currency-usd' style='font-size=20px'></span><span>Affiliate</span></a></div>"
                              "</div>"
                              "<a id='user-credits-app' href='/app/account/'>"
                              "</a>"
                            "</div>"
                          "</div>"
                          "<div style='display: none;justify-content: flex-end;' id='user_info'></div>",
                    show_label=False)
        with gr.Row(elem_id="topbar"):
            with gr.Column(scale=6, min_width=850):
                with gr.Row(elem_id="quicksettings"):
                    main_entry.make_checkpoint_manager_ui()
                    # Quicksetting is not used here, but keep it so the program will not throw any error
                    for i, k, item in sorted(settings.quicksettings_list, key=lambda x: settings.quicksettings_names.get(x[1], x[0])):
                        component = create_setting_component(k, is_quicksettings=True, visible=False, interactive=False)
                        settings.component_dict[k] = component

                    # This is the real place to set sd checkpoint
                    sd_checkpoint_options = shared.opts.data_labels["sd_model_checkpoint"]

                    sd_model_selection = sd_checkpoint_options.component(
                        label=sd_checkpoint_options.label,
                        elem_id="sd_model_checkpoint_dropdown",
                        elem_classes=["quicksettings"],
                        visible=True,
                        choices=[],
                        value=None,
                    )
                    create_refresh_button(
                        sd_model_selection,
                        None,
                        None,
                        #sd_checkpoint_options.component_args,
                        # filter_outrefiners,
                        "refresh_sd_model_checkpoint_dropdown",
                        _js="updateCheckpointDropdown"
                    )

                    gr.HTML(elem_id="gallery")
                    gr.Button(elem_id="gallery_change_checkpoint", visible=False).click(
                        fn=None,
                        _js="updateCheckpoint",
                        inputs=[],
                        outputs=[sd_model_selection],
                    )

                    def get_model_title_from_params(request: gr.Request, params):
                        # sd_models.checkpoint_tiles() is guaranteed to return at least one model title
                        checkpoint_tiles = sd_models.checkpoint_tiles(request)
                        if not checkpoint_tiles:
                            checkpoint_tiles = [shared.opts.data["sd_model_checkpoint"], ]

                        if "Model hash" not in params and "Model" not in params:
                            return checkpoint_tiles[0]
                        if "Model hash" in params:
                            ckpt_info = sd_models.get_closet_checkpoint_match(params["Model hash"])

                            if ckpt_info is not None:
                                return ckpt_info.title

                        if "Model" in params:
                            ckpt_info = sd_models.get_closet_checkpoint_match(params["Model"])

                            if ckpt_info is not None:
                                return ckpt_info.title

                        return checkpoint_tiles[0]

                    def _get_gallery_model_from_params(params: dict) -> dict:
                        all_model_info: AllModelInfo = params[MODEL_INFO_KEY]
                        sha256 = params.get("Model hash")
                        if not sha256:
                            return gr.update(value=None)

                        model_info = all_model_info.get_checkpoint_by_hash(sha256)
                        if model_info is None:
                            return gr.update(value=None)

                        return gr.update(value=model_info.title)

                    txt2img_paste_fields.append((sd_model_selection, _get_gallery_model_from_params))
                    img2img_paste_fields.append((sd_model_selection, _get_gallery_model_from_params))

                    sd_model_selection.change(
                        _js='on_sd_model_selection_updated',
                        fn=None,
                        inputs=sd_model_selection,
                        outputs=[txt2img_model_title, img2img_model_title]
                    )

                    sd_model_selection.select(
                        _js='on_sd_model_selection_updated',
                        fn=None,
                        inputs=sd_model_selection,
                        outputs=[txt2img_model_title, img2img_model_title]
                    )
                    # extra_networks_button = create_browse_model_button(
                    #     'Show workspace models',
                    #     'browse_models_in_workspace',
                    #     button_style="width: 200px !important; flex-grow: 0.3 !important; align-self: flex-end;",
                    #     js_function="browseWorkspaceModels")
                    # create_browse_model_button(
                    #     'Browse All Models',
                    #     'browse_all_models',
                    #     button_style="width: 200px !important; flex-grow: 0.3 !important; align-self: flex-end;",
                    #     js_function="openWorkSpaceDialog")

        parameters_copypaste.connect_paste_params_buttons(dummy_component)

        # with FormRow(variant='compact', elem_id="img2img_extra_networks", visible=False) as extra_networks:
        #     extra_networks_ui = ui_extra_networks.create_ui(extra_networks, extra_networks_button, 'img2img')
        #     ui_extra_networks.setup_ui(extra_networks_ui, txt2img_gallery)
        #     ui_extra_networks.setup_ui(extra_networks_ui, img2img_gallery)

        with gr.Tabs(elem_id="tabs") as tabs:
            tab_order = {k: i for i, k in enumerate(opts.ui_tab_order)}
            sorted_interfaces = sorted(interfaces, key=lambda x: tab_order.get(x[1], 9999))

            for interface, label, ifid in sorted_interfaces:
                if label in shared.opts.hidden_tabs:
                    if label in ('Settings', 'Setting'):
                        with gr.TabItem(label, id=ifid, elem_id=f"tab_{ifid}", elem_classes=["hidden"]):
                            interface.render()
                    continue
                with gr.TabItem(label, id=ifid, elem_id=f"tab_{ifid}"):
                    interface.render()

                if ifid not in ["extensions", "settings"]:
                    loadsave.add_block(interface, ifid)

            loadsave.add_component(f"webui/Tabs@{tabs.elem_id}", tabs)

            loadsave.setup_ui()

        # def tab_changed(evt: gr.SelectData):
        #     no_quick_setting = getattr(shared.opts, "tabs_without_quick_settings_bar", [])
        #     return gr.update(visible=evt.value not in no_quick_setting)
        #
        # tabs.select(tab_changed, outputs=[quicksettings_row], show_progress=False, queue=False)

        if os.path.exists(os.path.join(script_path, "notification.mp3")) and shared.opts.notification_audio:
            gr.Audio(interactive=False, value=os.path.join(script_path, "notification.mp3"), elem_id="audio_notification", visible=False)

        footer = shared.html("footer.html")
        languages = list(localization.localizations.keys())
        languages.sort()
        footer = footer.format(versions=versions_html(), language_list=['None'] + languages)
        gr.HTML(footer, elem_id="footer")
        settings.add_functionality(demo)

        update_image_cfg_scale_visibility = lambda: gr.update(visible=False)
        settings.text_settings.change(fn=update_image_cfg_scale_visibility, inputs=[], outputs=[image_cfg_scale])
        demo.load(fn=update_image_cfg_scale_visibility, inputs=[], outputs=[image_cfg_scale])

        # modelmerger_ui.setup_ui(
        #     dummy_component=dummy_component,
        #     sd_model_checkpoint_component=main_entry.ui_checkpoint,
        #     upgrade_info=upgrade_info,
        # )

        main_entry.forge_main_entry()

        def load_styles(request: gr.Request):
            choices = {"choices": [x for x in shared.prompt_styles(request).styles.keys()]}
            return gr.update(**choices), gr.update(**choices), gr.update(**choices), gr.update(**choices)
        demo.load(fn=load_styles, inputs=None, outputs=[txt2img_prompt_styles, txt2img_prompt_selections, img2img_prompt_styles, img2img_prompt_selections])

        demo.load(
            fn=None, js="updateCheckpointDropdownWithHR", inputs=None, outputs=[sd_model_selection, hr_checkpoint_name])

        demo.load(
            fn=lambda: return_signature_str_from_list(txt2img_signature_args), inputs=None, outputs=[txt2img_signature])
        demo.load(
            fn=lambda: return_signature_str_from_list(txt2img_upscale_signature_args), inputs=None, outputs=[txt2img_upscale_signature])
        demo.load(
            fn=lambda: return_signature_str_from_list(img2img_signature_args), inputs=None, outputs=[img2img_signature])

        global txt2img_function_index
        global img2img_function_index
        for demo_block_function_idx, demo_block_function in demo.fns.items():
            if demo_block_function == txt2img_gradio_function:
                txt2img_function_index = demo_block_function_idx
            if demo_block_function == img2img_gradio_function:
                img2img_function_index = demo_block_function_idx

        demo.load(
            fn=lambda: txt2img_function_index, inputs=None, outputs=[txt2img_fn_index_component])
        demo.load(
            fn=lambda: img2img_function_index, inputs=None, outputs=[img2img_fn_index_component])

        # build elements for script page load callbback
        interface_list = []
        interface_components = []
        global interface_function_indicies
        for interface_name in script_callbacks.script_interfaces:
            interface_arg_start_index = len(interface_components)
            for component_index in script_callbacks.script_interfaces[interface_name][0].blocks:
                interface_component = script_callbacks.script_interfaces[interface_name][0].blocks[component_index]
                if isinstance(interface_component, gr.components.Component):
                    interface_components.append(interface_component)
            interfce_arg_end_index = len(interface_components)
            interface_list.append(
                (interface_name,
                 interface_arg_start_index,
                 interfce_arg_end_index,
                 script_callbacks.script_interfaces[interface_name][0]))
            interface_function_indicies[interface_name] = {
                "interface_title": script_callbacks.script_interfaces[interface_name][1],
                "interface_name": script_callbacks.script_interfaces[interface_name][2],
                "interface_fn_indicies": [],
            }
            for script_fn in script_callbacks.script_interfaces[interface_name][0].fns:
                for demo_block_function_idx, demo_block_function in enumerate(demo.fns):
                    if demo_block_function == script_fn:
                        interface_function_indicies[interface_name]["interface_fn_indicies"].append(demo_block_function_idx)
                        break

        demo.load(
            fn=script_callbacks.page_load_callback_factory(interface_list), inputs=interface_components, outputs=interface_components)

    if ui_settings_from_file != loadsave.ui_settings:
        loadsave.dump_defaults()
    demo.ui_loadsave = loadsave

    return demo


def versions_html():
    import torch
    import launch

    python_version = ".".join([str(x) for x in sys.version_info[0:3]])
    commit = launch.commit_hash()
    short_commit = commit[0:8]
    tag = launch.git_tag()

    if shared.xformers_available:
        import xformers
        xformers_version = xformers.__version__
    else:
        xformers_version = "N/A"

    return f"""
webui version: <a href="https://github.com/AUTOMATIC1111/stable-diffusion-webui/commit/{commit}">{tag}</a>
&#x2000;•&#x2000;
python: <span title="{sys.version}">{python_version}</span>
&#x2000;•&#x2000;
torch: {getattr(torch, '__long_version__',torch.__version__)}
&#x2000;•&#x2000;
xformers: {xformers_version}
&#x2000;•&#x2000;
gradio: {gr.__version__}
&#x2000;•&#x2000;
diffus commit: <a href="https://github.com/Graviti-AI/stable-diffusion-webui/commit/{commit}">{short_commit}</a>
&#x2000;•&#x2000;
checkpoint: <a id="sd_checkpoint_hash">N/A</a>
"""


def setup_ui_api(app):
    from pydantic import BaseModel, Field
    from modules.launch_utils import startup_record
    assert opts is not None, "opts is not initialized yet"

    class QuicksettingsHint(BaseModel):
        name: str = Field(title="Name of the quicksettings field")
        label: str = Field(title="Label of the quicksettings field")

    def quicksettings_hint():
        return [QuicksettingsHint(name=k, label=v.label) for k, v in opts.data_labels.items()]

    app.add_api_route("/internal/quicksettings-hint", quicksettings_hint, methods=["GET"], response_model=list[QuicksettingsHint])

    app.add_api_route("/internal/ping", lambda: {}, methods=["GET"])

    app.add_api_route("/internal/profile-startup", lambda: startup_record, methods=["GET"])

    def download_sysinfo(attachment=False):
        from fastapi.responses import PlainTextResponse

        text = sysinfo.get()
        filename = f"sysinfo-{datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M')}.json"

        return PlainTextResponse(text, headers={'Content-Disposition': f'{"attachment" if attachment else "inline"}; filename="{filename}"'})

    app.add_api_route("/internal/sysinfo", download_sysinfo, methods=["GET"])
    app.add_api_route("/internal/sysinfo-download", lambda: download_sysinfo(attachment=True), methods=["GET"])

    def construct_signature_response(args: list, default_values: list, fn_index: int | None, output_placeholders: list):
        return {
            "signature": return_signature_str_from_list(args),
            "args": args,
            "default_values": default_values,
            "fn_index": fn_index,
            "output_placeholders": output_placeholders,
        }

    app.add_api_route(
        "/internal/signature/txt2img",
        lambda: construct_signature_response(
            args=txt2img_signature_args,
            default_values=txt2img_params_default_values,
            fn_index=txt2img_function_index,
            output_placeholders=txt2img_suffix_outputs
        ),
        methods=["GET"])
    app.add_api_route(
        "/internal/signature/img2img",
        lambda: construct_signature_response(
            args=img2img_signature_args,
            default_values=img2img_params_default_values,
            fn_index=img2img_function_index,
            output_placeholders=img2img_suffix_outputs
        ),
        methods=["GET"])
    app.add_api_route(
        "/internal/scripts/function_index",
        lambda: interface_function_indicies,
        methods=["GET"])

    import fastapi.staticfiles
    app.mount("/webui-assets", fastapi.staticfiles.StaticFiles(directory=launch_utils.repo_dir('stable-diffusion-webui-assets')), name="webui-assets")
