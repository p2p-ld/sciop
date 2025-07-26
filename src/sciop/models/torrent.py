import re
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional, Self
from urllib.parse import ParseResult, quote, urlparse, urlunparse

import humanize
from pydantic import ModelWrapValidatorHandler, field_validator, model_validator
from sqlalchemy import ColumnElement, Connection, SQLColumnExpression, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.attributes import AttributeEventToken
from sqlalchemy.orm.mapper import Mapper
from sqlalchemy.sql import func
from sqlmodel import Field, Relationship, select

from sciop.config import get_config
from sciop.models.base import SQLModel
from sciop.models.magnet import MagnetLink
from sciop.models.mixins import EditableMixin, SortableCol, SortMixin, TableMixin
from sciop.models.tracker import TorrentTrackerLink, Tracker
from sciop.types import EscapedStr, FileName, IDField, MaxLenURL

if TYPE_CHECKING:
    from sciop.models import Upload
    from sciop.models.dataset import Account

PADFILE_PATTERN = re.compile(r"(.*/|^)\.pad/\d+$")


class TorrentVersion(StrEnum):
    v1 = "v1"
    v2 = "v2"
    hybrid = "hybrid"


class FileInTorrent(TableMixin, SortMixin, table=True):
    """A file within a torrent file"""

    __sortable__ = (SortableCol(name="path"), SortableCol(name="size"))

    __tablename__ = "files_in_torrent"

    file_in_torrent_id: IDField = Field(None, primary_key=True)
    path: EscapedStr = Field(description="Path of file within torrent", max_length=1024)
    size: int = Field(description="Size in bytes")

    torrent_id: Optional[int] = Field(
        default=None, foreign_key="torrent_files.torrent_file_id", ondelete="CASCADE", index=True
    )
    torrent: Optional["TorrentFile"] = Relationship(back_populates="files")

    @property
    def human_size(self) -> str:
        return humanize.naturalsize(self.size, binary=True)


class FileInTorrentCreate(SQLModel):
    path: str = Field(max_length=4096)
    size: int

    @property
    def human_size(self) -> str:
        return humanize.naturalsize(self.size, binary=True)


class FileInTorrentRead(FileInTorrentCreate):
    pass


class TorrentFileBase(SQLModel):
    file_name: FileName = Field(max_length=1024)
    v1_infohash: Optional[str] = Field(
        None,
        max_length=40,
        min_length=40,
        unique=True,
        index=True,
        description="SHA1 hash of infodict",
    )
    v2_infohash: Optional[str] = Field(
        None,
        min_length=64,
        max_length=64,
        description="SHA256 hash of infodict",
        unique=True,
        index=True,
    )
    short_hash: Optional[str] = Field(
        None,
        min_length=8,
        max_length=8,
        description="length-8 truncated version of the v2 infohash, if present, or the v1 infohash",
        index=True,
    )
    version: TorrentVersion = Field(
        description="Whether this torrent was created as a v1, v2, or hybrid torrent"
    )
    total_size: int = Field(description="Total torrent size in bytes")
    piece_size: int = Field(description="Piece size in bytes")
    torrent_size: Optional[int] = Field(
        None, description="Size of the .torrent file itself, in bytes"
    )

    @property
    def download_path(self) -> str:
        """Path beneath the root"""
        return quote(f"/torrents/{self.infohash}/{self.file_name}")

    @property
    def infohash(self) -> str:
        """The v2 infohash, if present, else the v1 infohash"""
        if self.v2_infohash:
            return self.v2_infohash
        else:
            return self.v1_infohash

    @property
    def filesystem_path(self) -> Path:
        """Location of where this torrent is or should be on the filesystem"""
        return self.get_filesystem_path(self.infohash, self.file_name)

    @classmethod
    def get_filesystem_path(cls, infohash: str, file_name: str) -> Path:
        return get_config().paths.torrents / infohash / file_name

    @property
    def human_size(self) -> str:
        """Human-sized string representation of the torrent size"""
        return humanize.naturalsize(self.total_size, binary=True)

    @property
    def human_torrent_size(self) -> str:
        """Human-sized string representation of the torrent file size"""
        return humanize.naturalsize(self.torrent_size, binary=True)

    @property
    def human_piece_size(self) -> str:
        return humanize.naturalsize(self.piece_size, binary=True)

    @property
    def magnet_link(self) -> str:
        """
        Use :class:`.MagnetLink` to render a magnet link!
        """
        return MagnetLink.from_torrent(self).render()

    @property
    def trackers(self) -> dict[MaxLenURL, Tracker]:
        """Convenience accessor for trackers through tracker links, keyed by announce url"""
        return {tl.tracker.announce_url: tl.tracker for tl in self.tracker_links}

    @property
    def tracker_links_map(self) -> dict[str, TorrentTrackerLink]:
        """Tracker links mapped by announce url"""
        return {link.tracker.announce_url: link for link in self.tracker_links}

    @property
    def n_files(self) -> int:
        return len(self.files)


class TorrentFile(TorrentFileBase, TableMixin, EditableMixin, table=True):
    __tablename__ = "torrent_files"

    torrent_file_id: IDField = Field(None, primary_key=True)
    account_id: Optional[int] = Field(default=None, foreign_key="accounts.account_id", index=True)
    account: "Account" = Relationship(back_populates="torrents")
    upload_id: Optional[int] = Field(default=None, foreign_key="uploads.upload_id", index=True)
    upload: Optional["Upload"] = Relationship(back_populates="torrent")
    files: list["FileInTorrent"] = Relationship(back_populates="torrent", cascade_delete=True)
    tracker_links: list[TorrentTrackerLink] = Relationship(
        back_populates="torrent", cascade_delete=True
    )
    short_hash: str = Field(
        min_length=8,
        max_length=8,
        description="length-8 truncated version of the v2 infohash, if present, or the v1 infohash",
        index=True,
    )

    @hybrid_property
    def infohash(self) -> str:
        """The v2 infohash, if present, else the v1 infohash"""
        if self.v2_infohash:
            return self.v2_infohash
        else:
            return self.v1_infohash

    @infohash.inplace.expression
    def _infohash(self) -> ColumnElement[str]:
        return func.ifnull(self.v2_infohash, self.v1_infohash)

    @hybrid_property
    def seeders(self) -> Optional[int]:
        seeders = [link.seeders for link in self.tracker_links if link.seeders is not None]
        if not seeders:
            return None
        return max(seeders)

    @seeders.inplace.expression
    def _seeders(self) -> SQLColumnExpression[int]:
        return (
            select(func.max(TorrentTrackerLink.seeders))
            .where(TorrentTrackerLink.torrent_file_id == self.torrent_file_id)
            .label("seeders")
        )

    @hybrid_property
    def leechers(self) -> Optional[int]:
        leechers = [link.leechers for link in self.tracker_links if link.leechers is not None]
        if not leechers:
            return None
        return max(leechers)

    @leechers.inplace.expression
    def _leechers(self) -> SQLColumnExpression[int]:
        return (
            select(func.max(TorrentTrackerLink.leechers))
            .where(TorrentTrackerLink.torrent_file_id == self.torrent_file_id)
            .label("leechers")
        )

    @hybrid_property
    def n_files(self) -> int:
        return len(self.files)

    @n_files.inplace.expression
    @classmethod
    def _n_files(cls) -> ColumnElement[int]:
        return func.count(cls.files)
        # .where(FileInTorrent.torrent_id == cls.torrent_file_id))


@event.listens_for(TorrentFile, "after_delete")
def _delete_torrent_file(mapper: Mapper, connection: Connection, target: TorrentFile) -> None:
    """
    When a reference to a torrent file is deleted, delete the torrent file itself
    """
    target.filesystem_path.unlink(missing_ok=True)


@event.listens_for(TorrentFile.file_name, "set")
def _rename_torrent_file(
    target: TorrentFile, value: Path, oldvalue: Path, initiator: AttributeEventToken
) -> None:
    if (
        filesystem_path := TorrentFile.get_filesystem_path(target.infohash, str(oldvalue))
    ).exists():
        filesystem_path.rename(
            TorrentFile.get_filesystem_path(infohash=target.infohash, file_name=str(value))
        )


class TorrentFileCreate(TorrentFileBase):
    files: list[FileInTorrentCreate]
    announce_urls: list[MaxLenURL]

    @model_validator(mode="after")
    def get_short_hash(self) -> Self:
        """Get short hash, if not explicitly provided"""
        if self.short_hash is None:
            if self.v2_infohash:
                self.short_hash = self.v2_infohash[0:8]
            else:
                self.short_hash = self.v1_infohash[0:8]
        return self

    @field_validator("announce_urls", mode="after")
    def remove_query_params(cls, val: list[MaxLenURL]) -> MaxLenURL:
        """
        Remove query params from trackers, as these often contain passkeys
        and shouldn't be necessary for tracker metata we persist to the db
        """
        stripped = []
        for url in val:
            parsed: ParseResult = urlparse(url)
            stripped.append(
                urlunparse(
                    ParseResult(
                        scheme=parsed.scheme,
                        netloc=parsed.netloc,
                        path=parsed.path,
                        params=parsed.params,
                        query="",
                        fragment=parsed.fragment,
                    )
                )
            )
        return stripped

    @field_validator("files", mode="after")
    def remove_padfiles(cls, val: list[FileInTorrentCreate]) -> list[FileInTorrentCreate]:
        """Remove .pad/d+ files"""
        return [v for v in val if not PADFILE_PATTERN.match(v.path)]

    @model_validator(mode="after")
    def any_infohash(self) -> Self:
        """Need either a v1 or a v2 infohash"""
        assert (
            self.v1_infohash or self.v2_infohash
        ), "Need to have either a v1 or v2 infohash, or both"
        return self


class TorrentFileRead(TorrentFileBase):
    short_hash: str = Field(
        None,
        min_length=8,
        max_length=8,
        description="length-8 truncated version of the v2 infohash, if present, or the v1 infohash",
        index=True,
    )
    announce_urls: list[MaxLenURL] = Field(default_factory=list)
    seeders: Optional[int] = None
    leechers: Optional[int] = None

    @model_validator(mode="wrap")
    @classmethod
    def flatten_trackers(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        val = handler(data)

        if isinstance(data, TorrentFile) and not val.announce_urls:
            val.announce_urls = [v.tracker.announce_url for v in data.tracker_links]

        return val
