from enum import StrEnum
from typing import TYPE_CHECKING, Any, Optional

import sqlalchemy as sqla
from pydantic import field_validator
from sqlalchemy import ColumnElement, event
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm.attributes import NEVER_SET, AttributeEventToken
from sqlalchemy.schema import UniqueConstraint
from sqlmodel import Field, Relationship

from sciop.models.base import SQLModel
from sciop.models.mixins import ModerableMixin, TableMixin
from sciop.types import IDField, InputType, MaxLenURL, UsernameStr, UTCDateTime

if TYPE_CHECKING:
    from sciop.models import Account, AuditLog, TorrentFile


class WebseedStatus(StrEnum):
    in_original = "in_original"
    """
    Webseed was present in the original upload.
    We don't validate these by default until we know how expensive this is, 
    the uploader can correct them later if needed. 
    """
    pending_review = "pending_review"
    """
    The webseed needs to be reviewed, 
    since it was added by an account without permissions to do so.
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


class Webseed(WebseedBase, TableMixin, ModerableMixin, table=True):
    __tablename__ = "webseeds"
    __table_args__ = (UniqueConstraint("url", "torrent_id"),)

    webseed_id: IDField = Field(default=None, primary_key=True)

    account_id: int | None = Field(default=None, foreign_key="accounts.account_id")
    account: "Account" = Relationship(back_populates="webseeds")
    torrent_id: int | None = Field(
        default=None, foreign_key="torrent_files.torrent_file_id", ondelete="CASCADE"
    )
    torrent: "TorrentFile" = Relationship(back_populates="webseeds")
    audit_log_target: list["AuditLog"] = Relationship(back_populates="target_webseed")

    @hybrid_method
    def removable_by(self, account: Optional["Account"] = None) -> bool:
        """
        Make removable by the creating account, torrent uploader, or reviewers
        """
        if account is None:
            return False
        return (
            self.account == account
            or self.torrent.account == account
            or account.has_scope("review")
        )

    @removable_by.inplace.expression
    @classmethod
    def _removable_by(cls, account: Optional["Account"] = None) -> ColumnElement[bool]:
        if account is None:
            return sqla.false()
        return sqla.or_(
            cls.account == account,
            cls.torrent.account == account,
            account.has_scope("review") == True,
        )


class WebseedCreate(SQLModel):
    url: MaxLenURL = Field(
        ...,
        schema_extra={"json_schema_extra": {"input_type": InputType.input}},
    )
    """URL of webseed"""


class WebseedRead(WebseedBase):
    account: UsernameStr
    torrent: str
    created_at: UTCDateTime
    updated_at: UTCDateTime
    is_approved: bool
    is_removed: bool

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


@event.listens_for(Webseed.is_approved, "set")
def _sync_webseeds_set(
    target: Webseed, value: bool, old_value: bool, initiator: AttributeEventToken
) -> None:
    if old_value == NEVER_SET or target.torrent is None:
        return

    from sciop.models.torrent import _sync_webseeds

    if value and target.status in ("validated", "in_original"):
        _sync_webseeds(target.torrent, target.torrent.webseeds, add=[target.url])
    else:
        _sync_webseeds(target.torrent, target.torrent.webseeds, remove=[target.url])


@event.listens_for(Webseed.status, "set")
def _sync_webseeds_set(
    target: Webseed, value: bool, old_value: bool, initiator: AttributeEventToken
) -> None:
    if old_value == NEVER_SET or target.torrent is None:
        return

    from sciop.models.torrent import _sync_webseeds

    if value in ("validated", "in_original") and target.is_approved:
        _sync_webseeds(target.torrent, target.torrent.webseeds, add=[target.url])
    else:
        _sync_webseeds(target.torrent, target.torrent.webseeds, remove=[target.url])
