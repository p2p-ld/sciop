from datetime import datetime, timedelta
from typing import Callable

import pytest
from lxml import etree

from sciop.frontend import rss as rss_module
from sciop.frontend.rss import SIZE_BREAKPOINTS
from sciop.models import TorrentFile, Upload
from sciop.models.rss import RSSCacheWrapper, RSSFeedCache


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
def size_feed_uploads(upload, torrentfile, dataset, session) -> Callable[[int], tuple[Upload, ...]]:

    ds = dataset()

    def _size_feed_uploads(size: int) -> tuple[Upload, ...]:

        sizes = [size - 1, size, size + 1]
        names = ["smaller", "equal", "larger"]
        uls = []
        for name, size in zip(names, sizes):
            t: TorrentFile = torrentfile(file_name=f"{name}.torrent")
            t.total_size = size
            session.add(t)
            session.commit()
            ul = upload(dataset_=ds, torrentfile_=t)
            uls.append(ul)
        return tuple(uls)

    return _size_feed_uploads


@pytest.fixture()
def rss_cache(monkeypatch: pytest.MonkeyPatch) -> RSSCacheWrapper:
    """Fresh, monkeypatched version of the rss feed cache"""
    rss_cache = RSSFeedCache(delta=1, clear_timeout=1)
    monkeypatch.setattr(rss_module.rss_cache, "rss_cache", rss_cache)

    return rss_module.rss_cache


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


@pytest.mark.parametrize("size", SIZE_BREAKPOINTS.keys())
def test_gt_feed(size, client, size_feed_uploads, session):
    """
    Less-than feeds should include everything smaller than the breakpoint
    """
    size_title, size_int = SIZE_BREAKPOINTS[size]
    smaller, equal, larger = size_feed_uploads(size_int)

    feed = client.get(f"/rss/size/gt/{size}.rss")
    assert feed.status_code == 200

    tree = etree.fromstring(feed.text.encode("utf-8"))
    items = tree.findall(".//item")
    assert len(items) == 2

    names = [item.find("title").text for item in items]
    assert sorted(names) == sorted(["equal.torrent", "larger.torrent"])


@pytest.mark.parametrize("size", SIZE_BREAKPOINTS.keys())
def test_lt_feed(size, client, size_feed_uploads, session):
    """
    Less-than feeds should include everything smaller than the breakpoint
    """
    size_title, size_int = SIZE_BREAKPOINTS[size]
    smaller, equal, larger = size_feed_uploads(size_int)

    feed = client.get(f"/rss/size/lt/{size}.rss")
    assert feed.status_code == 200

    tree = etree.fromstring(feed.text.encode("utf-8"))
    items = tree.findall(".//item")
    assert len(items) == 2

    names = [item.find("title").text for item in items]
    assert sorted(names) == sorted(["smaller.torrent", "equal.torrent"])


def test_cache_hit(client, size_feed_uploads, rss_cache, capsys, upload, dataset):
    """
    When we hit an RSS feed twice, we should return a cached copy
    """
    cache_key = "/rss/all.rss"
    assert cache_key not in rss_cache.rss_cache.cache_table
    feed_1 = client.get(cache_key)
    assert feed_1.status_code == 200
    assert cache_key in rss_cache.rss_cache.cache_table

    ds = dataset(slug="cache-hit")
    _ = upload(dataset_=ds)

    feed_2 = client.get(cache_key)
    assert feed_1.status_code == 200

    # If they were cached, they should be identical
    # (i.e. the timestamp, and should not include the new upload)
    assert feed_1.content == feed_2.content
    out = capsys.readouterr().out
    assert sum(["Cache miss" in line for line in out.split("\n")]) == 1
    assert sum(["Cache hit" in line for line in out.split("\n")]) == 1


def test_cache_evict(client, size_feed_uploads, rss_cache, capsys, upload, dataset):
    """
    When a cached feed is expired, we should recompute the feed
    """
    cache_key = "/rss/all.rss"
    assert cache_key not in rss_cache.rss_cache.cache_table
    feed_1 = client.get(cache_key)
    assert feed_1.status_code == 200
    assert cache_key in rss_cache.rss_cache.cache_table

    # expire the cache clear interval and the individual item
    cache_clear_time = datetime.now() - timedelta(hours=1)
    rss_cache.rss_cache.cache_table[cache_key] = (
        cache_clear_time,
        rss_cache.rss_cache.cache_table[cache_key][1],
    )
    rss_cache.rss_cache.time_last_cleared_cache = cache_clear_time

    # make a new item
    ds = dataset(slug="cache-miss")
    _ = upload(dataset_=ds)

    feed_2 = client.get(cache_key)
    assert feed_1.status_code == 200

    # The second feed should be recomputed
    assert feed_1.content != feed_2.content
    out = capsys.readouterr().out
    assert sum(["Cache miss" in line for line in out.split("\n")]) == 2
    assert sum(["Cleaning cache" in line for line in out.split("\n")]) == 1
    assert sum(["Cache hit" in line for line in out.split("\n")]) == 0
    # we should have gotten a new cache clear time while clearing
    assert rss_cache.rss_cache.time_last_cleared_cache != cache_clear_time
