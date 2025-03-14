import contextlib
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, Connection, Table, event, text
from sqlmodel import Field, SQLModel


class _FriedolinType(StrEnum):
    friedolin = "friedolin"


class _Friedolin(SQLModel, table=True):
    __tablename__ = "friedolin"
    friedolin: _FriedolinType = Field(
        "friedolin",
        primary_key=True,
        unique=True,
        sa_column_args=[
            CheckConstraint(text("friedolin = 'friedolin'"), name="the_friedolin_constraint")
        ],
    )


@event.listens_for(_Friedolin.__table__, "after_create")
def _make_friedolin(target: Table, connection: Connection, **kwargs: Any) -> None:
    with contextlib.suppress(Exception):
        # this can fail and we literally don't care
        connection.execute(target.insert().values(friedolin="friedolin"))
