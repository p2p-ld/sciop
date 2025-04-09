from typing import Any, ClassVar, Self, cast

from sqlalchemy import select
from sqlmodel import Session

from sciop.models.base import SQLModel


class ListlikeMixin(SQLModel):
    """
    Mixin for models that are many-to-many joined to "primary" models,
    like tags, urls, etc. where the same tag or url is expected to be re-used many times.

    These are expected to only have one
    """

    __value_column_name__: ClassVar[str | tuple[str, ...]] = None

    @classmethod
    def get_item(cls, value: str, session: Session, commit: bool = False, **kwargs: Any) -> Self:
        """
        Get or create the row corresponding to the value of this item.

        Args:
            value (str): The value to get or create.
            session (Session): SQLAlchemy session.
            commit (bool): If creating a new model, commit it to the database before returning
            **kwargs: If creating a new version of the model and kwargs are present,
                pass them to the newly created model
        """
        if cls.__value_column_name__ is None:
            raise ValueError("__value_column__ must be declared for ListlikeMixins")

        if isinstance(cls.__value_column_name__, tuple):
            raise NotImplementedError("tuple selection for listlike items is not implemented yet")

        existing = session.exec(
            select(cls).where(getattr(cls, cls.__value_column_name__) == value)
        ).scalar()
        if existing:
            return existing
        new_item = cls(**{cls.__value_column_name__: value, **kwargs})
        if commit:
            session.add(new_item)
            session.commit()
            session.refresh(new_item)
        return new_item

    @classmethod
    def get_items(cls, existing: list[Self], select: list[str | dict]) -> list[Self]:
        """
        Given a list of some already-existing versions of this class,
        subset them using a list of the `__value_column_name__` values,
        creating any new items that need to be
        """
        if cls.__value_column_name__ is None:
            raise ValueError("__value_column__ must be declared for ListlikeMixins")
        if isinstance(cls.__value_column_name__, str):
            select = cast(list[str], select)
            existing_map = {getattr(e, cls.__value_column_name__): e for e in existing}
            items = [
                existing_map.get(selected, cls(**{cls.__value_column_name__: selected}))
                for selected in select
            ]
        else:
            # a tuple
            select = cast(list[dict], select)
            existing_map = {
                tuple(getattr(e, colname) for colname in cls.__value_column_name__): e
                for e in existing
            }
            items = [
                existing_map.get(
                    tuple(selected[colname] for colname in cls.__value_column_name__),
                    cls(**selected),
                )
                for selected in select
            ]
        return items
