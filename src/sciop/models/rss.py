"""
See https://www.bittorrent.org/beps/bep_0036.html
for the bittorrent RSS spec
"""

from datetime import UTC, datetime

from sciop.models import Upload
from sciop.vendor.fastapi_rss.models import GUID, Enclosure, EnclosureAttrs, Item, RSSFeed


class TorrentItem(Item):
    """An individual torrent within a torrent RSS feed"""

    @classmethod
    def from_upload(cls, upload: Upload) -> "TorrentItem":
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
        cls, title: str, link: str, description: str, uploads: list[Upload]
    ) -> "TorrentFeed":
        items = [TorrentItem.from_upload(upload) for upload in uploads]
        return TorrentFeed(
            title=title,
            link=link,
            description=description,
            item=items,
            last_build_date=datetime.now(UTC),
        )
