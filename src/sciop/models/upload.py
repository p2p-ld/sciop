from typing import Optional
from urllib.parse import urljoin

import sqlalchemy as sqla
from pydantic import field_validator
from sqlalchemy import ColumnElement, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.attributes import AttributeEventToken
from sqlmodel import Field, Relationship

from sciop.config import config
from sciop.models import Account, AuditLog, Dataset, DatasetPart, TorrentFile
from sciop.models.dataset import UploadDatasetPartLink
from sciop.models.mixins import (
    ModerableMixin,
    SearchableMixin,
    TableMixin,
    TableReadMixin,
    EditableMixin,
)
from sciop.services.markdown import render_db_fields_to_html
from sciop.types import IDField, InputType, SlugStr


class UploadBase(ModerableMixin):
    """
    A copy of a dataset
    """

    method: Optional[str] = Field(
        None,
        description="""Description of how the dataset was acquired. Markdown input is supported.""",
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
        max_length=8192,
    )
    method_html: Optional[str] = Field(
        "",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
        max_length=16384,
    )
    description: Optional[str] = Field(
        None,
        description="Any additional information about this dataset upload. "
        "Markdown input is supported.",
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
        max_length=8192,
    )
    description_html: Optional[str] = Field(
        "",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
        max_length=16384,
    )

    @property
    def human_size(self) -> str:
        """Human-sized string representation of the torrent size"""
        return self.torrent.human_size

    @property
    def human_torrent_size(self) -> str:
        """Human-sized string representation of the size of the torrent itself"""
        return self.torrent.human_torrent_size

    @property
    def download_path(self) -> str:
        """Location where the torrent can be downloaded relative to site root"""
        return self.torrent.download_path

    @property
    def absolute_download_path(self) -> str:
        """Download path including the site root"""
        return urljoin(config.base_url, self.download_path)

    @property
    def file_name(self) -> str:
        return self.torrent.file_name

    @property
    def short_hash(self) -> Optional[str]:
        if self.torrent:
            return self.torrent.short_hash
        return None

    @property
    def infohash(self) -> Optional[str]:
        if self.torrent:
            return self.torrent.infohash
        return None

    @property
    def rss_description(self) -> str:
        """
        String to be used in the RSS description for this upload

        Todo: dump all model details here programmatically instead of hardcoded like this
        """
        return f"""
            <p>
            <strong>Dataset:</strong> 
              <a href="{config.base_url}/datasets/{self.dataset.slug}">
                {config.base_url}/datasets/{self.dataset.slug}
              </a>
            </p>
            <p>
            <strong>Upload:</strong> 
              <a href="{config.base_url}/uploads/{self.infohash}">
              {config.base_url}/uploads/{self.infohash}
              </a>
            </p>
            <p>
            <strong>Description:</strong> {self.description}
            </p>
            <p>
            <strong>Method:</strong> {self.method}
            </p>
        """


class Upload(UploadBase, TableMixin, SearchableMixin, EditableMixin, table=True):
    __tablename__ = "uploads"
    __searchable__ = ["description", "method"]

    upload_id: IDField = Field(default=None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="datasets.dataset_id")
    dataset: Dataset = Relationship(back_populates="uploads")
    dataset_parts: list[DatasetPart] = Relationship(
        back_populates="uploads", link_model=UploadDatasetPartLink
    )
    account_id: Optional[int] = Field(default=None, foreign_key="accounts.account_id")
    account: Account = Relationship(back_populates="submissions")
    torrent: Optional["TorrentFile"] = Relationship(
        back_populates="upload", sa_relationship_kwargs={"lazy": "selectin"}
    )

    audit_log_target: list["AuditLog"] = Relationship(back_populates="target_upload")

    @hybrid_property
    def seeders(self) -> int:
        return self.torrent.seeders

    @seeders.inplace.expression
    def _seeders(self) -> ColumnElement[Optional[int]]:
        return self.torrent._seeders()

    @hybrid_property
    def leechers(self) -> int:
        return self.torrent.leechers

    @seeders.inplace.expression
    def _leechers(self) -> ColumnElement[Optional[int]]:
        return self.torrent._leechers()

    @hybrid_property
    def is_visible(self) -> bool:
        """
        Whether the dataset should be displayed and included in feeds.
        Override parent method to include uploads that have a torrent file
        """
        return self.is_approved and not self.is_removed and self.torrent is not None

    @is_visible.inplace.expression
    @classmethod
    def _is_visible(cls) -> ColumnElement[bool]:
        return sqla.and_(
            cls.is_approved == True, cls.is_removed == False, cls.torrent != None  # noqa: E711
        )


@event.listens_for(Upload.is_removed, "set")
def _upload_remove_torrent(
    target: Upload, value: bool, oldvalue: bool, initiator: AttributeEventToken
) -> None:
    """Remove an associated torrent when the"""
    if value and not oldvalue and oldvalue is not None and target.torrent:
        from sciop.db import get_session

        with next(get_session()) as session:
            torrent = session.merge(target.torrent)
            session.delete(torrent)
            session.commit()


event.listen(Upload, "before_update", render_db_fields_to_html("description", "method"))
event.listen(Upload, "before_insert", render_db_fields_to_html("description", "method"))


class UploadRead(UploadBase, TableReadMixin):
    """Version of datasaet upload returned when reading"""

    dataset: Optional[SlugStr] = None
    torrent: Optional["TorrentFile"] = None
    seeders: Optional[int] = None
    leechers: Optional[int] = None

    @field_validator("dataset", mode="before")
    def extract_slug(cls, value: Optional["Dataset"] = None) -> SlugStr:
        if value is not None:
            value = value.slug
        return value


class UploadCreate(UploadBase):
    """Dataset upload for creation, excludes the is_approved param"""

    torrent_infohash: str = Field(
        min_length=40, max_length=64, description="Infohash of the torrent file, v1 or v2"
    )
    part_slugs: Optional[list[SlugStr]] = Field(
        default=None,
        title="Dataset Parts",
        description="Parts of a dataset that this upload corresponds to",
    )
