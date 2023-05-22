import datetime

from sqlalchemy import select, update, delete, func
from sqlalchemy.orm import Session
from modules.model_management.database import Base
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, DateTime


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
    metadata = Column(String)

    local_preview = Column(String)
    preview = Column(String)


def list_checkpoints(session: Session, skip: int = 0, limit: int = 20):
    stmt = select(
        CheckpointInfo
    ).order_by(
        CheckpointInfo.name,
    ).offset(
        skip,
    ).limit(
        limit,
    )
    return session.scalars(stmt)
