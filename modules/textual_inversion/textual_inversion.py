import logging
import os
from collections import namedtuple
from collections.abc import Mapping
from contextlib import closing

import starlette.requests
import torch
import tqdm
import html
import datetime
import csv
import safetensors.torch

import numpy as np
from PIL import Image, PngImagePlugin

from modules import shared, devices, sd_hijack, sd_models, images, sd_samplers, sd_hijack_checkpoint, errors, hashes

from modules.textual_inversion.image_embedding import embedding_to_b64, embedding_from_b64, insert_image_data_embed, extract_image_data_embed, caption_image_overlay
from modules.model_info import ModelInfo


TextualInversionTemplate = namedtuple("TextualInversionTemplate", ["name", "path"])
textual_inversion_templates = {}


def list_textual_inversion_templates():
    textual_inversion_templates.clear()

    for root, _, fns in os.walk(shared.cmd_opts.textual_inversion_templates_dir):
        for fn in fns:
            path = os.path.join(root, fn)

            textual_inversion_templates[fn] = TextualInversionTemplate(fn, path)

    return textual_inversion_templates


class Embedding:
    def __init__(self, vec, name, step=None):
        self.vec = vec
        self.name = name
        self.step = step
        self.shape = None
        self.vectors = 0
        self.cached_checksum = None
        self.sd_checkpoint = None
        self.sd_checkpoint_name = None
        self.optimizer_state_dict = None
        self.filename = None
        self.hash = None
        self.shorthash = None

    def save(self, filename):
        embedding_data = {
            "string_to_token": {"*": 265},
            "string_to_param": {"*": self.vec},
            "name": self.name,
            "step": self.step,
            "sd_checkpoint": self.sd_checkpoint,
            "sd_checkpoint_name": self.sd_checkpoint_name,
        }

        torch.save(embedding_data, filename)

        if shared.opts.save_optimizer_state and self.optimizer_state_dict is not None:
            optimizer_saved_dict = {
                'hash': self.checksum(),
                'optimizer_state_dict': self.optimizer_state_dict,
            }
            torch.save(optimizer_saved_dict, f"{filename}.optim")

    def checksum(self):
        if self.cached_checksum is not None:
            return self.cached_checksum

        def const_hash(a):
            r = 0
            for v in a:
                r = (r * 281 ^ int(v) * 997) & 0xFFFFFFFF
            return r

        self.cached_checksum = f'{const_hash(self.vec.reshape(-1) * 100) & 0xffff:04x}'
        return self.cached_checksum

    def set_hash(self, v):
        self.hash = v
        self.shorthash = self.hash[0:12]


class DirWithTextualInversionEmbeddings:
    def __init__(self, path):
        self.path = path
        self.mtime = None

    def has_changed(self):
        if not os.path.isdir(self.path):
            return False

        mt = os.path.getmtime(self.path)
        if self.mtime is None or mt > self.mtime:
            return True

    def update(self):
        if not os.path.isdir(self.path):
            return

        self.mtime = os.path.getmtime(self.path)


class EmbeddingDatabase:
    def __init__(self):
        self.ids_lookup = {}
        self.word_embeddings = {}
        self.skipped_embeddings = {}
        self.expected_shape = -1
        self.embedding_dirs = {}
        self.previously_displayed_embeddings = ()

        # a cache to store loaded embeddings
        # key: embedding filename
        # value: embedding data
        self._loaded_embeddings = {}
        self._embedding_model_info: dict[str, ModelInfo] = {}

    def add_embedding_dir(self, path):
        self.embedding_dirs[path] = DirWithTextualInversionEmbeddings(path)

    def clear_embedding_dirs(self):
        self.embedding_dirs.clear()

    def register_embedding(self, embedding, model):
        return self.register_embedding_by_name(embedding, model, embedding.name)

    def register_embedding_by_name(self, embedding, model, name):
        ids = [0, 0, 0]  # model.cond_stage_model.tokenize([name])[0]
        first_id = ids[0]
        if first_id not in self.ids_lookup:
            self.ids_lookup[first_id] = []
        if name in self.word_embeddings:
            # remove old one from the lookup list
            lookup = [x for x in self.ids_lookup[first_id] if x[1].name!=name]
        else:
            lookup = self.ids_lookup[first_id]
        if embedding is not None:
            lookup += [(ids, embedding)]
        self.ids_lookup[first_id] = sorted(lookup, key=lambda x: len(x[0]), reverse=True)
        if embedding is None:
            # unregister embedding with specified name
            if name in self.word_embeddings:
                del self.word_embeddings[name]
            if len(self.ids_lookup[first_id])==0:
                del self.ids_lookup[first_id]
            return None
        self.word_embeddings[name] = embedding
        return embedding

    def get_expected_shape(self):
        devices.torch_npu_set_device()
        vec = shared.sd_model.cond_stage_model.encode_embedding_init_text(",", 1)
        return vec.shape[1]

    def load_from_model_info(self, model_info: ModelInfo):
        name = model_info.name_for_extra
        sha256 = model_info.sha256

        if sha256 not in self._loaded_embeddings:
            if not model_info.is_safetensors:
                data = torch.load(model_info.filename, map_location="cpu")
            else:
                data = safetensors.torch.load_file(model_info.filename, device="cpu")

            try:
                embedding = create_embedding_from_data(data, name, filename=model_info.filename, filepath=model_info.filename, sha256=sha256)
            except:
                logging.exception(f"Error loading embedding {model_info.filename}")
                self._loaded_embeddings[sha256] = None
                return

            # cache the loaded embedding
            self._loaded_embeddings[sha256] = embedding

        embedding = self._loaded_embeddings.get(sha256)
        if embedding:
            embedding.name = name
            embedding.filename = model_info.filename

            if self.expected_shape == -1 or self.expected_shape == embedding.shape:
                self.register_embedding(embedding, shared.sd_model)
            else:
                self.skipped_embeddings[name] = embedding


    # def load_from_dir(self, request, embdir):
    #     if not os.path.isdir(embdir.path):
    #         return

    #     for root, _, fns in os.walk(embdir.path, followlinks=True):
    #         for fn in fns:
    #             try:
    #                 fullfn = os.path.join(root, fn)

    #                 if os.stat(fullfn).st_size == 0:
    #                     continue

    #                 self.load_from_file(fullfn, fn)
    #             except Exception:
    #                 errors.report(f"Error loading embedding {fn}", exc_info=True)
    #                 continue


    def load_textual_inversion_embeddings(self, embedding_model_info: Mapping[str, ModelInfo], force_reload=False, sync_with_sd_model=True):
        embedding_model_info = dict(embedding_model_info)
        if not force_reload:
            if self._embedding_model_info == embedding_model_info:
                return

        self.ids_lookup.clear()
        self.word_embeddings.clear()
        self.skipped_embeddings.clear()

        if sync_with_sd_model:
            self.expected_shape = self.get_expected_shape()

        for model_info in embedding_model_info.values():
            self.load_from_model_info(model_info)

        # re-sort word_embeddings because load_from_dir may not load in alphabetic order.
        # using a temporary copy so we don't reinitialize self.word_embeddings in case other objects have a reference to it.
        sorted_word_embeddings = {e.name: e for e in sorted(self.word_embeddings.values(), key=lambda e: e.name.lower())}
        self.word_embeddings.clear()
        self.word_embeddings.update(sorted_word_embeddings)

        displayed_embeddings = (tuple(self.word_embeddings.keys()), tuple(self.skipped_embeddings.keys()))
        if shared.opts.textual_inversion_print_at_load and self.previously_displayed_embeddings != displayed_embeddings:
            self.previously_displayed_embeddings = displayed_embeddings
            print(f"Textual inversion embeddings loaded({len(self.word_embeddings)}): {', '.join(self.word_embeddings.keys())}")
            if self.skipped_embeddings:
                print(f"Textual inversion embeddings skipped({len(self.skipped_embeddings)}): {', '.join(self.skipped_embeddings.keys())}")

        self._embedding_model_info = embedding_model_info


    def find_embedding_at_position(self, tokens, offset):
        token = tokens[offset]
        possible_matches = self.ids_lookup.get(token, None)

        if possible_matches is None:
            return None, None

        for ids, embedding in possible_matches:
            if tokens[offset:offset + len(ids)] == ids:
                return embedding, len(ids)

        return None, None


def create_embedding(name, num_vectors_per_token, overwrite_old, init_text='*'):
    cond_model = shared.sd_model.cond_stage_model

    with devices.autocast():
        cond_model([""])  # will send cond model to GPU if lowvram/medvram is active

    #cond_model expects at least some text, so we provide '*' as backup.
    embedded = cond_model.encode_embedding_init_text(init_text or '*', num_vectors_per_token)
    vec = torch.zeros((num_vectors_per_token, embedded.shape[1]), device=devices.device)

    #Only copy if we provided an init_text, otherwise keep vectors as zeros
    if init_text:
        for i in range(num_vectors_per_token):
            vec[i] = embedded[i * int(embedded.shape[0]) // num_vectors_per_token]

    # Remove illegal characters from name.
    name = "".join( x for x in name if (x.isalnum() or x in "._- "))
    fn = os.path.join(shared.cmd_opts.embeddings_dir, f"{name}.pt")
    if not overwrite_old:
        assert not os.path.exists(fn), f"file {fn} already exists"

    embedding = Embedding(vec, name)
    embedding.step = 0
    embedding.save(fn)

    return fn


def create_embedding_from_data(data, name, filename='unknown embedding file', filepath=None, sha256=None):
    if 'string_to_param' in data:  # textual inversion embeddings
        param_dict = data['string_to_param']
        param_dict = getattr(param_dict, '_parameters', param_dict)  # fix for torch 1.12.1 loading saved file from torch 1.11
        assert len(param_dict) == 1, 'embedding file has multiple terms in it'
        emb = next(iter(param_dict.items()))[1]
        vec = emb.detach().to(devices.device, dtype=torch.float32)
        shape = vec.shape[-1]
        vectors = vec.shape[0]
    elif type(data) == dict and 'clip_g' in data and 'clip_l' in data:  # SDXL embedding
        vec = {k: v.detach().to(devices.device, dtype=torch.float32) for k, v in data.items()}
        shape = data['clip_g'].shape[-1] + data['clip_l'].shape[-1]
        vectors = data['clip_g'].shape[0]
    elif type(data) == dict and type(next(iter(data.values()))) == torch.Tensor:  # diffuser concepts
        assert len(data.keys()) == 1, 'embedding file has multiple terms in it'

        emb = next(iter(data.values()))
        if len(emb.shape) == 1:
            emb = emb.unsqueeze(0)
        vec = emb.detach().to(devices.device, dtype=torch.float32)
        shape = vec.shape[-1]
        vectors = vec.shape[0]
    else:
        raise Exception(f"Couldn't identify {filename} as neither textual inversion embedding nor diffuser concept.")

    embedding = Embedding(vec, name)
    embedding.step = data.get('step', None)
    embedding.sd_checkpoint = data.get('sd_checkpoint', None)
    embedding.sd_checkpoint_name = data.get('sd_checkpoint_name', None)
    embedding.vectors = vectors
    embedding.shape = shape

    if filepath:
        embedding.filename = filepath
        embedding.set_hash(hashes.sha256(filepath, "textual_inversion/" + name) or '')

    if sha256:
        embedding.set_hash(sha256)

    return embedding

