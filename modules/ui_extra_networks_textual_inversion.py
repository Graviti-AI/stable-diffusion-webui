import json
import os

import gradio as gr

from modules import ui_extra_networks, sd_hijack, shared


class ExtraNetworksPageTextualInversion(ui_extra_networks.ExtraNetworksPage):
    def __init__(self):
        super().__init__('Textual Inversion')
        self.allow_negative_prompt = True
        self.max_model_size_mb = 5

    def refresh_metadata(self):
        sd_hijack.model_hijack.embedding_db.load_textual_inversion_embeddings()
        for embedding in sd_hijack.model_hijack.embedding_db.word_embeddings.values():
            path, ext = os.path.splitext(embedding.filename)
            metadata_path = "".join([path, ".meta"])
            metadata = ui_extra_networks.ExtraNetworksPage.read_metadata_from_file(metadata_path)
            if metadata is not None:
                self.metadata[embedding.name] = metadata

    def refresh(self, request: gr.Request):
        sd_hijack.model_hijack.embedding_db.load_textual_inversion_embeddings(force_reload=True)
        self.refresh_metadata()

    def get_items_count(self):
        return len(sd_hijack.model_hijack.embedding_db.word_embeddings)

    def list_items(self):
        sd_hijack.model_hijack.embedding_db.load_textual_inversion_embeddings()
        for embedding in sd_hijack.model_hijack.embedding_db.word_embeddings.values():
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
            yield {
                "name": embedding.name,
                "filename": embedding.filename,
                "preview": self.find_preview(path),
                "description": self.find_description(path),
                "search_term": search_term,
                "prompt": json.dumps(embedding.name),
                "local_preview": f"{path}.preview.{shared.opts.samples_format}",
                "metadata": metadata,
            }

    def allowed_directories_for_previews(self):
        return list(sd_hijack.model_hijack.embedding_db.embedding_dirs)
