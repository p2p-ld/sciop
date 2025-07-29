from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import field_validator
from sqlmodel import Relationship

from sciop.models.base import SQLModel
from sciop.types import MaxLenURL, UsernameStr, UTCDateTime

if TYPE_CHECKING:
    from sciop.models import Account, TorrentFile


class WebseedStatus(StrEnum):
    in_original = "in_original"
    """
    Webseed was present in the original upload.
    We don't validate these by default until we know how expensive this is, 
    the uploader can correct them later if needed. 
    """
    queued = "queued"
    """
    Queued for validation
    """
    in_progress = "in_progress"
    """Validation currently happening"""
    validated = "validated"
    """Validation successful"""
    error = "error"
    """Some error in validation"""


class WebseedBase(SQLModel):
    url: MaxLenURL
    status: WebseedStatus
    message: str | None = None
    """Message to display in the case of error, etc."""


class Webseed(WebseedBase, table=True):
    account: "Account" = Relationship(back_populates="webseeds")
    torrent: "TorrentFile" = Relationship(back_populates="webseeds")


class WebseedCreate(SQLModel):
    url: MaxLenURL
    """URL of webseed"""
    torrent: str
    """Infohash of torrent to add webseed to"""


class WebseedRead(WebseedBase):
    account: UsernameStr
    torrent: str
    created_at: UTCDateTime
    updated_at: UTCDateTime

    @field_validator("account", mode="before")
    @classmethod
    def username_from_account(cls, data: Any) -> str:
        from sciop.models import Account, AccountRead

        if isinstance(data, Account | AccountRead):
            data = data.username
        return data

    @field_validator("torrent", mode="before")
    @classmethod
    def infohash_from_torrentfile(cls, data: Any) -> str:
        from sciop.models import TorrentFile, TorrentFileRead

        if isinstance(data, TorrentFile | TorrentFileRead):
            data = data.infohash
        return data
