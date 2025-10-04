import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, Optional, Self, cast
from urllib.parse import urljoin

import sqlalchemy as sqla
from pydantic import field_validator
from sqlalchemy import ColumnElement, SQLColumnExpression, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.attributes import AttributeEventToken
from sqlmodel import Field, Relationship, func, select

from sciop.config import get_config
from sciop.models import (
    Account,
    AuditLog,
    Dataset,
    DatasetPart,
    Report,
    TorrentFile,
    TorrentFileRead,
    TorrentTrackerLink,
)
from sciop.models.dataset import UploadDatasetPartLink
from sciop.models.mixins import (
    EditableMixin,
    FrontendMixin,
    ModerableMixin,
    SearchableMixin,
    SortableCol,
    SortMixin,
    TableMixin,
    TableReadMixin,
    all_optional,
)
from sciop.services.markdown import render_db_fields_to_html
from sciop.types import FileName, IDField, InputType, SlugStr, UsernameStr, UTCDateTime

if TYPE_CHECKING:
    from sqlmodel import Session


class UploadBase(ModerableMixin, FrontendMixin):
    """
    A copy of a dataset
    """

    __name__: ClassVar[str] = "upload"

    method: Optional[str] = Field(
        None,
        title="Method",
        description="""Description of how the dataset was acquired. Markdown input is supported.""",
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
        max_length=163840,
    )
    method_html: Optional[str] = Field(
        "",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
        max_length=655360,
    )
    description: Optional[str] = Field(
        None,
        title="Description",
        description="Any additional information about this dataset upload. "
        "Markdown input is supported.",
        schema_extra={"json_schema_extra": {"input_type": InputType.textarea}},
        max_length=163840,
    )
    description_html: Optional[str] = Field(
        "",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
        max_length=655360,
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
        return urljoin(get_config().server.base_url, self.download_path)

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
              <a href="{get_config().server.base_url}/datasets/{self.dataset.slug}">
                {get_config().server.base_url}/datasets/{self.dataset.slug}
              </a>
            </p>
            <p>
            <strong>Upload:</strong> 
              <a href="{get_config().server.base_url}/uploads/{self.infohash}">
              {get_config().server.base_url}/uploads/{self.infohash}
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

    @property
    def frontend_url(self) -> str:
        return f"/uploads/{self.infohash}/"

    @hybrid_property
    def short_name(self) -> str:
        return self.short_hash


class Upload(UploadBase, TableMixin, SearchableMixin, EditableMixin, SortMixin, table=True):
    __tablename__ = "uploads"
    __searchable__ = {
        "description": 2.0,
        "method": 1.0,
    }
    __sortable__ = (
        SortableCol(),
        SortableCol(name="infohash", title="hash"),
        SortableCol(name="file_name", title="name"),
        SortableCol(name="size", title="size"),
        SortableCol(
            name="seeders",
            title="""<span class="seeders-icon" aria-label="up arrow">⇧</span>""",
            tooltip="Number of seeders for upload",
        ),
        SortableCol(
            name="leechers",
            title="""<span class="downloaders-icon" aria-label="down-arrow">⇧</span>""",
            tooltip="Number of seeders for upload",
        ),
        SortableCol(
            name="created_at",
            title="made",
        ),
    )
    created_at: Optional[UTCDateTime] = Field(default_factory=lambda: datetime.now(UTC), index=True)
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
    reports: list["Report"] = Relationship(back_populates="target_upload")

    @hybrid_property
    def infohash(self) -> Optional[str]:
        if self.torrent:
            return self.torrent.infohash
        return None

    @infohash.inplace.expression
    def infohash(self) -> SQLColumnExpression[str]:
        return cast("SQLColumnExpression[str]", TorrentFile.infohash)

    @hybrid_property
    def file_name(self) -> str:
        return self.torrent.file_name

    @file_name.inplace.expression
    def _file_name(cls) -> SQLColumnExpression[str]:
        return cast(
            "SQLColumnExpression[str]",
            TorrentFile.file_name,
        )

    @property
    def name(self) -> str:
        """File name without the .torrent suffix!"""
        return re.sub(r".torrent$", "", self.file_name)

    @property
    def magnet_link(self) -> str:
        return self.torrent.magnet_link

    @hybrid_property
    def seeders(self) -> int:
        return self.torrent.seeders

    @seeders.inplace.expression
    @classmethod
    def _seeders(cls) -> SQLColumnExpression[Optional[int]]:
        return (
            select(func.max(TorrentTrackerLink.seeders))
            .join(TorrentTrackerLink.torrent)
            .where(TorrentFile.upload_id == cls.upload_id)
            .label("seeders")
        )

    @hybrid_property
    def leechers(self) -> int:
        return self.torrent.leechers

    @leechers.inplace.expression
    @classmethod
    def _leechers(cls) -> SQLColumnExpression[Optional[int]]:
        return (
            select(func.max(TorrentTrackerLink.leechers))
            .join(TorrentTrackerLink.torrent)
            .where(TorrentFile.upload_id == cls.upload_id)
            .label("leechers")
        )

    @hybrid_property
    def size(self) -> int:
        return self.torrent.total_size

    @classmethod
    @size.inplace.expression
    def _size(cls) -> SQLColumnExpression[int]:
        return (
            select(TorrentFile.total_size)
            .where(TorrentFile.upload_id == cls.upload_id)
            .correlate(cls)
            .label("size")
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

    def to_read(self) -> "UploadRead":
        return UploadRead.model_validate(self)


@event.listens_for(Upload.is_removed, "set")
def _upload_remove_torrent(
    target: Upload, value: bool, oldvalue: bool, initiator: AttributeEventToken
) -> None:
    """Remove an associated torrent when the"""
    if value and not oldvalue and oldvalue is not None and target.torrent:
        from sciop.db import get_session

        with get_session() as session:
            torrent = session.merge(target.torrent)
            session.delete(torrent)
            session.commit()


event.listen(Upload, "before_update", render_db_fields_to_html("description", "method"))
event.listen(Upload, "before_insert", render_db_fields_to_html("description", "method"))


class UploadRead(UploadBase, TableReadMixin):
    """Version of datasaet upload returned when reading"""

    account: Optional[UsernameStr] = None
    dataset: Optional[SlugStr] = None
    dataset_parts: Optional[list[SlugStr]] = None
    torrent: Optional["TorrentFileRead"] = None
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

    @field_validator("dataset_parts", mode="before")
    def extract_part_slugs(cls, value: list["DatasetPart"] | None = None) -> list[SlugStr] | None:
        if value:
            value = sorted([v.part_slug for v in value])
        return value

    @field_validator("account", mode="before")
    def extract_username(cls, value: Optional["Account"] = None) -> SlugStr:
        if value is not None:
            value = value.username
        return value

    @property
    def magnet_link(self) -> str:
        return self.torrent.magnet_link

    @property
    def size(self) -> int:
        return self.torrent.total_size


class UploadCreate(UploadBase):
    """Dataset upload for creation, excludes the is_approved param"""

    infohash: str = Field(
        min_length=40,
        max_length=64,
        description="Infohash of the torrent file, v1 or v2",
        schema_extra={"json_schema_extra": {"input_type": InputType.none}},
    )
    dataset_slug: Optional[SlugStr] = Field(
        default=None,
        title="Dataset Slug",
        description="Parts of a dataset that this upload corresponds to",
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
