from modules import scripts_postprocessing, ui_components, deepbooru, shared
import gradio as gr


class ScriptPostprocessingCeption(scripts_postprocessing.ScriptPostprocessing):
    name = "Caption"
    order = 4040

    def ui(self):
        with ui_components.InputAccordion(False, label="Caption") as enable:
            option = gr.CheckboxGroup(value=["Deepbooru"], choices=["Deepbooru", "BLIP"], show_label=False)

        return {
            "enable": enable,
            "option": option,
        }

    def process(self, pp: scripts_postprocessing.PostprocessedImage, enable, option):
        if not enable:
            return

        captions = {}

        if "Deepbooru" in option:
            captions["Deepbooru"] = deepbooru.model.tag(pp.image)

        if "BLIP" in option:
            captions["BLIP"] = shared.interrogator.interrogate(pp.image.convert("RGB"))

        pp.caption = captions
