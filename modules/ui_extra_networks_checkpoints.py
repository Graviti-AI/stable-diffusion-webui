import html
import json
import os

from modules import shared, ui_extra_networks, sd_models
from fastapi import Request


class ExtraNetworksPageCheckpoints(ui_extra_networks.ExtraNetworksPage):
    def __init__(self):
        super().__init__('Checkpoints')
        self.min_model_size_mb = 1e3

    def refresh_metadata(self):
        for name, checkpoint in sd_models.checkpoints_list.items():
            path, ext = os.path.splitext(checkpoint.filename)
            metadata_path = "".join([path, ".meta"])
            metadata = ui_extra_networks.ExtraNetworksPage.read_metadata_from_file(metadata_path)
            if metadata is not None:
                self.metadata[checkpoint.name_for_extra] = metadata

    def refresh(self, request: Request):
        shared.refresh_checkpoints(request)
        self.refresh_metadata()

    def get_items_count(self):
        return len(sd_models.checkpoints_list)

    def list_items(self):
        checkpoint: sd_models.CheckpointInfo
        for name, checkpoint in sd_models.checkpoints_list.items():
            path, ext = os.path.splitext(checkpoint.filename)
            search_term = " ".join([self.search_terms_from_path(checkpoint.filename), (checkpoint.sha256 or "")])
            metadata = self.metadata.get(checkpoint.name_for_extra, None)
            if metadata is not None:
                search_term = " ".join([
                    search_term,
                    ", ".join(metadata["tags"]),
                    ", ".join(metadata["trigger_word"]),
                    metadata["model_name"]])
            yield {
                "name": checkpoint.name_for_extra,
                "filename": path,
                "preview": self.find_preview(path),
                "description": self.find_description(path),
                "search_term": search_term,
                "onclick": '"' + html.escape(f"""return selectCheckpoint({json.dumps(name)})""") + '"',
                "local_preview": f"{path}.{shared.opts.samples_format}",
                "metadata": metadata,
            }

    def allowed_directories_for_previews(self):
        return [v for v in [shared.cmd_opts.ckpt_dir, sd_models.model_path] if v is not None]
