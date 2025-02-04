from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class TableMixin(SQLModel):
    """Mixin to add base elements to all tables"""

    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: Optional[datetime] = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)},
    )


class TableReadMixin(SQLModel):
    """
    Mixin to add base elements to the read version of all tables
    """

    id: int
    created_at: datetime
    updated_at: datetime
