from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Optional
from urllib.parse import urlparse

from pydantic import computed_field
from sqlalchemy.schema import UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from sciop.models.mixin import TableMixin
from sciop.types import IDField, MaxLenURL

if TYPE_CHECKING:
    from sciop.models import TorrentFile


class TrackerProtocol(StrEnum):
    udp = "udp"
    http = "http"
    https = "https"


class TorrentTrackerLink(TableMixin, table=True):
    __tablename__ = "torrent_tracker_links"
    __table_args__ = (UniqueConstraint("torrent_file_id", "tracker_id"),)
    __table_kwargs__ = {"sqlite_autoincrement": True}

    torrent_file_id: Optional[int] = Field(
        default=None,
        foreign_key="torrent_files.torrent_file_id",
        primary_key=True,
        ondelete="CASCADE",
    )
    tracker_id: Optional[int] = Field(
        default=None, foreign_key="trackers.tracker_id", primary_key=True
    )
    torrent: "TorrentFile" = Relationship(back_populates="tracker_links")
    tracker: "Tracker" = Relationship(back_populates="torrent_links")
    seeders: Optional[int] = Field(default=None)
    leechers: Optional[int] = Field(default=None)
    completed: Optional[int] = Field(default=None)
    last_scraped_at: Optional[datetime] = Field(default=None)


class TrackerBase(SQLModel):
    announce_url: MaxLenURL = Field(description="Tracker announce url", unique=True, index=True)
    protocol: TrackerProtocol


class Tracker(TrackerBase, TableMixin, table=True):
    """A bittorrent tracker"""

    __tablename__ = "trackers"

    tracker_id: IDField = Field(None, primary_key=True)
    torrent_links: list[TorrentTrackerLink] = Relationship(back_populates="tracker")
    last_scraped_at: Optional[datetime] = Field(default=None)
    scrape_failures: int = Field(
        default=0,
        description="Number of sequential failures to scrape this tracker, "
        "used for exponential backoff. "
        "Should be set to 0 after a successful scrape",
    )
    next_scrape_after: Optional[datetime] = Field(default=None)


class TrackerCreate(SQLModel):
    announce_url: MaxLenURL = Field(description="Tracker announce url")

    @computed_field
    def protocol(self) -> TrackerProtocol:
        return TrackerProtocol[urlparse(self.announce_url).scheme]


class TrackerRead(TrackerBase):
    announce_url: MaxLenURL
