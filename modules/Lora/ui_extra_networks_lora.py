import json
import os
import gradio as gr

from modules import shared, ui_extra_networks
from modules.Lora import lora


class ExtraNetworksPageLora(ui_extra_networks.ExtraNetworksPage):
    def __init__(self):
        super().__init__('Lora')
        self.min_model_size_mb = 1
        self.max_model_size_mb = 1e3

    def refresh_metadata(self):
        for name, lora_on_disk in lora.available_loras.items():
            if name not in self.metadata:
                path, ext = os.path.splitext(lora_on_disk.filename)
                metadata_path = "".join([path, ".meta"])
                metadata = ui_extra_networks.ExtraNetworksPage.read_metadata_from_file(metadata_path)
                if metadata is not None:
                    self.metadata[name] = metadata

    def refresh(self, request: gr.Request):
        lora.list_available_loras()
        self.refresh_metadata()

    def get_items_count(self):
        return len(lora.available_loras)

    def list_items(self):
        for name, lora_on_disk in lora.available_loras.items():
            path, ext = os.path.splitext(lora_on_disk.filename)
            search_term = self.search_terms_from_path(lora_on_disk.filename)
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
                    f"<lora:{name}:") + " + opts.extra_networks_default_multiplier + " + json.dumps(">"),
                "local_preview": f"{path}.{shared.opts.samples_format}",
                "metadata": metadata,
            }

    def allowed_directories_for_previews(self):
        return [shared.cmd_opts.lora_dir]
