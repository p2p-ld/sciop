"""
Models for parsing and storing atom feeds
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, Relationship

from sciop.models.base import SQLModel
from sciop.types import IDField, MaxLenURL, UTCDateTime


class AtomFeed(SQLModel, table=True):
    """
    An atom feed subscription.

    The `updated_at` field is not automatically populated,
    but reflects the `updated` field in the atom feed.
    """

    __tablename__ = "atom_feeds"

    atom_feed_id: IDField = Field(None, primary_key=True)
    created_at: Optional[UTCDateTime] = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: Optional[UTCDateTime] = Field(None)
    url: MaxLenURL
    name: str = Field(..., description="Short-name used when displaying items from this feed")
    entries: list[AtomFeedEntry] = Relationship(back_populates="feed", cascade_delete=True)


class AtomFeedEntry(SQLModel, table=True):
    """
    An item within an atom feed.

    Names mirror the names used in the atom spec,
    and so may diverge from names used consistently elsewhere in sciop
    """

    __tablename__ = "atom_feed_entries"

    feed_id: Optional[int] = Field(
        default=None, foreign_key="atom_feeds.atom_feed_id", ondelete="CASCADE"
    )
    feed: Optional[AtomFeed] = Relationship(back_populates="entries")
    atom_entry_id: IDField = Field(None, primary_key=True)

    id: str = Field(
        ...,
        description="The value of the `id` field *in the <entry> item* - "
        "NOT a primary key for the database",
    )
    title: str = Field(max_length=4096)
    summary: str = Field(max_length=2**13)
    link: MaxLenURL
    author_name: str = Field(max_length=256)
    author_uri: MaxLenURL | None = None
    published: UTCDateTime | None = None
    updated: UTCDateTime
