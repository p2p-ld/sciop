from typing import TYPE_CHECKING, Optional

from sqlalchemy import Select, case
from sqlmodel import Field, Relationship, select

from sciop.models.mixins import EditableMixin, ListlikeMixin, SearchableMixin, TableMixin
from sciop.types import IDField, MaxLenURL

if TYPE_CHECKING:
    from sciop.models import Dataset, Upload


class DatasetURLLink(TableMixin, EditableMixin, table=True):
    __tablename__ = "dataset_url_links"
    dataset_id: Optional[int] = Field(
        default=None, foreign_key="datasets.dataset_id", primary_key=True, index=True
    )
    url_id: Optional[int] = Field(
        default=None, foreign_key="urls.url_id", primary_key=True, index=True
    )


class UploadURLLink(TableMixin, EditableMixin, table=True):
    __tablename__ = "upload_url_links"
    upload_id: Optional[int] = Field(
        default=None, foreign_key="uploads.upload_id", primary_key=True, index=True
    )
    url_id: Optional[int] = Field(
        default=None, foreign_key="urls.url_id", primary_key=True, index=True
    )


class URL(ListlikeMixin, SearchableMixin, table=True):
    __tablename__ = "urls"
    __value_column_name__ = "url"
    __searchable__ = ["url"]

    url_id: IDField = Field(default=None, primary_key=True)
    url: MaxLenURL = Field(unique=True)
    datasets: list["Dataset"] = Relationship(back_populates="urls", link_model=DatasetURLLink)
    uploads: list["Upload"] = Relationship(back_populates="urls", link_model=UploadURLLink)

    @classmethod
    def search(cls, query: str) -> Select:
        """
        Urls that contain the query as typed come first, in lexicographic order,
        followed by the looser full text matches by rank.
        """
        matches = cls.search_statement(query).cte("matches")
        exact = cls.url.icontains(query, autoescape=True)
        return (
            select(cls)
            .join(matches, onclause=cls.url_id == matches.c.rowid)
            .order_by(exact.desc(), case((exact, 0), else_=matches.c.rank), cls.url)
        )
