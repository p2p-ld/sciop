"""
See https://www.bittorrent.org/beps/bep_0036.html
for the bittorrent RSS spec
"""

import inspect
from datetime import UTC, datetime
from functools import wraps
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Awaitable,
    Callable,
    Dict,
    List,
    Mapping,
    Optional,
    ParamSpec,
    Tuple,
    TypeAlias,
)

from fastapi import Depends
from fastapi import Request as FARequest
from fasthx.utils import append_to_signature

from sciop.config import config
from sciop.vendor.fastapi_rss.models import GUID, Enclosure, EnclosureAttrs, Item, RSSFeed
from sciop.vendor.fastapi_rss.rss_response import RSSResponse

if TYPE_CHECKING:
    from sciop.models import Upload

    Request: TypeAlias = FARequest
else:
    Request: TypeAlias = Mapping[str, Any]
    """
    Alias for `Request` arguments.

    Workaround for this FastAPI bug: https://github.com/fastapi/fastapi/discussions/12403.
    And here's a FastAPI bugfix: https://github.com/fastapi/fastapi/pull/12406.

    This workaround should be removed when FastAPI had several new releases with the fix.
    
    Stolen from fasthx.dependencies
    """

P = ParamSpec("P")


class TorrentItem(Item):
    """An individual torrent within a torrent RSS feed"""

    @classmethod
    def from_upload(cls, upload: "Upload") -> "TorrentItem":
        return TorrentItem(
            title=upload.file_name,
            description=upload.rss_description,
            guid=GUID(content=upload.absolute_download_path),
            enclosure=Enclosure(
                attrs=EnclosureAttrs(
                    url=upload.absolute_download_path,
                    type="application/x-bittorrent",
                    length=upload.torrent.torrent_size,
                )
            ),
        )


class TorrentFeed(RSSFeed):

    @classmethod
    def from_uploads(
        cls, title: str, link: str, description: str, uploads: list["Upload"]
    ) -> "TorrentFeed":
        items = [TorrentItem.from_upload(upload) for upload in uploads]
        return TorrentFeed(
            title=title,
            link=link,
            description=description,
            item=items,
            last_build_date=datetime.now(UTC),
        )


class RSSFeedCache:
    def __init__(self):
        self.cache_table: Dict[str, Tuple[datetime, bytes]] = {}
        self.time_last_cleared_cache: datetime = datetime.now()

    def clean_cache(self) -> None:
        keys_to_purge: List[str] = []
        purge_time_before = datetime.now() - config.rss_feed_cache_delta
        for key, val_tuple in self.cache_table:
            time_stored, data = val_tuple
            if time_stored < purge_time_before:
                keys_to_purge.append(key)

        for purge_key in keys_to_purge:
            del self.cache_table[purge_key]

    def is_valid_cache_entry(self, key: str) -> bool:
        if key not in self.cache_table:
            return False

        return self.cache_table[key][0] > datetime.now() - config.rss_feed_cache_delta

    def get_valid_cached_item(self, key: str) -> Optional[bytes]:
        if datetime.now() - self.time_last_cleared_cache > config.rss_feed_cache_clear_time:
            self.clean_cache()
        if self.is_valid_cache_entry(key):
            return self.cache_table[key][1]
        return None

    def add_to_cache(self, key: str, item: bytes) -> None:
        self.cache_table[key] = (datetime.now(), item)


def _get_request(request: FARequest) -> Request:
    return request


RequireRequest = Annotated[Request, Depends(_get_request)]


class RSSCacheWrapper:
    """
    Cache RSS responses, keyed by the request path, and expired according to
    :attr:`.Config.rss_feed_cache_delta`.

    Applied as a decorator to individual routes rather than used as an actual middleware,
    see https://github.com/fastapi/fastapi/discussions/7691#discussioncomment-7529698
    """

    def __init__(self) -> None:
        self.rss_cache = RSSFeedCache()

    def wrap(
        self, func: Callable[P, Awaitable[RSSResponse]]
    ) -> Callable[..., Awaitable[RSSResponse]]:
        @wraps(func)
        async def _inner(
            _rss_request: RequireRequest, *args: P.args, **kwargs: P.kwargs
        ) -> RSSResponse:
            if (
                cache_result := self.rss_cache.get_valid_cached_item(_rss_request.url.path)
            ) is not None:
                return RSSResponse(cache_result)

            response: RSSResponse = await func(*args, **kwargs)
            self.rss_cache.add_to_cache(_rss_request.url.path, response.body)
            return response

        return append_to_signature(
            _inner,  # type: ignore[arg-type]
            inspect.Parameter(
                "_rss_request",
                inspect.Parameter.KEYWORD_ONLY,
                annotation=RequireRequest,
            ),
        )
