import os

from modules import ui_extra_networks, sd_hijack, shared
from modules.ui_extra_networks import quote_js


class ExtraNetworksPageTextualInversion(ui_extra_networks.ExtraNetworksPage):
    def __init__(self):
        super().__init__('Textual Inversion')
        self.allow_negative_prompt = True
        self.max_model_size_mb = 5

    def refresh(self, _):
        sd_hijack.model_hijack.embedding_db.load_textual_inversion_embeddings(force_reload=True)

    def get_items_count(self):
        return len(sd_hijack.model_hijack.embedding_db.word_embeddings)

    def create_item(self, name, index=None, model=None, enable_filter=True):
        if model is None:
            embedding = sd_hijack.model_hijack.embedding_db.word_embeddings.get(name)
        else:
            embedding = model

        path, ext = os.path.splitext(embedding.filename)
        search_term = self.search_terms_from_path(embedding.filename)
        metadata = self.metadata.get(embedding.name, None)
        if metadata is not None:
            search_term = " ".join([
                search_term,
                ", ".join(metadata["tags"]),
                ", ".join(metadata["trigger_word"]),
                metadata["model_name"],
                metadata["sha256"]])
        return {
            "name": name,
            "filename": embedding.filename,
            "shorthash": embedding.shorthash,
            "preview": self.find_preview(path),
            "description": self.find_description(path),
            "search_terms": [search_term],
            "prompt": quote_js(embedding.name),
            "local_preview": f"{path}.preview.{shared.opts.samples_format}",
            "sort_keys": {'default': index, **self.get_sort_keys(embedding.filename)},
            "metadata": metadata,
        }

    def list_items(self):
        sd_hijack.model_hijack.embedding_db.load_textual_inversion_embeddings()
        for index, (name, embedding) in enumerate(sd_hijack.model_hijack.embedding_db.word_embeddings.items()):
            yield self.create_item(name, index, embedding)

    def allowed_directories_for_previews(self):
        return list(sd_hijack.model_hijack.embedding_db.embedding_dirs)
