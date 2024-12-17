import gradio as gr

from modules import scripts, sd_models
from modules.infotext_utils import PasteField
from modules.ui_common import create_refresh_button
from modules.ui_components import InputAccordion

from modules.model_info import AllModelInfo, MODEL_INFO_KEY


class ScriptRefiner(scripts.ScriptBuiltinUI):
    section = "accordions"
    create_group = False

    def __init__(self):
        pass

    def title(self):
        return "Refiner"

    def show(self, is_img2img):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        with InputAccordion(False, label="Refiner", elem_id=self.elem_id("enable")) as enable_refiner:
            with gr.Row():
                refiner_checkpoint = gr.Dropdown(
                    label='Checkpoint',
                    info='(use model of same architecture)',
                    elem_id=self.elem_id("checkpoint"),
                    choices=[],
                    value=None,
                    tooltip="switch to another model in the middle of generation")
                create_refresh_button(refiner_checkpoint, None, None, self.elem_id("checkpoint_refresh"), _js="updateCheckpointDropdown")

                refiner_switch_at = gr.Slider(value=0.8, label="Switch at", minimum=0.01, maximum=1.0, step=0.01, elem_id=self.elem_id("switch_at"), tooltip="fraction of sampling steps when the switch to refiner model should happen; 1=never, 0.5=switch in the middle of generation")

            enable_refiner.change(
                fn=None,
                _js="async (enabled) => enabled ? await updateCheckpointDropdown() : {__type__: 'update'}",
                inputs=[enable_refiner],
                outputs=[refiner_checkpoint],
            )

        def lookup_checkpoint(title):
            info = sd_models.get_closet_checkpoint_match(title)
            return None if info is None else info.short_title

        def _gallery_lookup_checkpoint(params: dict) -> dict:
            all_model_info: AllModelInfo = params[MODEL_INFO_KEY]
            short_title = params.get("Refiner")
            if not short_title:
                return gr.update(value=None)

            model_info = all_model_info.get_checkpoint_by_short_title(short_title)
            if model_info is None:
                return gr.update(value=None)

            return gr.update(value=model_info.title)

        self.infotext_fields = [
            PasteField(enable_refiner, lambda d: 'Refiner' in d),
            PasteField(refiner_checkpoint, _gallery_lookup_checkpoint, api="refiner_checkpoint"),
            PasteField(refiner_switch_at, 'Refiner switch at', api="refiner_switch_at"),
        ]

        return enable_refiner, refiner_checkpoint, refiner_switch_at

    def setup(self, p, enable_refiner, refiner_checkpoint, refiner_switch_at):
        # the actual implementation is in sd_samplers_common.py, apply_refiner
        if not enable_refiner or refiner_checkpoint in (None, "", "None"):
            p.refiner_checkpoint = None
            p.refiner_switch_at = None
        else:
            p.refiner_checkpoint = refiner_checkpoint
            p.refiner_switch_at = refiner_switch_at
