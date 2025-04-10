import sys
from enum import StrEnum
from typing import ClassVar, Self

from sqlalchemy import select
from sqlmodel import Session

from sciop.models.base import SQLModel


class EnumTableMixin(SQLModel):
    """Enum table mixin for method for ensuring all enum values exist"""

    __enum_column_name__: ClassVar[str] = None
    """Column that has the enum values for which rows should be created"""

    @classmethod
    def enum_class(cls) -> StrEnum:
        """Get the enum itself used in the enum column"""
        return cls.model_fields[cls.__enum_column_name__].annotation

    @classmethod
    def ensure_enum_values(cls, session: Session) -> None:
        if cls.__enum_column_name__ is None:
            raise ValueError("__enum_column_name__ must be declared for EnumTableMixins")

        enum = cls.enum_class()
        for item in enum:
            stmt = select(cls).where(getattr(cls, cls.__enum_column_name__) == item.value)
            existing_enum_row = session.exec(stmt).first()
            if not existing_enum_row:
                db_item = cls(**{cls.__enum_column_name__: item.value})
                session.add(db_item)

        session.commit()

    @classmethod
    def get_item(cls, item: str | StrEnum, session: Session) -> Self:
        """Get the row corresponding to this enum item"""
        if isinstance(item, str) and sys.version_info < (3, 12):
            if item not in cls.enum_class().__members__:
                raise KeyError(f"No such item {item} exists in {cls.enum_class()}")
        elif item not in cls.enum_class():
            raise KeyError(f"No such item {item} exists in {cls.enum_class()}")

        item = session.exec(
            select(cls).where(getattr(cls, cls.__enum_column_name__) == item)
        ).scalar()
        return item
