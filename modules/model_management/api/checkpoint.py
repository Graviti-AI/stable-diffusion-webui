import json
import time

from fastapi import Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from modules.model_management.database import checkpoint as checkpoint_repository
from modules.model_management.database import get_db


def _get_app(app):
    import modules.shared
    if app:
        return app
    if modules.shared.demo:
        return modules.shared.demo
    return None


def setup_checkpoint_api(app):
    while True:
        app = _get_app(app)
        if app:
            break
        time.sleep(10)
    app.add_api_route("sd_extra_networks/update_page",
                      list_checkpoint,
                      methods=["GET"],
                      response_model=ListCheckpointResponse)


class CheckpointInfo:
    def __init__(self, checkpoint_info: checkpoint_repository.CheckpointInfo):
        self.filename = checkpoint_info.filename
        self.name = checkpoint_info.name
        self.name_for_extra = checkpoint_info.name_for_extra
        self.model_name = checkpoint_info.model_name
        self.hash = checkpoint_info.hash
        self.sha256 = checkpoint_info.sha256
        self.shorthash = self.sha256[0:10] if self.sha256 else None
        self.title = self.name if self.shorthash is None else f'{self.name} [{self.shorthash}]'
        self.ids = [self.hash, self.model_name, self.title, self.name, f'{self.name} [{self.hash}]',
                    ] + (
                       [self.shorthash, self.sha256, f'{self.name} [{self.shorthash}]'] if self.shorthash else []
                   )
        self.metadata = json.loads(checkpoint_info.metadata)


class ListCheckpointResponse(BaseModel):
    page: int = Field(default=1, title="PageIndex", description="page index")
    totoal_count: int = Field(default=0, title="TotalCount", description="total count")
    model_list: list[CheckpointInfo] = Field(default=[], title="ModelList", description="model list")
    allow_negative_prompt: bool = Field(default=False, title="allow_negative_prompt",
                                        description="allow_negative_prompt")


def list_checkpoint(request: Request,
                    model_type,
                    search_value,
                    page=1,
                    page_size=14,
                    need_refresh=False,
                    db: Session = Depends(get_db)):
    if page < 1:
        page = 1
    if size > 20:
        size = 20

    result = list()
    for record in checkpoint_repository.list_checkpoints(db, skip=(page - 1) * size, limit=size):
        result.append(CheckpointInfo(record))
