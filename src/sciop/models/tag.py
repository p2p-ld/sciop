from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship

from sciop.models.mixin import ListlikeMixin, TableMixin
from sciop.types import IDField, SlugStr

if TYPE_CHECKING:
    from sciop.models import Dataset


class DatasetTagLink(TableMixin, table=True):
    __tablename__ = "dataset_tag_link"
    dataset_id: Optional[int] = Field(
        default=None, foreign_key="dataset.dataset_id", primary_key=True
    )
    tag_id: Optional[int] = Field(default=None, foreign_key="tag.tag_id", primary_key=True)


class Tag(ListlikeMixin, table=True):
    __value_column_name__ = "tag"

    tag_id: IDField = Field(default=None, primary_key=True)
    datasets: list["Dataset"] = Relationship(back_populates="tags", link_model=DatasetTagLink)
    tag: SlugStr = Field(max_length=32, unique=True)
