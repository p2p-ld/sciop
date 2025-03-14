from typing import TYPE_CHECKING, Optional

from sqlmodel import Field, Relationship, SQLModel

from sciop.models.mixins import ListlikeMixin, TableMixin, EditableMixin
from sciop.types import IDField, SlugStr

if TYPE_CHECKING:
    from sciop.models import Dataset


class DatasetTagLink(TableMixin, EditableMixin, table=True):
    __tablename__ = "dataset_tag_links"
    dataset_id: Optional[int] = Field(
        default=None, foreign_key="datasets.dataset_id", primary_key=True
    )
    tag_id: Optional[int] = Field(default=None, foreign_key="tags.tag_id", primary_key=True)


class Tag(ListlikeMixin, table=True):
    __tablename__ = "tags"
    __value_column_name__ = "tags"

    tag_id: IDField = Field(default=None, primary_key=True)
    datasets: list["Dataset"] = Relationship(back_populates="tags", link_model=DatasetTagLink)
    tag: SlugStr = Field(max_length=32, unique=True)


class TagSummary(SQLModel):
    tag: SlugStr = Field(max_length=32)
    n_datasets: int = Field(0)
    n_uploads: int = Field(0)
