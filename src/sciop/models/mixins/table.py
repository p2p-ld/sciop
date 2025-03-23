from datetime import UTC, datetime
from typing import Optional, get_origin

from pydantic import ConfigDict
from sqlalchemy.ext.hybrid import hybrid_method, hybrid_property
from sqlmodel import Field, SQLModel

from sciop.types import IDField, UTCDateTime


class TableMixin(SQLModel):
    """Mixin to add base elements to all tables"""

    created_at: Optional[UTCDateTime] = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: Optional[UTCDateTime] = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)},
    )

    model_config = ConfigDict(ignored_types=(hybrid_method, hybrid_property))

    @property
    def id(self) -> int:
        """
        The value of the primary key, `table_id` property.
        """
        for name, field in self.model_fields.items():
            try:
                if field.annotation is IDField or IDField in get_origin(field.annotation):
                    return getattr(self, name)
            except TypeError:
                continue
        raise AttributeError("No IDField found")


class TableReadMixin(SQLModel):
    """
    Mixin to add base elements to the read version of all tables
    """

    created_at: UTCDateTime
    updated_at: UTCDateTime
