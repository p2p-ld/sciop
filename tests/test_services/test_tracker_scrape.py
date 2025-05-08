import hashlib
import random
from datetime import UTC, datetime, timedelta
from math import ceil, floor

import flatbencode
import pytest
from pytest_httpx import HTTPXMock
from sqlmodel import select

from sciop.models import TorrentFile, TorrentTrackerLink
from sciop.services.tracker_scrape import (
    ScrapeResponse,
    UDPTrackerClient,
    gather_scrapable_torrents,
    scrape_http_tracker,
    scrape_torrent_stats,
)

from ..fixtures.tracker import MockTrackerProtocol


@pytest.mark.parametrize("version", ["v1", "v2"])
@pytest.mark.asyncio(loop_scope="module")
async def test_scrape_tracker(tracker, version):
    """
    We can correctly scrape data for a torrent
    :param tracker:
    :return:
    """
    transport, proto, port = tracker
    proto: MockTrackerProtocol
    numbers = random.sample(range(1, 1000), 10)
    if version == "v1":
        hashes = [hashlib.sha1(str(i).encode("ascii")).hexdigest() for i in numbers]
    else:
        hashes = [hashlib.sha256(str(i).encode("ascii")).hexdigest() for i in numbers]

    client = await UDPTrackerClient.from_url(f"udp://localhost:{port}")
    result = await client.scrape(hashes)
    assert await client.connection_id in proto.connids

    for hash, stats in result.responses.items():
        assert proto.stats[hash[0:40]]["seeders"] == stats.seeders
        assert proto.stats[hash[0:40]]["leechers"] == stats.leechers
        assert proto.stats[hash[0:40]]["completed"] == stats.completed


@pytest.mark.asyncio(loop_scope="module")
async def test_scrape_pagination(tracker):
    """
    Split tracker requests into batches of 70, reusing connection ID
    """
    transport, proto, port = tracker
    n_hashes = 300
    numbers = random.sample(range(1, 1000), n_hashes)
    hashes = [hashlib.sha1(str(i).encode("ascii")).hexdigest() for i in numbers]

    client = await UDPTrackerClient.from_url(f"udp://localhost:{port}")
    result = await client.scrape(hashes)

    assert len(proto.batches) == ceil(len(numbers) / 70)
    for i in range(floor(len(numbers) / 70)):
        assert len(proto.batches[i]["infohashes"]) == 70
    assert len(proto.batches[-1]["infohashes"]) == len(numbers) % 70

    all_hashes = []
    for batch in proto.batches:
        all_hashes.extend(batch["infohashes"])
    assert all_hashes == hashes

    tids = {batch["transaction_id"] for batch in proto.batches}
    cids = {batch["connection_id"] for batch in proto.batches}
    assert len(tids) == 1
    assert len(cids) == 1

    assert len(proto.connids) == 1


@pytest.mark.asyncio(loop_scope="module")
async def test_scrape_autoid(tracker):
    """
    Automatically refresh connection and transaction IDs on expiration
    """
    transport, proto, port = tracker

    client = await UDPTrackerClient.from_url(f"udp://localhost:{port}")

    # get one first batch
    numbers = random.sample(range(1, 1000), 140)
    hashes = [hashlib.sha1(str(i).encode("ascii")).hexdigest() for i in numbers[0:70]]
    result = await client.scrape(hashes)

    # expire connection id
    client._connection_id_created = datetime.now() - timedelta(hours=1)

    # request another batch
    hashes = [hashlib.sha1(str(i).encode("ascii")).hexdigest() for i in numbers[70:]]
    result2 = await client.scrape(hashes)

    assert len(proto.connids) == 2


def test_gather_scrapable_torrents(torrentfile, session):
    """
    We should update only torrents that we haven't scraped recently,
    and whose trackers aren't unresponsive
    """

    recent = "udp://scraped.recently"
    unresponsive = "udp://un.responsive"
    extra = "udp://ex.tra"
    not_recent = "udp://not.recent"

    torrent: TorrentFile = torrentfile(extra_trackers=[recent, unresponsive, extra, not_recent])
    v1_only = torrentfile(v2_infohash=None, extra_trackers=[extra])

    torrent.tracker_links_map[recent].last_scraped_at = datetime.now(UTC)
    torrent.tracker_links_map[unresponsive].tracker.next_scrape_after = datetime.now(
        UTC
    ) + timedelta(minutes=30)
    torrent.tracker_links_map[not_recent].last_scraped_at = datetime.now(UTC) - timedelta(weeks=1)

    session.add(torrent)
    session.commit()

    scrapable = gather_scrapable_torrents()
    assert recent not in scrapable
    assert unresponsive not in scrapable
    assert len(scrapable[extra]) == 2
    assert len(scrapable[not_recent]) == 1
    assert not any([k.startswith("wss") for k in scrapable])


@pytest.mark.asyncio
async def test_scrape_torrent_stats(torrentfile, session, unused_udp_port_factory, tracker_factory):
    ports = [unused_udp_port_factory(), unused_udp_port_factory()]
    trackers = [f"udp://localhost:{ports[0]}", f"udp://localhost:{ports[1]}"]
    a = torrentfile(announce_urls=trackers)
    b = torrentfile(announce_urls=trackers)
    c = torrentfile(announce_urls=trackers)

    ta, _ = tracker_factory(port=ports[0])
    tb, _ = tracker_factory(port=ports[1])

    async with (
        ta as (ta_transport, ta_proto),
        tb as (tb_transport, tb_proto),
    ):
        await scrape_torrent_stats()

    links = session.exec(select(TorrentTrackerLink)).all()
    for link in links:
        if link.tracker.announce_url == trackers[0]:
            assert ta_proto.stats[link.torrent.v1_infohash[0:40]]["seeders"] == link.seeders
            assert ta_proto.stats[link.torrent.v1_infohash[0:40]]["leechers"] == link.leechers
            assert ta_proto.stats[link.torrent.v1_infohash[0:40]]["completed"] == link.completed
        else:
            assert tb_proto.stats[link.torrent.v1_infohash[0:40]]["seeders"] == link.seeders
            assert tb_proto.stats[link.torrent.v1_infohash[0:40]]["leechers"] == link.leechers
            assert tb_proto.stats[link.torrent.v1_infohash[0:40]]["completed"] == link.completed


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tracker",
    [
        "https://academictorrents.com/announce.php",
    ],
)
async def test_scrape_http_tracker_single(tracker, monkeypatch, httpx_mock: HTTPXMock):
    """
    When an HTTP tracker doesn't return all the infohashes results for us,
    and we have configured ourselves to do so,
    we should request each infohash individually
    """
    from sciop.services import tracker_scrape

    monkeypatch.setattr(
        tracker_scrape.config.tracker_scraping,
        "http_tracker_single_only",
        ["https://academictorrents.com/announce.php"],
    )
    monkeypatch.setattr(
        tracker_scrape.config.tracker_scraping,
        "http_tracker_scrape_all",
        [],
    )

    # mock responses
    httpx_mock.add_response(
        url="https://academictorrents.com/scrape.php?info_hash=%0A%24m%40%B8%F8%295%83%F9T%A7.%A5%89%80%ED%D1%1E%F4"
        "&info_hash=%BA%05%19%990%1B%10%9E%AB7%D1o%02%7B%3FI%AD%E2%DE%13"
        "&info_hash=K%A6%81%15%88v%D89%97%3B%A9%93%14%B7%F2%8F%F3V%BB%F1",
        content=b"d5:filesd20:K\xa6\x81\x15\x88v\xd89\x97;\xa9\x93\x14\xb7\xf2\x8f\xf3V\xbb\xf1d8:completei40e10:downloadedi58e10:incompletei1eeee",
    )
    httpx_mock.add_response(
        url="https://academictorrents.com/scrape.php?info_hash=%0A%24m%40%B8%F8%295%83%F9T%A7.%A5%89%80%ED%D1%1E%F4",
        content=b"d5:filesd20:\n$m@\xb8\xf8)5\x83\xf9T\xa7.\xa5\x89\x80\xed\xd1\x1e\xf4d8:completei31e10:downloadedi39e10:incompletei2eeee",
    )
    httpx_mock.add_response(
        url="https://academictorrents.com/scrape.php?info_hash=K%A6%81%15%88v%D89%97%3B%A9%93%14%B7%F2%8F%F3V%BB%F1",
        content=b"d5:filesd20:K\xa6\x81\x15\x88v\xd89\x97;\xa9\x93\x14\xb7\xf2\x8f\xf3V\xbb\xf1d8:completei40e10:downloadedi58e10:incompletei1eeee",
    )
    httpx_mock.add_response(
        url="https://academictorrents.com/scrape.php?info_hash=%BA%05%19%990%1B%10%9E%AB7%D1o%02%7B%3FI%AD%E2%DE%13",
        content=b"d5:filesd20:\xba\x05\x19\x990\x1b\x10\x9e\xab7\xd1o\x02{?I\xad\xe2\xde\x13d8:completei31e10:downloadedi205e10:incompletei22eeee",
    )

    infohashes = [
        "0a246d40b8f8293583f954a72ea58980edd11ef4",
        "ba051999301b109eab37d16f027b3f49ade2de13",
        "4ba681158876d839973ba99314b7f28ff356bbf1",
    ]
    res = await scrape_http_tracker(tracker, infohashes)
    assert len(res.errors) == 0
    assert len(res.responses) == 3
    for ih, response in res.responses.items():
        assert ih in infohashes
        assert response.seeders > 0
        assert response.completed > 0
        assert response.announce_url == tracker


async def test_scrape_http_tracker_all(monkeypatch, httpx_mock: HTTPXMock):
    """
    We can scrape trackers who only return multiple infohashes by scraping all data they have
    :param monkeypatch:
    :param httpx_mock:
    :return:
    """
    from sciop.services import tracker_scrape

    tracker = "https://academictorrents.com/announce.php"
    monkeypatch.setattr(
        tracker_scrape.config.tracker_scraping,
        "http_tracker_single_only",
        [],
    )
    monkeypatch.setattr(
        tracker_scrape.config.tracker_scraping,
        "http_tracker_scrape_all",
        [tracker],
    )

    httpx_mock.add_response(
        url="https://academictorrents.com/scrape.php",
        content=b"d5:filesd20:\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00d8:completei0e10:downloadedi0e10:incompletei0ee20:\x19V\xfbU\xa8S\xaa\xf0U\x8a \xf7Z\xdf\xcbe\x15K|jd8:completei6e10:downloadedi13e10:incompletei6ee20:\xb8\x1c\x1b\xe4\xf0\xb7\xecb.\xc9\xcb\xde%Q\xaa\xf1T}\xc3<d8:completei3e10:downloadedi1e10:incompletei4eeee",  # noqa: E501
    )
    infohashes = [
        "b81c1be4f0b7ec622ec9cbde2551aaf1547dc33c",
        "1956fb55a853aaf0558a20f75adfcb65154b7c6a",
    ]
    res = await scrape_http_tracker(tracker, infohashes)
    assert len(res.errors) == 0
    assert len(res.responses) == 2
    assert res.responses[infohashes[0]] == ScrapeResponse(
        infohash=infohashes[0], announce_url=tracker, seeders=3, completed=1, leechers=4
    )
    assert res.responses[infohashes[1]] == ScrapeResponse(
        infohash=infohashes[1], announce_url=tracker, seeders=6, completed=13, leechers=6
    )


@pytest.mark.parametrize("infohashes", [["0" * 40], ["0" * 40, "1" * 40]])
async def test_empty_responses_are_errors(httpx_mock: HTTPXMock, infohashes):
    """
    Empty responses should be treated as errors,
    this causes us to exponentially back off making requests to them
    """
    httpx_mock.add_response(content=flatbencode.encode({b"files": {}}), is_reusable=True)
    res = await scrape_http_tracker("http://example.com/announce", infohashes)

    assert len(res.errors) == 1
    assert res.errors[0].type == "no_response"
