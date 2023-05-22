from datetime import datetime

from modules.model_management.database import Base
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime

import datetime

from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session


class FavoriteModel(Base):
    __tablename__ = "favorite_models"
    id = Column(Integer, primary_key=True, index=True)

    created_at = Column(DateTime)
    updated_at = Column(DateTime, onupdate=datetime.datetime.now)
    deleted_at = Column(DateTime, default=None, index=True)
    last_accessed_at = Column(DateTime, index=True)

    user_id = Column(String, index=True)

    model_id = Column(Integer, index=True)

    model_title = Column(String, index=True)
    model_type = Column(String)


def _stmt_where(stmt, user_id: str, model_info: dict):
    stmt = stmt.where(
        FavoriteModel.user_id == user_id,
    )
    model_id = model_info.get('id', '')
    model_title = model_info.get('model_title', '')
    if model_id:
        stmt = stmt.where(FavoriteModel.model_id == model_id)
    elif model_title:
        stmt = stmt.where(FavoriteModel.model_title == model_title)
    return stmt


def get_favorite_models_for_user(session: Session, user_id: str, model_type: str, skip: int = 0, limit: int = 20):
    stmt = select(
        FavoriteModel
    ).where(
        FavoriteModel.user_id == user_id,
        FavoriteModel.model_type == model_type,
    ).order_by(
        FavoriteModel.last_accessed_at,
    ).offset(
        skip,
    ).limit(
        limit,
    )
    return session.scalars(stmt)


def get_favorite_model_count_for_user(session: Session, user_id: str, model_type: str, model_info: dict):
    stmt = select(
        func.count(FavoriteModel.id),
    ).where(
        FavoriteModel.model_type == model_type,
    ).order_by(
        FavoriteModel.last_accessed_at,
    )
    stmt = _stmt_where(stmt, user_id, model_info)
    return session.scalar(stmt)


def add_favorite_model_for_user(session: Session, user_id: str, model_info: dict):
    model_id = model_info.get('id', '')
    model_title = model_info.get('model_title', '')
    model_type = model_info.get('model_type', '')
    if not model_id and (not model_title or not model_type):
        raise Exception('model_id and model_file are present')

    favorite = FavoriteModel(
        created_at=datetime.datetime.now(),
        updated_at=datetime.datetime.now(),
        last_accessed_at=datetime.datetime.now(),
        user_id=user_id,
        model_title=model_title,
        model_type=model_type
    )
    session.add(favorite)
    session.commit()
    return favorite


def remove_favorite_models_for_user(session: Session, user_id: str, model_info: dict):
    stmt = update(
        FavoriteModel
    )
    stmt = _stmt_where(
        stmt, user_id, model_info
    ).values(
        deleted_at=datetime.datetime.now()
    )
    print(stmt)
    session.execute(stmt)
    session.commit()


def touch_favorite_models_for_user(session: Session, user_id: str, model_info: dict):
    stmt = update(
        FavoriteModel
    )
    stmt = _stmt_where(
        stmt, user_id, model_info
    ).values(
        last_accessed_at=datetime.datetime.now()
    )
    print(stmt)
    session.execute(stmt)
    session.commit()
