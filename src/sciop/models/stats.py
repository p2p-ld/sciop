from sqlmodel import Field, SQLModel

from sciop.models.mixins import TableMixin
from sciop.types import IDField, UTCDateTime


class SiteStatsBase(SQLModel):
    n_seeders: int
    n_downloaders: int
    n_datasets: int
    n_uploads: int
    n_files: int
    total_size: int
    total_capacity: int


class SiteStats(SiteStatsBase, TableMixin, table=True):
    __tablename__ = "site_stats"

    site_stats_id: IDField = Field(None, primary_key=True)


class SiteStatsRead(SiteStatsBase):
    created_at: UTCDateTime
