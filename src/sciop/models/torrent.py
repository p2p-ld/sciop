import hashlib
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Generator, Optional, Self

import bencodepy
import humanize
from pydantic import ModelWrapValidatorHandler, field_validator, model_validator
from sqlalchemy import ColumnElement, Connection, event
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm.attributes import AttributeEventToken
from sqlalchemy.orm.mapper import Mapper
from sqlalchemy.sql import func
from sqlmodel import Field, Relationship, SQLModel
from torf import Torrent as Torrent_
from torf import _errors, _torrent, _utils

from sciop.config import config
from sciop.models.mixins import EditableMixin, TableMixin
from sciop.models.tracker import TorrentTrackerLink, Tracker
from sciop.types import EscapedStr, FileName, IDField, MaxLenURL

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

    MAX_TORRENT_FILE_SIZE = config.upload_limit

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # use these goofy names since `_infohash` is already used
        self._internal_infohash = None
        self._internal_infohash_v2 = None

    @property
    def v2_infohash(self) -> Optional[str]:
        """SHA256 hash of info dict, if `file tree` is present"""
        if self._internal_infohash_v2 is None:
            if "file tree" not in self.metainfo["info"]:
                return None

            self._internal_infohash_v2 = hashlib.sha256(
                bencodepy.encode(self.metainfo["info"])
            ).hexdigest()
        return self._internal_infohash_v2

    @property
    def infohash(self) -> Optional[str]:
        """Override parent impl to not validate when accessing an infohash..."""
        if self._internal_infohash is None:
            try:
                try:
                    info = _utils.encode_dict(self.metainfo["info"])
                except ValueError as e:
                    raise _errors.MetainfoError(e) from e
                else:
                    self._internal_infohash = hashlib.sha1(bencodepy.encode(info)).hexdigest()
            except _errors.MetainfoError as e:
                # If we can't calculate infohash, see if it was explicitly specifed.
                # This is necessary to create a Torrent from a Magnet URI.
                try:
                    return self._infohash
                except AttributeError:
                    raise e from None
        return self._internal_infohash

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


def _assert_type(
    obj: list | dict,
    keys: tuple[str | int],
    exp_types: tuple[type],
    must_exist: bool = True,
    check: Optional[Callable] = None,
) -> None:
    """
    Override torf's ridiculously inefficient validation function

    Raise MetainfoError if value is not of a particular type

    :param obj: The object to check
    :type obj: sequence or mapping
    :param keys: Sequence of keys so that ``obj[key[0]][key[1]]...`` resolves to
        a value
    :type obj: sequence
    :param exp_types: Sequence of allowed types that the value specified by
        `keys` must be an instance of
    :type obj: sequence
    :param bool must_exist: Whether to raise MetainfoError if `keys` does not
         resolve to a value
    :param callable check: Callable that gets the value specified by `keys` and
        returns True if it is OK, False otherwise
    """
    keys = list(keys)
    i = -1
    for j, key in enumerate(keys[:-1]):
        try:
            obj = obj[key]
        except (KeyError, IndexError):
            i = j + 1
            break

    key = keys[i]

    if not _utils.key_exists_in_list_or_dict(key, obj):
        if must_exist:
            raise _errors.MetainfoError(f"Missing {key!r} in {keys}")

    elif not isinstance(obj[key], exp_types):
        if len(exp_types) > 2:
            exp_types_str = ", ".join(t.__name__ for t in exp_types[:-1])
            exp_types_str += " or " + exp_types[-1].__name__
        else:
            exp_types_str = " or ".join(t.__name__ for t in exp_types)
        type_str = type(obj[key]).__name__
        raise _errors.MetainfoError(
            f"{keys}[{key!r}] must be {exp_types_str}, " f"not {type_str}: {obj[key]!r}"
        )

    elif check is not None and not check(obj[key]):
        raise _errors.MetainfoError(f"{keys}[{key!r}] is invalid: {obj[key]!r}")


def _key_exists_in_list_or_dict(key: str | int, lst_or_dct: list | dict) -> bool:
    """True if `lst_or_dct[key]` does not raise an Exception"""
    try:
        _ = lst_or_dct[key]
        return True
    except (KeyError, IndexError):
        return False


_torrent.utils.key_exists_in_list_or_dict = _key_exists_in_list_or_dict
_torrent.utils.assert_type = _assert_type


class FileInTorrent(TableMixin, EditableMixin, table=True):
    """A file within a torrent file"""

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
        return humanize.naturalsize(self.size)


class FileInTorrentCreate(SQLModel):
    path: str = Field(max_length=4096)
    size: int


class FileInTorrentRead(FileInTorrentCreate):
    pass


class TorrentFileBase(SQLModel):
    file_name: FileName = Field(max_length=1024)
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
        return self.get_filesystem_path(self.infohash, self.file_name)

    @classmethod
    def get_filesystem_path(cls, infohash: str, file_name: str) -> Path:
        return config.torrent_dir / infohash / file_name

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

    @property
    def trackers(self) -> dict[MaxLenURL, Tracker]:
        """Convenience accessor for trackers through tracker links, keyed by announce url"""
        return {tl.tracker.announce_url: tl.tracker for tl in self.tracker_links}

    @property
    def tracker_links_map(self) -> dict[str, TorrentTrackerLink]:
        """Tracker links mapped by announce url"""
        return {link.tracker.announce_url: link for link in self.tracker_links}


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
    def _seeders(self) -> ColumnElement[Optional[int]]:
        return func.max(TorrentTrackerLink.seeders).where(
            TorrentTrackerLink.torrent_id == self.torrent_id
        )

    @hybrid_property
    def leechers(self) -> Optional[int]:
        leechers = [link.leechers for link in self.tracker_links if link.leechers is not None]
        if not leechers:
            return None
        return max(leechers)

    @leechers.inplace.expression
    def _leechers(self) -> ColumnElement[Optional[int]]:
        return func.max(TorrentTrackerLink.leechers).where(
            TorrentTrackerLink.torrent_id == self.torrent_id
        )


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


class TorrentFileRead(TorrentFileBase):
    files: list[str]
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

    @field_validator("files", mode="before")
    def flatten_files(cls, val: list[FileInTorrentRead]) -> list[str]:
        return [v.path for v in val]

    @model_validator(mode="wrap")
    @classmethod
    def flatten_trackers(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        val = handler(data)

        if isinstance(data, TorrentFile) and not val.announce_urls:
            val.announce_urls = [v.tracker.announce_url for v in data.tracker_links]

        return val
