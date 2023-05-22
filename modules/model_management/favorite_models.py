import logging

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

import modules.sd_models
from modules.model_management.database import get_db, repository
from modules.user import User

logger = logging.getLogger(__name__)


def setup_user_models_api(app):
    app.add_api_route("/internal/favorites/models",
                      add_favorite_model,
                      methods=["POST"],
                      response_model=AddFavoriteModelResponse)
    app.add_api_route("/internal/favorites/models/{model_type}",
                      get_favorite_model,
                      methods=["GET"],
                      response_model=GetFavoriteModelResponse)
    app.add_api_route("/internal/favorites/models/{model_type}/{model_title}",
                      delete_favorite_model,
                      methods=["DELETE"],
                      response_model=DeleteFavoriteModelResponse)


class AddFavoriteModelRequest(BaseModel):
    model_title: str = Field(default=None, title="ModelTitle", description="model title to favorite")
    model_type: str = Field(default=None, title="ModelType", description="model type to favorite")


class AddFavoriteModelResponse(BaseModel):
    ok: bool = Field(default=None, title="OK", description="request ok or not")
    model_title: str = Field(default=None, title="ModelTitle", description="model title to favorite")


def add_favorite_model(request: Request, req: AddFavoriteModelRequest, db: Session = Depends(get_db)):
    user = User.current_user(request)
    checkpoint_info = modules.sd_models.get_closet_checkpoint_match(req.model_title)
    if not checkpoint_info:
        raise HTTPException(status_code=404,
                            detail=f"not able to find a model with name='{req.model_title}', type='{req.model_type}"
                            )

    model_info = {
        'id': '',
        'model_type': req.model_type,
        'model_title': checkpoint_info.title,
        'model_hash': checkpoint_info.hash,
        'model_sha256': checkpoint_info.sha256,
        'model_name': checkpoint_info.name,
    }

    try:
        if repository.get_favorite_model_count_for_user(db, user.uid, req.model_type, model_info) > 0:
            raise HTTPException(status_code=400, detail=f"'{req.model_title}' is already favorited")
        repository.add_favorite_model_for_user(db, user.uid, model_info)
        return AddFavoriteModelResponse(ok=True, model_title=checkpoint_info.title)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f'failed to add favorite models: {e.__str__()}')
        raise HTTPException(status_code=500, detail="database error")


class GetFavoriteModelResponse(BaseModel):
    records: list = Field(default=[], title="ModelTitle", description="model title to favorite")
    total: int = Field(default=0, title="Total", description="total record count")
    current: int = Field(default=1, title="Current", description="current page index, start from 1")
    size: int = Field(default=20, title="Size", description="page size")


def get_favorite_model(request: Request,
                       model_type: str,
                       page: int = 1,
                       size: int = 20,
                       total: int = 0,
                       db: Session = Depends(get_db)):
    user = User.current_user(request)
    if page < 1:
        page = 1
    if size > 20:
        size = 20
    if total == 0:
        total = repository.get_favorite_model_count_for_user(db, user.uid, model_type, {})
    model_titles = []
    if total > 0:
        for record in repository.get_favorite_models_for_user(db,
                                                              user.uid,
                                                              model_type,
                                                              skip=(page - 1) * size,
                                                              limit=size):
            model_titles.append(record.model_title)
    return GetFavoriteModelResponse(
        records=model_titles,
        current=page,
        size=size,
        total=total
    )


def touch_favorite_model(request: Request, model_title: str):
    user = User.current_user(request)
    for db in get_db():
        repository.touch_favorite_models_for_user(db, user.uid, {'model_title': model_title})
        break


class DeleteFavoriteModelResponse(BaseModel):
    ok: bool = Field(default=False, title="OK", description="request ok or not")


def delete_favorite_model(request: Request, model_type: str, model_title: str, db: Session = Depends(get_db)):
    user = User.current_user(request)
    try:
        repository.remove_favorite_models_for_user(db, user.uid, {'model_title': model_title, 'model_type': model_type})
        return DeleteFavoriteModelResponse(ok=True)
    except Exception as e:
        logger.error(f'failed to add favorite models: {e.__str__()}')
        raise HTTPException(status_code=500, detail="database error")
