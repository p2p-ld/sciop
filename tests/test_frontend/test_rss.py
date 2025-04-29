import pytest
from lxml import etree

from sciop.models import TorrentFile, Upload


@pytest.fixture()
def seed_feed_uploads(upload, torrentfile, dataset, session) -> tuple[Upload, ...]:
    ds = dataset()

    seeds = [None, 0, 1, 5, 10, 11]
    uls = []
    for seed in seeds:
        t: TorrentFile = torrentfile(file_name=f"{seed}.torrent")
        if seed is not None:
            t.tracker_links[0].seeders = seed
            session.add(t)
            session.commit()

        ul = upload(dataset_=ds, torrentfile_=t)
        uls.append(ul)
    return tuple(uls)


@pytest.fixture()
def size_feed_uploads(upload, torrentfile, dataset, session) -> tuple[Upload, ...]:
    ds = dataset()

    sizes = [10 * (2**40), 5 * (2**40), 1 * (2**40), 500 * (2**30), 2**30, 1**20]
    names = ["10tb", "5tb", "1tb", "500gb", "1gb", "1mb"]
    uls = []
    for name, size in zip(names, sizes):
        t: TorrentFile = torrentfile(file_name=f"{name}.torrent")
        t.total_size = size
        session.add(t)
        session.commit()
        ul = upload(dataset_=ds, torrentfile_=t)
        uls.append(ul)
    return tuple(uls)


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


def test_escaped_urls(upload, torrentfile, dataset, client):
    """
    Torrents with spaces don't break RSS feeds
    """
    t = torrentfile(file_name="torrent with spaces.torrent")
    ds = dataset(tags=["test"])
    ul = upload(torrentfile_=t, dataset_=ds)
    feed = client.get("/rss/tag/test.rss")
    assert feed.status_code == 200
    tree = etree.fromstring(feed.text.encode("utf-8"))
    guid = tree.find(".//guid").text
    assert "torrent%20with%20spaces.torrent" in guid


@pytest.mark.skip()
def test_no_include_removed():
    pass


@pytest.mark.skip()
def test_no_include_unapproved():
    pass


def test_unseeded_feed(client, seed_feed_uploads):
    """
    The no-seeds feed should contain torrents with zero seeds
    (which is different than `None` seeds)
    """
    feed = client.get("/rss/seeds/unseeded.rss")

    tree = etree.fromstring(feed.text.encode("utf-8"))
    items = tree.findall(".//item")
    assert len(items) == 1
    assert items[0].find("title").text == "0.torrent"


def test_low_seeds_feed(client, seed_feed_uploads):
    """
    Low seeds feed should show items with 1-10 seeeds
    """
    feed = client.get("/rss/seeds/1-10.rss")

    tree = etree.fromstring(feed.text.encode("utf-8"))
    items = tree.findall(".//item")
    assert len(items) == 3
    names = [item.find("title").text for item in items]
    assert sorted(names) == sorted(["1.torrent", "5.torrent", "10.torrent"])


def test_1tb_feed(client, size_feed_uploads, session):
    """
    1TB feed should include torrents larger than 1TB
    """
    feed = client.get("/rss/size/1tb.rss")

    tree = etree.fromstring(feed.text.encode("utf-8"))
    items = tree.findall(".//item")
    assert len(items) == 3

    names = [item.find("title").text for item in items]
    assert sorted(names) == sorted(["10tb.torrent", "5tb.torrent", "1tb.torrent"])


def test_5tb_feed(client, size_feed_uploads):
    """
    1TB feed should include torrents larger than 5TB
    """
    feed = client.get("/rss/size/5tb.rss")

    tree = etree.fromstring(feed.text.encode("utf-8"))
    items = tree.findall(".//item")
    assert len(items) == 2

    names = [item.find("title").text for item in items]
    assert sorted(names) == sorted(["10tb.torrent", "5tb.torrent"])
