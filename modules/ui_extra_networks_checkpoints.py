import html
import json
import os

from modules import shared, ui_extra_networks, sd_models


class ExtraNetworksPageCheckpoints(ui_extra_networks.ExtraNetworksPage):
    def __init__(self, model_path: str):
        super().__init__('Checkpoints')
        self.model_path = model_path

    def refresh(self):
        shared.refresh_checkpoints()

    def list_items(self):
        checkpoint: sd_models.CheckpointInfo
        check_points = sd_models.list_models(None)
        for name, checkpoint in check_points.checkpoints_list.items():
            path, ext = os.path.splitext(checkpoint.filename)
            yield {
                "name": checkpoint.name_for_extra,
                "filename": path,
                "preview": self.find_preview(path),
                "description": self.find_description(path),
                "search_term": self.search_terms_from_path(checkpoint.filename) + " " + (checkpoint.sha256 or ""),
                "onclick": '"' + html.escape(f"""return selectCheckpoint({json.dumps(name)})""") + '"',
                "local_preview": f"{path}.{shared.opts.samples_format}",
            }

    def allowed_directories_for_previews(self):
        return [v for v in [shared.cmd_opts.ckpt_dir, self.model_path] if v is not None]

