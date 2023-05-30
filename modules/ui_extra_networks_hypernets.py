import json
import os
import gradio as gr

from modules import shared, ui_extra_networks


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

    def list_items(self):
        for name, path in shared.hypernetworks.items():
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

            yield {
                "name": name,
                "filename": path,
                "preview": self.find_preview(path),
                "description": self.find_description(path),
                "search_term": search_term,
                "prompt": json.dumps(
                    f"<hypernet:{name}:") + " + opts.extra_networks_default_multiplier + " + json.dumps(">"),
                "local_preview": f"{path}.preview.{shared.opts.samples_format}",
                "metadata": metadata,
            }

    def allowed_directories_for_previews(self):
        return [shared.cmd_opts.hypernetwork_dir]
