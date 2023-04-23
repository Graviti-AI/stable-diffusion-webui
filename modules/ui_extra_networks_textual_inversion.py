import json
import os

import gradio as gr

from modules import ui_extra_networks, sd_hijack, shared


class ExtraNetworksPageTextualInversion(ui_extra_networks.ExtraNetworksPage):
    def __init__(self):
        super().__init__('Textual Inversion')
        self.allow_negative_prompt = True
        self.max_model_size_mb = 5

    def refresh(self, request: gr.Request):
        sd_hijack.model_hijack.embedding_db.load_textual_inversion_embeddings(force_reload=True)

    def list_items(self):
        sd_hijack.model_hijack.embedding_db.load_textual_inversion_embeddings()
        for embedding in sd_hijack.model_hijack.embedding_db.word_embeddings.values():
            path, ext = os.path.splitext(embedding.filename)
            metadata_path = "".join([path, ".meta"])
            yield {
                "name": embedding.name,
                "filename": embedding.filename,
                "preview": self.find_preview(path),
                "description": self.find_description(path),
                "search_term": self.search_terms_from_path(embedding.filename),
                "prompt": json.dumps(embedding.name),
                "local_preview": f"{path}.preview.{shared.opts.samples_format}",
                "metadata": ui_extra_networks.ExtraNetworksPage.read_metadata_from_file(metadata_path),
            }

    def allowed_directories_for_previews(self):
        return list(sd_hijack.model_hijack.embedding_db.embedding_dirs)
