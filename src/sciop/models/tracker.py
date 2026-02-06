from enum import StrEnum
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

from pydantic import computed_field
from sqlalchemy.schema import UniqueConstraint
from sqlmodel import Field, Relationship

from sciop.exceptions import ScrapeErrorType
from sciop.models.base import SQLModel
from sciop.models.mixins import TableMixin
from sciop.types import IDField, MaxLenURL, UTCDateTime

if TYPE_CHECKING:
    from sciop.models import TorrentFile


class TrackerProtocol(StrEnum):
    udp = "udp"
    http = "http"
    https = "https"
    wss = "wss"


class TorrentTrackerLink(TableMixin, table=True):
    __tablename__ = "torrent_tracker_links"
    __table_args__ = (UniqueConstraint("torrent_file_id", "tracker_id"),)
    __table_kwargs__ = {"sqlite_autoincrement": True}

    torrent_file_id: Optional[int] = Field(
        default=None,
        foreign_key="torrent_files.torrent_file_id",
        primary_key=True,
        ondelete="CASCADE",
        index=True,
    )
    tracker_id: Optional[int] = Field(
        default=None,
        foreign_key="trackers.tracker_id",
        primary_key=True,
        index=True,
    )
    torrent: "TorrentFile" = Relationship(back_populates="tracker_links")
    tracker: "Tracker" = Relationship(back_populates="torrent_links")
    seeders: Optional[int] = Field(default=None)
    leechers: Optional[int] = Field(default=None)
    completed: Optional[int] = Field(default=None)
    last_scraped_at: Optional[UTCDateTime] = Field(default=None)


class TrackerBase(SQLModel):
    announce_url: MaxLenURL = Field(description="Tracker announce url", unique=True, index=True)
    protocol: TrackerProtocol


class Tracker(TrackerBase, TableMixin, table=True):
    """A bittorrent tracker"""

    __tablename__ = "trackers"

    tracker_id: IDField = Field(None, primary_key=True)
    torrent_links: list[TorrentTrackerLink] = Relationship(back_populates="tracker")
    last_scraped_at: Optional[UTCDateTime] = Field(default=None)
    n_errors: int = Field(
        default=0,
        description="Number of sequential failures to scrape this tracker, "
        "used for exponential backoff. "
        "Should be set to 0 after a successful scrape",
    )
    error_type: Optional[ScrapeErrorType] = Field(default=None)
    next_scrape_after: Optional[UTCDateTime] = Field(default=None)

    def clear_backoff(self) -> None:
        """Reset a tracker's error count to 0 and clear the backoff delay"""
        self.n_errors = 0
        self.error_type = None
        self.next_scrape_after = None


class TrackerCreate(SQLModel):
    announce_url: MaxLenURL = Field(description="Tracker announce url")

    @computed_field
    def protocol(self) -> TrackerProtocol:
        return TrackerProtocol[urlparse(self.announce_url).scheme]


class TrackerRead(TrackerBase):
    announce_url: MaxLenURL
