#!/usr/bin/env python3

import json
import os
from typing import TYPE_CHECKING, Any, Literal, Protocol

import gradio as gr
from fastapi import FastAPI
from pydantic import BaseModel

from modules import script_callbacks
from modules.paths import get_binary_path, get_config_path

if TYPE_CHECKING:
    from modules.processing import StableDiffusionProcessing

MODEL_INFO_KEY = "_AllModelInfo"


_USED_MODEL_CONFIG: dict[str, Any] = {
    "CHECKPOINT": [("Refiner", True)],
    "LORA": "Lora hashes",
    "HYPERNETWORK": "Hypernetwork hashes",
    "EMBEDDING": "TI hashes",
}


def register_used_model_checkpoint_key(key: str, is_short: bool) -> None:
    _USED_MODEL_CONFIG["CHECKPOINT"].append((key, is_short))


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

        self._checkpoint_models: list[ModelInfo] = []
        self.embedding_models: dict[str, ModelInfo] = {}
        self.hypernetwork_models: dict[str, ModelInfo] = {}
        self.lora_models: dict[str, ModelInfo] = {}

        for model_info in self._models:
            match model_info.model_type:
                case "CHECKPOINT":
                    self._checkpoint_models.append(model_info)
                case "EMBEDDING":
                    self.embedding_models[model_info.name_for_extra] = model_info
                case "HYPERNETWORK":
                    self.hypernetwork_models[model_info.name_for_extra] = model_info
                case "LORA" | "LYCORIS":
                    self.lora_models[model_info.name_for_extra] = model_info

    def get_checkpoint_by_title(self, title: str) -> ModelInfo | None:
        for model_info in self._checkpoint_models:
            if model_info.title == title:
                return model_info

        return None

    def get_checkpoint_by_short_title(self, short_title: str) -> ModelInfo | None:
        for model_info in self._checkpoint_models:
            if model_info.short_title == short_title:
                return model_info

        return None

    def get_checkpoint_by_hash(self, sha256: str) -> ModelInfo | None:
        for model_info in self._checkpoint_models:
            if model_info.sha256.startswith(sha256):
                return model_info

        return None

    def is_xyz_plot_enabled(self) -> bool:
        return any(item.source == "xyz_plot" for item in self._models)

    def check_file_existence(self) -> None:
        for model in self._models:
            model.check_file_existence()

    def get_used_model_ids(self, p: "StableDiffusionProcessing") -> list[int]:
        used_model_ids = []
        extra_params = p.extra_generation_params

        for model_type, config in _USED_MODEL_CONFIG.items():
            match model_type:
                case "CHECKPOINT":
                    short_title = f"{p.sd_model_name} [{p.sd_model_hash}]"
                    model_info = self.get_checkpoint_by_short_title(short_title)
                    if model_info is None:
                        raise KeyError(short_title)

                    used_model_ids.append(model_info.id)

                    for key, is_short in config:
                        value = extra_params.get(key)
                        if not value:
                            continue

                        model_info = (
                            self.get_checkpoint_by_short_title(value)
                            if is_short
                            else self.get_checkpoint_by_title(value)
                        )
                        if model_info is None:
                            raise KeyError(value)

                        used_model_ids.append(model_info.id)

                    continue

                case "LORA":
                    models = self.lora_models
                    value = extra_params.get(config)

                case "HYPERNETWORK":
                    models = self.hypernetwork_models
                    value = extra_params.get(config)

                case "EMBEDDING":
                    models = self.embedding_models
                    value = extra_params.get(config)

                case _:
                    raise ValueError(f"Unknown model type: '{model_type}'")

            if not value:
                continue

            used_model_ids.extend(
                models[item.split(":", 1)[0].strip()].id for item in value.split(",")
            )

        return list(dict.fromkeys(used_model_ids))


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
