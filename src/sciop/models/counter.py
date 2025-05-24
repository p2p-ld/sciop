from datetime import UTC, datetime
from typing import Optional

from pydantic import field_validator
from sqlmodel import Field, Session, select

from sciop.models.base import SQLModel
from sciop.types import IDField, UTCDateTime


def _normalize_path(path: str) -> str:
    if len(path) > 1 and path[-1] == "/":
        path = path[:-1]
    return path


class HitCount(SQLModel, table=True):
    """Hitcount for a page"""

    hit_count_id: IDField = Field(None, primary_key=True)
    created_at: Optional[UTCDateTime] = Field(default_factory=lambda: datetime.now(UTC))
    path: str = Field(..., index=True, unique=True)
    count: int = 0

    @classmethod
    @field_validator("path")
    def normalize_path(cls, path: str) -> str:
        """
        Except for the root /, remove trailing /'s
        """
        return _normalize_path(path)

    @classmethod
    def next(cls, path: str, session: Session) -> int:
        """
        Increment and return the next count for a path
        """
        path = _normalize_path(path)
        maybe_counter = session.exec(select(HitCount).where(HitCount.path == path)).first()
        counter = HitCount(path=path, count=0) if maybe_counter is None else maybe_counter
        count = counter.count
        return count

    @classmethod
    def writeback(cls, path: str, session: Session) -> None:
        path = _normalize_path(path)
        maybe_counter = session.exec(select(HitCount).where(HitCount.path == path)).first()
        counter = HitCount(path=path, count=0) if maybe_counter is None else maybe_counter
        counter.count = HitCount.count + 1
        session.add(counter)
        session.commit()
