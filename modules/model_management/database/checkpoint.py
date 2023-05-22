from sqlalchemy import Column, Integer, String
from sqlalchemy import or_
from sqlalchemy.orm import Session, Query

from modules.model_management.database import Base


class CheckpointInfo(Base):
    __tablename__ = "checkpoints"

    id = Column(Integer, primary_key=True, index=True)

    filename = Column(String)
    name = Column(String, index=True)
    model_name = Column(String, index=True)
    title = Column(String, index=True)
    name_hash = Column(String, index=True)
    shorthash = Column(String, index=True)
    sha256 = Column(String, index=True)
    name_shorthash = Column(String, index=True)
    hash = Column(String, index=True)
    description = Column(String)

    name_for_extra = Column(String)
    mdata = Column(String)

    local_preview = Column(String)
    preview = Column(String)
    model_type = Column(String)


def list_checkpoints(session: Session, search_value: str = None, model_type: str = None, skip: int = 0,
                     limit: int = 20):
    query = session.query(CheckpointInfo)
    stmt = (
        _checkpoints_filter(query, search_value, model_type)
        .order_by(CheckpointInfo.name)
        .offset(skip)
        .limit(limit)
    )

    return session.scalars(stmt)


def count_checkpoints(session: Session, search_value: str = None, model_type: str = None) -> int:
    query = session.query(CheckpointInfo)
    query = _checkpoints_filter(query, search_value, model_type)

    return query.count()


def _checkpoints_filter(query: Query, search_value: str = None, model_type: str = None) -> Query:
    if model_type:
        query = query.filter(CheckpointInfo.model_type == model_type)

    if search_value:
        value = f'%{search_value}%'
        query = query.filter(
            or_(
                CheckpointInfo.name.like(value),
                CheckpointInfo.model_name.like(value),
                CheckpointInfo.title.like(value),
                CheckpointInfo.name_hash.like(value),
                CheckpointInfo.shorthash.like(value),
                CheckpointInfo.sha256.like(value),
                CheckpointInfo.name_shorthash.like(value),
                CheckpointInfo.hash.like(value),
            )
        )

    return query
