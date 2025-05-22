from sqlmodel import select

from sciop.models import TorrentFile, TorrentFileCreate

from ..conftest import DATA_DIR


def test_torrent_max_size_from_config():
    """
    Torrent class shouldn't have its own independent max size.

    Remove this once we replace torf
    """
    from sciop.config import get_config
    from sciop.models import Torrent

    assert get_config().upload_limit == Torrent.MAX_TORRENT_FILE_SIZE


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
    from sciop.models import Torrent

    torrent = Torrent.read(DATA_DIR / "test_hybrid_w_pad.torrent")
    files = torrent.files
    assert not any([".pad" in f.path for f in files])
    assert torrent.size == 9085750369


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
