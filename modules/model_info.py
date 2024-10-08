#!/usr/bin/env python3

import json
import os
from typing import Literal, Protocol

import gradio as gr
from fastapi import FastAPI, Request
from pydantic import BaseModel

from modules import script_callbacks
from modules.paths import get_binary_path, get_config_path
from modules.user import User

MODEL_INFO_KEY = "_AllModelInfo"


class ModelInfoProtocal(Protocol):
    @property
    def filename(self) -> str:
        ...

    @property
    def is_safetensors(self) -> bool:
        ...


class ModelInfo(BaseModel):
    id: int
    model_type: Literal["CHECKPOINT", "EMBEDDING", "HYPERNETWORK", "LORA", "LYCORIS"]
    base: Literal["SD1", "SD2", "SDXL", "PONY", "SD3", "FLUX"]
    source: str | None
    name: str
    sha256: str
    config_sha256: str | None

    @property
    def name_for_extra(self) -> str:
        return os.path.splitext(self.name)[0]

    @property
    def model_name(self) -> str:
        return self.name_for_extra

    @property
    def title(self) -> str:
        return f"{self.name} [{self.shorthash}]"

    @property
    def short_title(self) -> str:
        return f"{self.name_for_extra} [{self.shorthash}]"

    @property
    def filename(self) -> str:
        return str(get_binary_path(self.sha256))

    @property
    def shorthash(self) -> str:
        return self.sha256[:10]

    @property
    def config_filename(self) -> str | None:
        if not self.config_sha256:
            return None

        return str(get_config_path(self.config_sha256))

    @property
    def is_safetensors(self) -> bool:
        return os.path.splitext(self.name)[-1].lower() == ".safetensors"

    def calculate_shorthash(self) -> str:
        return self.shorthash

    def check_file_existence(self) -> None:
        assert os.path.exists(self.filename), f"Model '{self.title}' does not exist"
        assert self.config_filename is None or os.path.exists(
            self.config_filename
        ), f"Config '{self.config_sha256}' for model '{self.title}' does not exist"


class AllModelInfo:
    def __init__(self, data: str) -> None:
        self._models = [ModelInfo(**item) for item in json.loads(data)]

        self.checkpoint_models: dict[str, ModelInfo] = {}
        self.embedding_models: dict[str, ModelInfo] = {}
        self.hypernetwork_models: dict[str, ModelInfo] = {}
        self.lora_models: dict[str, ModelInfo] = {}

        for model_info in self._models:
            match model_info.model_type:
                case "CHECKPOINT":
                    self.checkpoint_models[model_info.title] = model_info
                case "EMBEDDING":
                    self.embedding_models[model_info.name_for_extra] = model_info
                case "HYPERNETWORK":
                    self.hypernetwork_models[model_info.name_for_extra] = model_info
                case "LORA" | "LYCORIS":
                    self.lora_models[model_info.name_for_extra] = model_info

    def is_xyz_plot_enabled(self) -> bool:
        return any(item.source == "xyz_plot" for item in self._models)

    def check_file_existence(self) -> None:
        for model in self._models:
            model.check_file_existence()

    def get_used_model_ids(self, used_models: dict[str, list[str]]) -> list[int]:
        model_ids = []

        for model_type, names in used_models.items():
            match model_type:
                case "EMBEDDING":
                    model_ids.extend(self.embedding_models[name].id for name in names)
                case "HYPERNETWORK":
                    model_ids.extend(self.hypernetwork_models[name].id for name in names)
                case "LORA":
                    model_ids.extend(self.lora_models[name].id for name in names)

        return model_ids


# class DatabaseAllModelInfo(AllModelInfo):
#     def __init__(self, request: Request) -> None:
#         from scripts.model_hijack.favorite_model import (
#             FavoriteModelDatabase,
#             FavoriteModelDatabaseByTitle,
#         )

#         user_id = User.current_user(request).uid

#         self.checkpoint_models = FavoriteModelDatabaseByTitle(user_id, "checkpoint")
#         self.embedding_models = FavoriteModelDatabase(user_id, "embedding")
#         self.hypernetwork_models = FavoriteModelDatabase(user_id, "hypernetwork")
#         self.lora_models = FavoriteModelDatabase(user_id, "lora")

#     def is_xyz_plot_enabled(self) -> bool:
#         return False

#     def check_file_existence(self) -> None:
#         return None


class FilesExistenceRequest(BaseModel):
    models: list[str]
    configs: list[str]


class FilesExistenceResponse(BaseModel):
    models: list[bool]
    configs: list[bool]


def check_files_existence_by_sha256(body: FilesExistenceRequest) -> FilesExistenceResponse:
    return FilesExistenceResponse(
        models=[get_binary_path(sha256.lower()).exists() for sha256 in body.models],
        configs=[get_config_path(sha256.lower()).exists() for sha256 in body.configs],
    )


def _setup_model_api(_: gr.Blocks, app: FastAPI):
    app.add_api_route(
        "/internal/files-existence",
        check_files_existence_by_sha256,
        methods=["POST"],
        response_model=FilesExistenceResponse,
    )


script_callbacks.on_app_started(_setup_model_api)
