import os
import json

import gradio as gr

from modules import shared, ui_extra_networks
from modules.ui_extra_networks import quote_js
from modules.hashes import sha256_from_cache


class ExtraNetworksPageHypernetworks(ui_extra_networks.ExtraNetworksPage):
    def __init__(self):
        super().__init__('Hypernetworks')
        self.min_model_size_mb = 10
        self.max_model_size_mb = 1e3

    def refresh_metadata(self):
        for name, path in shared.hypernetworks.items():
            path, ext = os.path.splitext(path)
            metadata_path = "".join([path, ".meta"])
            metadata = ui_extra_networks.ExtraNetworksPage.read_metadata_from_file(metadata_path)
            if metadata is not None:
                self.metadata[name] = metadata

    def refresh(self, request: gr.Request):
        shared.reload_hypernetworks()
        self.refresh_metadata()

    def get_items_count(self):
        return len(shared.hypernetworks)

    def create_item(self, name, index=None, model=None, enable_filter=True):
        if model is None:
            path = shared.hypernetworks[name]
        else:
            path = model
        path, ext = os.path.splitext(path)
        search_term = self.search_terms_from_path(path)
        metadata = self.metadata.get(name, None)
        if metadata is not None:
            search_term = " ".join([
                search_term,
                ", ".join(metadata["tags"]),
                ", ".join(metadata["trigger_word"]),
                metadata["model_name"],
                metadata["sha256"]])

        return {
            "name": name,
            "filename": path,
            "shorthash": metadata.get("sha256", "")[0:10] if metadata else "",
            "preview": self.find_preview(path),
            "description": self.find_description(path),
            "search_term": search_term,
            "prompt": quote_js(
                f"<hypernet:{name}:") + " + opts.extra_networks_default_multiplier + " + quote_js(">"),
            "local_preview": f"{path}.preview.{shared.opts.samples_format}",
            "sort_keys": {'default': index, **self.get_sort_keys(path + ext)},
            "metadata": metadata,
        }

    def list_items(self):
        for index, (name, path) in enumerate(shared.hypernetworks.items()):
            yield self.create_item(name, index, path)

    def allowed_directories_for_previews(self):
        return [shared.cmd_opts.hypernetwork_dir]
