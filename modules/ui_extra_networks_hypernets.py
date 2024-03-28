import os

from modules import shared, ui_extra_networks
from modules.ui_extra_networks import quote_js
from modules.hashes import sha256_from_cache


class ExtraNetworksPageHypernetworks(ui_extra_networks.ExtraNetworksPage):
    def __init__(self):
        super().__init__('Hypernetworks')
        self.min_model_size_mb = 10
        self.max_model_size_mb = 1e3

    def refresh(self, _):
        shared.reload_hypernetworks()

    def get_items_count(self):
        return len(shared.hypernetworks)

    def create_item(self, name, index=None, model=None, enable_filter=True):
        if model is None:
            full_path = shared.hypernetworks[name]
        else:
            full_path = model
        full_path, ext = os.path.splitext(full_path)
        search_term = self.search_terms_from_path(full_path)
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
            "filename": full_path,
            "shorthash": metadata.get("sha256", "")[0:10] if metadata else "",
            "preview": self.find_preview(full_path),
            "description": self.find_description(full_path),
            "search_terms": [search_term],
            "prompt": quote_js(f"<hypernet:{name}:") + " + opts.extra_networks_default_multiplier + " + quote_js(">"),
            "local_preview": f"{full_path}.preview.{shared.opts.samples_format}",
            "sort_keys": {'default': index, **self.get_sort_keys(full_path + ext)},
            "metadata": metadata,
        }

    def list_items(self):
        for index, (name, path) in enumerate(shared.hypernetworks.items()):
            yield self.create_item(name, index, path)

    def allowed_directories_for_previews(self):
        return [shared.cmd_opts.hypernetwork_dir]
