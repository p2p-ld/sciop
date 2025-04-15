import urllib.parse
from typing import TYPE_CHECKING, Optional, Self, cast
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
    EditableMixin,
    ModerableMixin,
    SearchableMixin,
    TableMixin,
    TableReadMixin,
    all_optional,
)
from sciop.services.markdown import render_db_fields_to_html
from sciop.types import FileName, IDField, InputType, SlugStr

if TYPE_CHECKING:
    from sqlmodel import Session


class UploadBase(ModerableMixin):
    """
    A copy of a dataset
    """

    method: Optional[str] = Field(
        None,
        title="Method",
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
        title="Description",
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
    def short_hash(self) -> Optional[str]:
        if self.torrent:
            return self.torrent.short_hash
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

    @property
    def n_files(self) -> int:
        return self.torrent.n_files

    @property
    def seeders(self) -> int:
        return self.torrent.seeders

    @property
    def leechers(self) -> int:
        return self.torrent.leechers


class Upload(UploadBase, TableMixin, SearchableMixin, EditableMixin, table=True):
    __tablename__ = "uploads"
    __searchable__ = {
        "description": 2.0,
        "method": 1.0,
    }

    upload_id: IDField = Field(default=None, primary_key=True)
    dataset_id: Optional[int] = Field(default=None, foreign_key="datasets.dataset_id", index=True)
    dataset: Dataset = Relationship(back_populates="uploads")
    dataset_parts: list[DatasetPart] = Relationship(
        back_populates="uploads", link_model=UploadDatasetPartLink
    )
    account_id: Optional[int] = Field(default=None, foreign_key="accounts.account_id", index=True)
    account: Account = Relationship(back_populates="submissions")
    torrent: Optional["TorrentFile"] = Relationship(
        back_populates="upload", sa_relationship_kwargs={"lazy": "selectin"}
    )

    audit_log_target: list["AuditLog"] = Relationship(back_populates="target_upload")

    @property
    def infohash(self) -> Optional[str]:
        if self.torrent:
            return self.torrent.infohash
        return None

    @property
    def file_name(self) -> str:
        return self.torrent.file_name

    @property
    def magnet_link(self) -> str:
        magnet_string = "magnet:?xt="
        if self.torrent.v1_infohash:
            magnet_string += f"urn:btih:{self.torrent.v1_infohash}"
            if self.torrent.v2_infohash:
                magnet_string+= "&xt="
        if self.torrent.v2_infohash:
            magnet_string+=f"urn:btmh:{self.torrent.v2_infohash}"
        magnet_string+=f"&dn={urllib.parse.quote_plus(self.torrent.file_name)}"
        for tracker in self.torrent.tracker_links:
            magnet_string += "&tr="+urllib.parse.quote_plus(tracker.tracker.announce_url)
        return magnet_string



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
    def size(self) -> int:
        return self.torrent.total_size

    @size.inplace.expression
    def _size(self) -> ColumnElement[int]:
        return cast(
            "ColumnElement[int]",
            TorrentFile.total_size,
        )

    @hybrid_property
    def n_files(self) -> int:
        return self.torrent.n_files

    @n_files.inplace.expression
    def _n_files(self) -> ColumnElement[int]:
        return cast(
            "ColumnElement[int]",
            TorrentFile.n_files,
        )

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

    def update(self, session: "Session", new: "UploadUpdate", commit: bool = False) -> Self:
        from sciop import crud

        updated = new.model_dump(exclude_unset=True)
        if "infohash" in updated:
            infohash = updated.pop("infohash")
            self.torrent = crud.get_torrent_from_infohash(session=session, infohash=infohash)
        if "file_name" in updated:
            self.torrent.file_name = updated.pop("file_name")
        if "part_slugs" in updated:
            part_slugs = updated.pop("part_slugs")
            existing = {p.part_slug: p for p in self.dataset_parts}
            added = set(part_slugs) - set(existing.keys())
            to_add = {
                p.part_slug: p
                for p in crud.get_dataset_parts(
                    session=session, dataset_slug=self.dataset.slug, dataset_part_slugs=list(added)
                )
            }
            created = {
                p.part_slug: p
                for p in [
                    DatasetPart(part_slug=slug, dataset=self.dataset)
                    for slug in added - set(to_add.keys())
                ]
            }
            self.dataset_parts = list({**existing, **to_add, **created}.values())
        for key, value in updated.items():
            setattr(self, key, value)
        if commit:
            session.add(self)
            session.commit()
            session.refresh(self)
        return self


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

    @property
    def infohash(self) -> Optional[str]:
        if self.torrent:
            return self.torrent.infohash
        return None

    @property
    def file_name(self) -> str:
        return self.torrent.file_name

    @field_validator("dataset", mode="before")
    def extract_slug(cls, value: Optional["Dataset"] = None) -> SlugStr:
        if value is not None:
            value = value.slug
        return value


class UploadCreate(UploadBase):
    """Dataset upload for creation, excludes the is_approved param"""

    infohash: str = Field(
        min_length=40,
        max_length=64,
        description="Infohash of the torrent file, v1 or v2",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
    )
    part_slugs: Optional[list[SlugStr]] = Field(
        default=None,
        title="Dataset Parts",
        description="Parts of a dataset that this upload corresponds to",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
    )

    @classmethod
    def from_upload(cls, upload: Upload) -> Self:
        return cls.model_validate(
            upload,
            update={
                "infohash": upload.infohash,
                "part_slugs": [p.part_slug for p in upload.dataset_parts],
                "file_name": upload.file_name,
            },
        )


@all_optional
class UploadUpdate(UploadCreate):
    infohash: str = Field(
        min_length=40,
        max_length=64,
        description="Infohash of the torrent file, v1 or v2",
        schema_extra={"json_schema_extra": {"input_type": InputType.input, "disabled": True}},
    )
    file_name: Optional[FileName] = Field(
        default=None,
        max_length=1024,
        title="File name",
        description="Torrent filename (must end in .torrent)",
        schema_extra={"json_schema_extra": {"input_type": InputType.input}},
    )
