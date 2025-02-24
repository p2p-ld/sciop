from pathlib import Path
from typing import TYPE_CHECKING, Optional

import humanize
from pydantic import field_validator
from sqlmodel import Field, Relationship, SQLModel

from sciop.config import config
from sciop.models.mixin import TableMixin
from sciop.types import EscapedStr, IDField, MaxLenURL

if TYPE_CHECKING:
    from sciop.models import Upload
    from sciop.models.dataset import Account


class FileInTorrent(TableMixin, table=True):
    """A file within a torrent file"""

    __tablename__ = "file_in_torrent"

    file_in_torrent_id: IDField = Field(None, primary_key=True)
    path: EscapedStr = Field(description="Path of file within torrent", max_length=1024)
    size: int = Field(description="Size in bytes")

    torrent_id: Optional[int] = Field(default=None, foreign_key="torrent_file.torrent_file_id")
    torrent: Optional["TorrentFile"] = Relationship(back_populates="files")

    @property
    def human_size(self) -> str:
        return humanize.naturalsize(self.size)


class FileInTorrentCreate(SQLModel):
    path: EscapedStr = Field(max_length=1024)
    size: int


class FileInTorrentRead(FileInTorrentCreate):
    pass


class TrackerInTorrent(TableMixin, table=True):
    """A tracker within a torrent file"""

    __tablename__ = "tracker_in_torrent"

    tracker_in_torrent_id: IDField = Field(None, primary_key=True)
    url: MaxLenURL = Field(description="Tracker announce url")

    torrent_id: Optional[int] = Field(default=None, foreign_key="torrent_file.torrent_file_id")
    torrent: Optional["TorrentFile"] = Relationship(back_populates="trackers")


class TrackerInTorrentRead(SQLModel):
    url: MaxLenURL


class TorrentFileBase(SQLModel):
    file_name: str = Field(max_length=1024)
    file_hash: str = Field(description="blake2b Hash of the .torrent file itself")
    short_hash: Optional[str] = Field(
        None,
        min_length=8,
        max_length=8,
        description="length-8 truncated version of file_hash",
        index=True,
    )
    infohash: str = Field(max_length=256)
    total_size: int = Field(description="Total torrent size in bytes")
    piece_size: int = Field(description="Piece size in bytes")
    torrent_size: Optional[int] = Field(
        None, description="Size of the .torrent file itself, in bytes"
    )

    @property
    def download_path(self) -> str:
        """Path beneath the root"""
        return f"/torrents/{self. short_hash}/{self.file_name}"

    @property
    def filesystem_path(self) -> Path:
        """Location of where this torrent is or should be on the filesystem"""
        return config.torrent_dir / self.short_hash / self.file_name

    @property
    def human_size(self) -> str:
        """Human-sized string representation of the torrent size"""
        return humanize.naturalsize(self.total_size)

    @property
    def human_torrent_size(self) -> str:
        """Human-sized string representation of the torrent file size"""
        return humanize.naturalsize(self.torrent_size)

    @property
    def human_piece_size(self) -> str:
        return humanize.naturalsize(self.piece_size)


class TorrentFile(TorrentFileBase, TableMixin, table=True):
    __tablename__ = "torrent_file"

    torrent_file_id: IDField = Field(None, primary_key=True)
    account_id: Optional[int] = Field(default=None, foreign_key="account.account_id")
    account: "Account" = Relationship(back_populates="torrents")
    upload_id: Optional[int] = Field(default=None, foreign_key="upload.upload_id")
    upload: Optional["Upload"] = Relationship(back_populates="torrent")
    files: list["FileInTorrent"] = Relationship(back_populates="torrent")
    trackers: list["TrackerInTorrent"] = Relationship(back_populates="torrent")


class TorrentFileCreate(TorrentFileBase):
    files: list[FileInTorrentCreate]
    trackers: list[MaxLenURL]


class TorrentFileRead(TorrentFileBase):
    files: list[str]
    trackers: list[str]

    @field_validator("files", mode="before")
    def flatten_files(cls, val: list[FileInTorrentRead]) -> list[str]:
        return [v.path for v in val]

    @field_validator("trackers", mode="before")
    def flatten_trackers(cls, val: list[TrackerInTorrentRead]) -> list[str]:
        return [v.url for v in val]
