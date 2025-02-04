from pathlib import Path
from typing import TYPE_CHECKING, Optional

import humanize
from sqlmodel import Field, Relationship, SQLModel

from sciop.config import config
from sciop.models.mixin import TableMixin

if TYPE_CHECKING:
    from sciop.models.dataset import Account, DatasetInstance


class FileInTorrent(TableMixin, table=True):
    """A file within a torrent file"""

    path: str = Field(description="Path of file within torrent")
    size: int = Field(description="Size in bytes")

    torrent_id: Optional[int] = Field(default=None, foreign_key="torrentfile.id")
    torrent: Optional["TorrentFile"] = Relationship(back_populates="files")


class FileInTorrentCreate(SQLModel):
    path: str
    size: int


class FileInTorrentRead(FileInTorrentCreate):
    pass


class TrackerInTorrent(TableMixin, table=True):
    """A tracker within a torrent file"""

    url: str = Field(description="Tracker announce url")

    torrent_id: Optional[int] = Field(default=None, foreign_key="torrentfile.id")
    torrent: Optional["TorrentFile"] = Relationship(back_populates="trackers")


class TrackerInTorrentRead(SQLModel):
    url: str


class TorrentFileBase(SQLModel):
    file_name: str
    hash: str
    short_hash: Optional[str] = Field(
        None, min_length=8, max_length=8, description="length-8 truncated version of hash"
    )
    total_size: int = Field(description="Total torrent size in bytes")
    piece_size: int = Field(description="Piece size in bytes")
    torrent_size: Optional[int] = Field(
        None, description="Size of the torrent file itself, in bytes"
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


class TorrentFile(TorrentFileBase, TableMixin, table=True):
    account_id: Optional[int] = Field(default=None, foreign_key="account.id")
    account: "Account" = Relationship(back_populates="torrents")
    instance_id: Optional[int] = Field(default=None, foreign_key="datasetinstance.id")
    instance: Optional["DatasetInstance"] = Relationship(back_populates="torrent")
    files: list["FileInTorrent"] = Relationship(back_populates="torrent")
    trackers: list["TrackerInTorrent"] = Relationship(back_populates="torrent")


class TorrentFileCreate(TorrentFileBase):
    files: list[FileInTorrentCreate]
    trackers: list[str]


class TorrentFileRead(TorrentFileBase):
    files: list[FileInTorrentRead]
    trackers: list[TrackerInTorrentRead]
