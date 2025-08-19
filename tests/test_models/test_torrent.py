from typing import Callable as C

from sqlmodel import select
from torrent_models import Torrent

from sciop.models import TorrentFile, TorrentFileCreate, Webseed

from ..conftest import DATA_DIR


def test_strip_query_params():
    """
    We strip query params from trackers when creating them
    :return:
    """

    c = TorrentFileCreate(
        file_name="text.torrent",
        files=[{"path": "a.com", "size": 100}],
        version="v1",
        v1_infohash="0" * 40,
        total_size=100,
        piece_size=16 * (2**10),
        announce_urls=["https://example.com/announce?secret_key=abcdefg"],
    )
    assert c.announce_urls[0] == "https://example.com/announce"


def test_torrent_exclude_padfiles():
    from torrent_models import Torrent

    torrent = Torrent.read(DATA_DIR / "test_hybrid_w_pad.torrent")
    files = torrent.files
    assert not any([".pad" in f.path for f in files])
    assert torrent.total_size == 9085750369


def test_torrentcreate_exclude_padfiles():
    created = TorrentFileCreate(
        file_name="test_hybrid_w_pad.torrent",
        files=[
            {"path": "a.com", "size": 100},
            {"path": ".pad/59082", "size": 100},
            {"path": "b.com", "size": 100},
            {"path": ".pad/12345", "size": 100},
            {"path": "/notmatch/heli.pad/592834", "size": 100},
        ],
        version="v1",
        v1_infohash="0" * 40,
        total_size=100,
        piece_size=16 * (2**10),
        announce_urls=["https://example.com/announce?secret_key=abcdefg"],
    )
    assert not any([f.path.startswith(".pad") for f in created.files])
    assert any(["heli.pad" in f.path for f in created.files])


def test_get_torrent_stats(session, torrentfile):
    trackers = ["udp://localhost:6969", "udp://localhost:7070"]
    a = torrentfile(announce_urls=trackers)
    a.tracker_links[0].seeders = 1
    a.tracker_links[0].leechers = 4
    a.tracker_links[1].seeders = 3
    a.tracker_links[1].leechers = 2

    session.add(a)
    session.commit()
    session.refresh(a)

    assert a.seeders == 3
    assert a.leechers == 4

    stmt = select(TorrentFile).where(TorrentFile.seeders == 3)
    assert session.exec(stmt).first().torrent_file_id == a.torrent_file_id
    stmt = select(TorrentFile).where(TorrentFile.leechers == 4)
    assert session.exec(stmt).first().torrent_file_id == a.torrent_file_id


def test_webseeds_file_sync(torrentfile: C[[...], TorrentFile], session):
    """
    Webseeds stay in sync in the torrent file as the db object is mutated
    """
    tf = torrentfile(webseeds=None)
    session.add(tf)
    session.commit()
    session.refresh(tf)
    assert Torrent.read(tf.filesystem_path).url_list is None

    # add one with append
    tf.webseeds.append(
        Webseed(url="https://example.com/data", status="validated", is_approved=True)
    )
    session.add(tf)
    session.commit()
    session.refresh(tf)
    assert len(tf.webseeds) == 1
    assert Torrent.read(tf.filesystem_path).url_list == [
        "https://example.com/data"
    ], "Torrent file not updated from append"

    # set
    tf.webseeds = [
        Webseed(url="https://third.example.com/data", status="validated", is_approved=True),
        Webseed(url="https://fourth.example.com/data", status="validated", is_approved=True),
    ]
    session.add(tf)
    session.commit()
    session.refresh(tf)
    assert len(tf.webseeds) == 2
    assert Torrent.read(tf.filesystem_path).url_list == [
        "https://third.example.com/data",
        "https://fourth.example.com/data",
    ], "Torrent file not updated from set"

    # delete
    del tf.webseeds[0]
    session.add(tf)
    session.commit()
    session.refresh(tf)
    assert len(tf.webseeds) == 1
    assert Torrent.read(tf.filesystem_path).url_list == [
        "https://fourth.example.com/data"
    ], "Torrent file not updated from delete"


def test_webseeds_file_sync_moderation(torrentfile: C[[...], TorrentFile], session):
    """
    Webseeds stay in sync in the torrent file when moderation events happen for the webseed.

    Webseeds are not set is_removed=True when removed, they are just deleted,
    so we don't need to test that behavior here.
    """
    tf = torrentfile(webseeds=None)
    # add one with append
    tf.webseeds.append(
        Webseed(url="https://example.com/data", status="in_progress", is_approved=False)
    )
    session.add(tf)
    session.commit()
    session.refresh(tf)
    assert len(tf.webseeds) == 1
    assert Torrent.read(tf.filesystem_path).url_list is None

    tf.webseeds[0].is_approved = True
    session.add(tf.webseeds[0])
    session.commit()
    session.refresh(tf.webseeds[0])
    assert Torrent.read(tf.filesystem_path).url_list == ["https://example.com/data"]

    tf.webseeds[0].is_approved = False
    session.add(tf.webseeds[0])
    session.commit()
    session.refresh(tf.webseeds[0])
    assert Torrent.read(tf.filesystem_path).url_list is None
