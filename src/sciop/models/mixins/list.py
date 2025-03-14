from typing import ClassVar, Self

from sqlalchemy import select
from sqlmodel import Session, SQLModel


class ListlikeMixin(SQLModel):
    """
    Mixin for models that are many-to-many joined to "primary" models,
    like tags, urls, etc. where the same tag or url is expected to be re-used many times
    """

    __value_column_name__: ClassVar[str] = None

    @classmethod
    def get_item(cls, value: str, session: Session) -> Self:
        """Get the row corresponding to the value of this item"""
        if cls.__value_column_name__ is None:
            raise ValueError("__value_column__ must be declared for ListlikeMixins")

        return session.exec(
            select(cls).where(getattr(cls, cls.__value_column_name__) == value)
        ).first()
