import html
import json
import os

import gradio as gr

from modules import shared, ui_extra_networks, sd_models


class ExtraNetworksPageCheckpoints(ui_extra_networks.ExtraNetworksPage):
    def __init__(self):
        super().__init__('Checkpoints')
        self.min_model_size_mb = 1e3

    def refresh(self, request: gr.Request):
        shared.refresh_checkpoints(request.request)

    def list_items(self):
        checkpoint: sd_models.CheckpointInfo
        for name, checkpoint in sd_models.checkpoints_list.items():
            path, ext = os.path.splitext(checkpoint.filename)
            metadata_path = "".join([path, ".meta"])
            yield {
                "name": checkpoint.name_for_extra,
                "filename": path,
                "preview": self.find_preview(path),
                "description": self.find_description(path),
                "search_term": self.search_terms_from_path(checkpoint.filename) + " " + (checkpoint.sha256 or ""),
                "onclick": '"' + html.escape(f"""return selectCheckpoint({json.dumps(name)})""") + '"',
                "local_preview": f"{path}.{shared.opts.samples_format}",
                "metadata": ui_extra_networks.ExtraNetworksPage.read_metadata_from_file(metadata_path),
            }

    def allowed_directories_for_previews(self):
        return [v for v in [shared.cmd_opts.ckpt_dir, sd_models.model_path] if v is not None]
