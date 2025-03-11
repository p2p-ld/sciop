import hashlib
import random
from datetime import UTC, datetime, timedelta
from math import ceil, floor

import pytest
from sqlmodel import select

from sciop.models import TorrentFile, TorrentTrackerLink
from sciop.services.tracker_scrape import (
    UDPTrackerClient,
    gather_scrapable_torrents,
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
    assert not any([k.startswith("http") for k in scrapable])


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
            assert ta_proto.stats[link.torrent.infohash[0:40]]["seeders"] == link.seeders
            assert ta_proto.stats[link.torrent.infohash[0:40]]["leechers"] == link.leechers
            assert ta_proto.stats[link.torrent.infohash[0:40]]["completed"] == link.completed
        else:
            assert tb_proto.stats[link.torrent.infohash[0:40]]["seeders"] == link.seeders
            assert tb_proto.stats[link.torrent.infohash[0:40]]["leechers"] == link.leechers
            assert tb_proto.stats[link.torrent.infohash[0:40]]["completed"] == link.completed
