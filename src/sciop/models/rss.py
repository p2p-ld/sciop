"""
See https://www.bittorrent.org/beps/bep_0036.html
for the bittorrent RSS spec
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from sciop.config import config
from sciop.vendor.fastapi_rss.models import GUID, Enclosure, EnclosureAttrs, Item, RSSFeed

if TYPE_CHECKING:
    from sciop.models import Upload


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
    cache_table: Dict[str, Tuple[datetime, TorrentFeed]] = {}

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

    def get_valid_cached_item(self, key: str) -> Optional[TorrentFeed]:
        if self.is_valid_cache_entry(key):
            return self.cache_table[key][1]
        return None

    def add_to_cache(self, key: str, item: TorrentFeed) -> None:
        self.cache_table[key] = (datetime.now(), item)
