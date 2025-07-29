from enum import StrEnum
from typing import TYPE_CHECKING, Any

from pydantic import field_validator
from sqlalchemy.schema import UniqueConstraint
from sqlmodel import Field, Relationship

from sciop.models.base import SQLModel
from sciop.models.mixins import TableMixin
from sciop.types import IDField, MaxLenURL, UsernameStr, UTCDateTime

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


class Webseed(WebseedBase, TableMixin, table=True):
    __tablename__ = "webseeds"
    __table_args__ = (UniqueConstraint("url", "torrent_id"),)

    webseed_id: IDField = Field(default=None, primary_key=True)

    account_id: int | None = Field(default=None, foreign_key="accounts.account_id")
    account: "Account" = Relationship(back_populates="webseeds")
    torrent_id: int | None = Field(
        default=None, foreign_key="torrent_files.torrent_file_id", ondelete="CASCADE"
    )
    torrent: "TorrentFile" = Relationship(back_populates="webseeds")


class WebseedCreate(SQLModel):
    url: MaxLenURL
    """URL of webseed"""


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
