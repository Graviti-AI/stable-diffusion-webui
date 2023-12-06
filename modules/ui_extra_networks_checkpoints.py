import html
import json
import os

from modules import shared, ui_extra_networks, sd_models
from modules.ui_extra_networks import quote_js
from modules.ui_extra_networks_checkpoints_user_metadata import CheckpointUserMetadataEditor
from fastapi import Request


class ExtraNetworksPageCheckpoints(ui_extra_networks.ExtraNetworksPage):
    def __init__(self):
        super().__init__('Checkpoints')
        self.min_model_size_mb = 1e3
        self.max_model_size_mb = 15e3

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

    def create_item(self, name, index=None, model=None, enable_filter=True):
        if model is None:
            checkpoint: sd_models.CheckpointInfo = sd_models.checkpoint_aliases.get(name)
        else:
            checkpoint: sd_models.CheckpointInfo = model
        path, ext = os.path.splitext(checkpoint.filename)
        search_term = " ".join([self.search_terms_from_path(checkpoint.filename), (checkpoint.sha256 or "")])
        metadata = self.metadata.get(checkpoint.name_for_extra, None)
        if metadata is not None:
            search_term = " ".join([
                search_term,
                ", ".join(metadata["tags"]),
                ", ".join(metadata["trigger_word"]),
                metadata["model_name"]])
        return {
            "name": checkpoint.name_for_extra,
            "filename": path,
            "shorthash": checkpoint.shorthash,
            "preview": self.find_preview(path),
            "description": self.find_description(path),
            "search_term": search_term,
            "onclick": '"' + html.escape(f"""return selectCheckpoint({json.dumps(name)})""") + '"',
            "local_preview": f"{path}.{shared.opts.samples_format}",
            "metadata": checkpoint.metadata,
            "sort_keys": {'default': index, **self.get_sort_keys(checkpoint.filename)},
            "metadata": metadata,
        }

    def list_items(self):
        checkpoint: sd_models.CheckpointInfo
        for index, (name, checkpoint) in enumerate(sd_models.checkpoints_list.items()):
            yield self.create_item(name, index, checkpoint)

    def allowed_directories_for_previews(self):
        return [v for v in [shared.cmd_opts.ckpt_dir, sd_models.model_path] if v is not None]

    def create_user_metadata_editor(self, ui, tabname):
        return CheckpointUserMetadataEditor(ui, tabname, self)
