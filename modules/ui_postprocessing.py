import gradio as gr
from modules import scripts, shared, ui_common, postprocessing, call_queue, ui_toprow
import modules.infotext_utils as parameters_copypaste
from modules.ui_components import ResizeHandleRow
from modules.postprocessing import monitor_extras_params

import os
from PIL import Image
from tempfile import _TemporaryFileWrapper


def create_ui():
    dummy_component = gr.Label(visible=False)
    tab_index = gr.Number(value=0, visible=False)
    upgrade_info = gr.JSON(value={}, interactive=False, visible=False)

    source_width = gr.Number(visible=False)
    source_height = gr.Number(visible=False)
    source_widths = gr.JSON(visible=False)
    source_heights = gr.JSON(visible=False)

    with ResizeHandleRow(equal_height=False, variant='compact'):
        with gr.Column(variant='compact'):
            with gr.Tabs(elem_id="mode_extras"):
                with gr.TabItem('Single Image', id="single_image", elem_id="extras_single_tab") as tab_single:
                    extras_image = gr.Image(label="Source", source="upload", interactive=True, type="pil", elem_id="extras_image")

                with gr.TabItem('Batch Process', id="batch_process", elem_id="extras_batch_process_tab") as tab_batch:
                    image_batch = gr.Files(label="Batch Process", interactive=True, elem_id="extras_image_batch")
                    extras_batch_input_dir = gr.Label(visible=False)
                    extras_batch_output_dir = gr.Label(visible=False)
                    show_extras_results = gr.Label(visible=False)

                # with gr.TabItem('Batch from Directory', id="batch_from_directory", elem_id="extras_batch_directory_tab") as tab_batch_dir:
                #     extras_batch_input_dir = gr.Textbox(label="Input directory", **shared.hide_dirs, placeholder="A directory on the same machine where the server is running.", elem_id="extras_batch_input_dir")
                #     extras_batch_output_dir = gr.Textbox(label="Output directory", **shared.hide_dirs, placeholder="Leave blank to save images to the default path.", elem_id="extras_batch_output_dir")
                #     show_extras_results = gr.Checkbox(label='Show result images', value=True, elem_id="extras_show_extras_results")

            script_inputs = scripts.scripts_postproc.setup_ui()

        with gr.Column():
            from modules.paths import Paths
            toprow = ui_toprow.Toprow(is_compact=True, is_img2img=False, id_part="extras")
            toprow.create_inline_toprow_image()
            submit = toprow.submit

            output_panel = ui_common.create_output_panel("extras", Paths(None).outdir_extras_samples())

    tab_single.select(fn=lambda: 0, inputs=[], outputs=[tab_index])
    tab_batch.select(fn=lambda: 1, inputs=[], outputs=[tab_index])
    # tab_batch_dir.select(fn=lambda: 2, inputs=[], outputs=[tab_index])

    extras_image.change(
        _get_image_resolution,
        inputs=[extras_image],
        outputs=[source_width, source_height],
    )
    image_batch.change(
        _get_batch_image_resolusion,
        inputs=[image_batch],
        outputs=[source_widths, source_heights],
    )

    monitor_extras_params(tab_index, "extras_mode")
    monitor_extras_params(source_width, "source_width")
    monitor_extras_params(source_height, "source_height")
    monitor_extras_params(source_widths, "source_widths")
    monitor_extras_params(source_heights, "source_heights")

    submit.click(
        fn=call_queue.wrap_gradio_gpu_call(postprocessing.run_postprocessing, extra_outputs=[None, '', ''], add_monitor_state=True),
        _js="submit_extras",
        inputs=[
            dummy_component,
            tab_index,
            extras_image,
            image_batch,
            extras_batch_input_dir,
            extras_batch_output_dir,
            show_extras_results,
            *script_inputs
        ],
        outputs=[
            output_panel.gallery,
            output_panel.generation_info,
            output_panel.infotext,
            output_panel.html_log,
            upgrade_info,
        ],
        show_progress=False,
    )

    upgrade_info.change(None, [upgrade_info], None, _js="upgradeCheck")
    parameters_copypaste.add_paste_fields("extras", extras_image, None)

    extras_image.change(
        fn=scripts.scripts_postproc.image_changed,
        inputs=[], outputs=[]
    )

    output_panel.gallery.select(
        fn=None,
        inputs=[output_panel.generation_info],
        outputs=[output_panel.infotext],
        _js="updateExtraResults",
    )

def _get_image_resolution(image: Image.Image | _TemporaryFileWrapper | None) -> tuple[int, int]:
    if image is None:
        return 0, 0

    if not isinstance(image, Image.Image):
        image = Image.open(os.path.abspath(image.name))

    return image.width, image.height

def _get_batch_image_resolusion(images: list[Image.Image | _TemporaryFileWrapper]) -> tuple[list[int], list[int]]:
    if images is None:
        return [], []

    widths = []
    heights = []
    for image in images:
        width, height = _get_image_resolution(image)
        widths.append(width)
        heights.append(height)

    return widths, heights
