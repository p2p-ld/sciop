import hashlib
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator, Optional, Self

import bencodepy
import humanize
from pydantic import field_validator, model_validator
from sqlalchemy import Connection, event
from sqlalchemy.orm.mapper import Mapper
from sqlmodel import Field, Relationship, SQLModel
from torf import Torrent as Torrent_

from sciop.config import config
from sciop.models.mixin import TableMixin
from sciop.models.tracker import TorrentTrackerLink, TrackerRead
from sciop.types import EscapedStr, IDField, MaxLenURL

if TYPE_CHECKING:
    from sciop.models import Upload
    from sciop.models.dataset import Account


class TorrentVersion(StrEnum):
    v1 = "v1"
    v2 = "v2"
    hybrid = "hybrid"


@dataclass
class _File:
    path: os.PathLike[str]
    size: int


def _to_str(val: str | bytes) -> str:
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    elif isinstance(val, str):
        return val
    else:
        return str(val)


class Torrent(Torrent_):
    """
    Subclass of :class:`torf.Torrent` that can compute v2 infohashes
    and not spend literally eons processing torrent files
    """

    @property
    def v2_infohash(self) -> Optional[str]:
        """SHA256 hash of info dict, if `file tree` is present"""
        self.validate()
        if "file tree" not in self.metainfo["info"]:
            return None

        return hashlib.sha256(bencodepy.encode(self.metainfo["info"])).hexdigest()

    @property
    def torrent_version(self) -> TorrentVersion:
        if "pieces" in self.metainfo["info"] and "file tree" in self.metainfo["info"]:
            return TorrentVersion.hybrid
        elif "pieces" in self.metainfo["info"]:
            return TorrentVersion.v1
        elif "file tree" in self.metainfo["info"]:
            return TorrentVersion.v2
        else:
            raise ValueError("Unsure what version this torrent is, likely invalid")

    @property
    def files(self) -> Generator[_File, None, None]:
        """
        Override of the ridiculously inefficient file listing method in torf
        """
        info = self.metainfo["info"]
        if self.mode == "singlefile":
            yield _File(path=_to_str(info.get("name", b"")), size=self.size)
        elif self.mode == "multifile":

            basedir = _to_str(info.get("name", b""))
            for fileinfo in info["files"]:
                yield _File(
                    path=os.path.join(
                        basedir, *(_to_str(file_part) for file_part in fileinfo["path"])
                    ),
                    size=fileinfo["length"],
                )

    @files.setter
    def files(self, files: Any) -> None:
        super(Torrent, self.__class__).files.fset(self, files)

    @property
    def n_files(self) -> int:
        if self.mode == "singlefile":
            return 1
        else:
            return len(self.metainfo["info"]["files"])

    def _filters_changed(self, _: Any) -> None:
        """Make this a no-op because it's wildly expensive"""
        pass


class FileInTorrent(TableMixin, table=True):
    """A file within a torrent file"""

    __tablename__ = "files_in_torrent"

    file_in_torrent_id: IDField = Field(None, primary_key=True)
    path: EscapedStr = Field(description="Path of file within torrent", max_length=1024)
    size: int = Field(description="Size in bytes")

    torrent_id: Optional[int] = Field(
        default=None, foreign_key="torrent_files.torrent_file_id", ondelete="CASCADE"
    )
    torrent: Optional["TorrentFile"] = Relationship(back_populates="files")

    @property
    def human_size(self) -> str:
        return humanize.naturalsize(self.size)


class FileInTorrentCreate(SQLModel):
    path: str = Field(max_length=4096)
    size: int


class FileInTorrentRead(FileInTorrentCreate):
    pass


class TorrentFileBase(SQLModel):
    file_name: str = Field(max_length=1024)
    v1_infohash: str = Field(
        max_length=40, min_length=40, unique=True, index=True, description="SHA1 hash of infodict"
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
        return f"/torrents/{self.infohash}/{self.file_name}"

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
        return config.torrent_dir / self.infohash / self.file_name

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
    __tablename__ = "torrent_files"

    torrent_file_id: IDField = Field(None, primary_key=True)
    account_id: Optional[int] = Field(default=None, foreign_key="accounts.account_id")
    account: "Account" = Relationship(back_populates="torrents")
    upload_id: Optional[int] = Field(default=None, foreign_key="uploads.upload_id")
    upload: Optional["Upload"] = Relationship(back_populates="torrent")
    files: list["FileInTorrent"] = Relationship(back_populates="torrent", cascade_delete=True)
    tracker_links: list[TorrentTrackerLink] = Relationship(back_populates="torrent")
    short_hash: str = Field(
        min_length=8,
        max_length=8,
        description="length-8 truncated version of the v2 infohash, if present, or the v1 infohash",
        index=True,
    )


@event.listens_for(TorrentFile, "after_delete")
def _delete_torrent_file(mapper: Mapper, connection: Connection, target: TorrentFile) -> None:
    """
    When a reference to a torrent file is deleted, delete the torrent file itself
    """
    target.filesystem_path.unlink(missing_ok=True)


class TorrentFileCreate(TorrentFileBase):
    files: list[FileInTorrentCreate]
    trackers: list[MaxLenURL]

    @model_validator(mode="after")
    def get_short_hash(self) -> Self:
        """Get short hash, if not explicitly provided"""
        if self.short_hash is None:
            if self.v2_infohash:
                self.short_hash = self.v2_infohash[0:8]
            else:
                self.short_hash = self.v1_infohash[0:8]
        return self


class TorrentFileRead(TorrentFileBase):
    files: list[str]
    trackers: list[str] = Field(min_length=1, max_length=128)
    short_hash: str = Field(
        None,
        min_length=8,
        max_length=8,
        description="length-8 truncated version of the v2 infohash, if present, or the v1 infohash",
        index=True,
    )

    @field_validator("files", mode="before")
    def flatten_files(cls, val: list[FileInTorrentRead]) -> list[str]:
        return [v.path for v in val]

    @field_validator("trackers", mode="before")
    def flatten_trackers(cls, val: list[TrackerRead]) -> list[str]:
        return [v.url for v in val]
