#!/usr/bin/env python3

import json
import os
from typing import Literal, Protocol

from fastapi import Request
from pydantic import BaseModel

from modules.paths import get_binary_path, get_config_path
from modules.user import User


class ModelInfoProtocal(Protocol):
    @property
    def filename(self) -> str:
        ...

    @property
    def is_safetensors(self) -> bool:
        ...


class ModelInfo(BaseModel):
    model_type: Literal["checkpoint", "embedding", "hypernetwork", "lora"]
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
        return os.path.splitext(self.name)[-1] == ".safetensors"

    def calculate_shorthash(self) -> str:
        return self.shorthash

    def check_file_existence(self) -> None:
        assert os.path.exists(self.filename)
        assert self.config_filename is None or os.path.exists(self.config_filename)


class AllModelInfo:
    def __init__(self, data: str) -> None:
        self._models = [ModelInfo(**item) for item in json.loads(data)]

        self.checkpoint_models: dict[str, ModelInfo] = {}
        self.embedding_models: dict[str, ModelInfo] = {}
        self.hypernetwork_models: dict[str, ModelInfo] = {}
        self.lora_models: dict[str, ModelInfo] = {}

        for model_info in self._models:
            match model_info.model_type:
                case "checkpoint":
                    self.checkpoint_models[model_info.title] = model_info
                case "embedding":
                    self.embedding_models[model_info.name_for_extra] = model_info
                case "hypernetwork":
                    self.hypernetwork_models[model_info.name_for_extra] = model_info
                case "lora":
                    self.lora_models[model_info.name_for_extra] = model_info

    def is_xyz_plot_enabled(self) -> bool:
        return any(item.source == "xyz_plot" for item in self._models)

    def check_file_existence(self) -> None:
        for model in self._models:
            model.check_file_existence()


class DatabaseAllModelInfo(AllModelInfo):
    def __init__(self, request: Request) -> None:
        from scripts.model_hijack.favorite_model import (
            FavoriteModelDatabase,
            FavoriteModelDatabaseByTitle,
        )

        user_id = User.current_user(request).uid

        self.checkpoint_models = FavoriteModelDatabaseByTitle(user_id, "checkpoint")
        self.embedding_models = FavoriteModelDatabase(user_id, "embedding")
        self.hypernetwork_models = FavoriteModelDatabase(user_id, "hypernetwork")
        self.lora_models = FavoriteModelDatabase(user_id, "lora")

    def is_xyz_plot_enabled(self) -> bool:
        return False

    def check_file_existence(self) -> None:
        return None
