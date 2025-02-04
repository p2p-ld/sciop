"""
See https://www.bittorrent.org/beps/bep_0036.html
for the bittorrent RSS spec
"""

from datetime import UTC, datetime

from sciop.models import DatasetInstance
from sciop.vendor.fastapi_rss.models import GUID, Enclosure, EnclosureAttrs, Item, RSSFeed


class TorrentItem(Item):
    """An individual torrent within a torrent RSS feed"""

    @classmethod
    def from_instance(cls, instance: DatasetInstance) -> "TorrentItem":
        return TorrentItem(
            title=instance.file_name,
            description=instance.rss_description,
            guid=GUID(content=instance.absolute_download_path),
            enclosure=Enclosure(
                attrs=EnclosureAttrs(
                    url=instance.absolute_download_path,
                    type="application/x-bittorrent",
                    length=instance.torrent.torrent_size,
                )
            ),
        )


class TorrentFeed(RSSFeed):

    @classmethod
    def from_instances(
        cls, title: str, link: str, description: str, instances: list[DatasetInstance]
    ) -> "TorrentFeed":
        items = [TorrentItem.from_instance(instance) for instance in instances]
        return TorrentFeed(
            title=title,
            link=link,
            description=description,
            item=items,
            last_build_date=datetime.now(UTC),
        )
