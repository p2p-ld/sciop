from pydantic import Field
from pydantic.fields import FieldInfo

from sciop.models.base import SQLModel


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

    TODO: Consider merging `models.api.SearchParams.apply_sort` here?
    """

    __sortable__: tuple[SortableCol] = tuple()

    @classmethod
    def get_sortable_cols(cls, review: bool = False) -> list[SortableCol]:
        """
        Get the description of sortable columns for this model

        Args:
            review (bool): Whether to include the two review button column placeholders
        """

        cols = [
            col.merge_field(cls.model_fields[col.name]) if col.name else col
            for col in cls.__sortable__
        ]
        if review:
            cols.extend([SortableCol(), SortableCol()])

        return cols
