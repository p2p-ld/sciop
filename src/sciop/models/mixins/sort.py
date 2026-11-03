from typing import Optional

import sqlalchemy as sqla
from pydantic import Field
from pydantic.fields import FieldInfo

from sciop.helpers.type import unwrap
from sciop.models.base import SQLModel
from sciop.types import SortableStrEnum


class SortableCol(SQLModel):
    """
    Configuration of a sortable column
    """

    name: str = Field(
        "", description="The name of the column in the db. Can be empty for a spacer column"
    )
    title: str | None = Field(
        None,
        description="What to display in the column header. "
        "Can be raw HTML or a string. "
        "If None, use the field title, if present, "
        "otherwise use the name.",
    )
    tooltip: str | None = Field(None, description="Text to display as a hover tooltip")
    model: type[SQLModel] | str | None = Field(
        None,
        description="The model that has the column, if it isn't the model being sorted, "
        "e.g. a column from a joined table. "
        "Can be the name of a table model, for models that aren't defined yet.",
        exclude=True,
    )

    def merge_field(self, info: FieldInfo) -> "SortableCol":
        """
        Merge information from field, if needed
        """
        if self.title is None:
            if info.title:
                self.title = info.title
            else:
                self.title = self.name
        return self


class SortMixin(SQLModel):
    """
    Declare how a model's columns can be sorted.
    """

    __sortable__: tuple[SortableCol, ...] = tuple()

    @classmethod
    def get_sortable_cols(cls, review: bool = False) -> list[SortableCol]:
        """
        Get the description of sortable columns for this model

        Args:
            review (bool): Whether to include the two review button column placeholders
        """
        cols = []
        for col in cls.__sortable__:
            fields = cls._sort_model(col.name).model_fields
            cols.append(col.merge_field(fields[col.name]) if col.name in fields else col)
        if review:
            cols.extend([SortableCol(), SortableCol()])

        return cols

    @classmethod
    def sort_column(cls, name: str) -> Optional[sqla.ColumnElement]:
        """
        The column or expression to sort by for a column name,
        from the model declared in its :class:`.SortableCol`, if any, otherwise this model.

        Returns ``None`` if there is no such column.
        """
        model = cls._sort_model(name)
        col = getattr(model, name, None)
        if col is None:
            return None

        try:
            # try to get special types, but don't panic if we can't.
            # that just means it's not a special type we know about!
            annotation = unwrap(model.model_fields[name].annotation)
            if issubclass(annotation, SortableStrEnum):
                col = annotation.case_statement(col)
        except (TypeError, KeyError):
            pass
        return col

    @classmethod
    def _sort_model(cls, name: str) -> type[SQLModel]:
        """The model that has the sortable column with this name"""
        model = next((col.model for col in cls.__sortable__ if col.name == name), None)
        if model is None:
            return cls
        if isinstance(model, str):
            return next(
                mapper.class_
                for mapper in sqla.inspect(cls).registry.mappers
                if mapper.class_.__name__ == model
            )
        return model
