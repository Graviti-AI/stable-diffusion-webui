from modules import scripts_postprocessing, ui_components, deepbooru, shared
from modules.system_monitor import monitor_call_context
from modules.postprocessing import monitor_extras_params
import gradio as gr


class ScriptPostprocessingCeption(scripts_postprocessing.ScriptPostprocessing):
    name = "Caption"
    order = 4040

    def ui(self):
        with ui_components.InputAccordion(False, label="Caption") as enable:
            option = gr.CheckboxGroup(value=["Deepbooru"], choices=["Deepbooru", "BLIP"], show_label=False)

        monitor_extras_params(enable, "caption_enabled")
        monitor_extras_params(option, "caption_option_number", "(x) => x.length")

        return {
            "enable": enable,
            "option": option,
        }

    def _process(self, pp: scripts_postprocessing.PostprocessedImage, enable, option):
        if not enable:
            return

        captions = {}

        if "Deepbooru" in option:
            captions["Deepbooru"] = deepbooru.model.tag(pp.image)

        if "BLIP" in option:
            captions["BLIP"] = shared.interrogator.interrogate(pp.image.convert("RGB"))

        pp.caption = captions

    def process(self, pp: scripts_postprocessing.PostprocessedImage, enable, option):
        if not enable:
            return

        if not option:
            return

        with monitor_call_context(
            pp.get_request(),
            "extras.caption",
            "extras.caption",
            decoded_params={
                "width": pp.image.width,
                "height": pp.image.height,
                "option_number": len(option),
            },
        ):
            return self._process(pp, enable, option)
