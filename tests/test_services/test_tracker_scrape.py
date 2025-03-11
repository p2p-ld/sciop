import hashlib
import random
from datetime import datetime, timedelta
from math import ceil, floor

import pytest

from sciop.services.tracker_scrape import UDPTrackerClient

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
