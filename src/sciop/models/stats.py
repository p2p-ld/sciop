from datetime import datetime, UTC
from typing import Optional

from sqlmodel import Field

from sciop.models.base import SQLModel
from sciop.models.mixins import TableMixin
from sciop.types import IDField, UTCDateTime


class SiteStatsBase(SQLModel):
    """
    Site summary stats

    Items that require tracker scraping to be enabled are optional
    """
    n_seeders: int | None = None
    n_downloaders: int | None = None
    n_datasets: int
    n_uploads: int
    n_files: int
    total_size: int
    total_capacity: int | None = None


class SiteStats(SiteStatsBase, TableMixin, table=True):
    __tablename__ = "site_stats"
    created_at: Optional[UTCDateTime] = Field(default_factory=lambda: datetime.now(UTC), index=True)
    site_stats_id: IDField = Field(None, primary_key=True)


class SiteStatsRead(SiteStatsBase):
    created_at: UTCDateTime
