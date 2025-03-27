import pytest
from lxml import etree


def test_tag_feed(upload, dataset, client):
    ul = upload()
    ds = dataset(slug="second-dataset", tags=["default", "tag2"])
    ul2 = upload(dataset_=ds)

    feed = client.get("/rss/tag/default.rss")
    tree = etree.fromstring(feed.text.encode("utf-8"))
    assert tree.find("./channel/title").text == "Sciop tag: default"
    items = tree.findall(".//item")
    assert len(items) == 2
    # items are reverse chron
    assert "second-dataset" in items[0].find("description").text
    # torrents correctly handled
    for ul_, item in zip((ul2, ul), items):
        assert ul_.infohash in item.find("guid").text
        assert item.find("guid").text.endswith(".torrent")
        enclosure = item.find("enclosure")
        assert enclosure.attrib["type"] == "application/x-bittorrent"
        assert enclosure.attrib["url"].endswith(".torrent")


@pytest.mark.skip()
def test_no_include_removed():
    pass


@pytest.mark.skip()
def test_no_include_unapproved():
    pass
