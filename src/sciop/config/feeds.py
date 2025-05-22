from datetime import timedelta

from pydantic import BaseModel

from sciop.types import DeltaMinutes


class FeedConfig(BaseModel):
    """Configuration for RSS Feeds"""

    cache_delta: DeltaMinutes = timedelta(minutes=60)
    """The amount of time a cached rss feed entry will be considered valid"""
    cache_clear_time: DeltaMinutes = timedelta(minutes=10)
    """The amount of time between clearing all the dead keys in the rss feed cache"""
