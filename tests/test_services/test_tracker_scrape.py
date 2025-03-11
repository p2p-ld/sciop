import hashlib
import random

import pytest

from sciop.services.tracker_scrape import create_udp_tracker_client

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
    numbers = random.sample(range(1, 100), 10)
    if version == "v1":
        hashes = [hashlib.sha1(str(i).encode("ascii")).hexdigest() for i in numbers]
    else:
        hashes = [hashlib.sha256(str(i).encode("ascii")).hexdigest() for i in numbers]

    client = await create_udp_tracker_client(f"udp://localhost:{port}", hashes)
    await client.initiate_connection()
    assert client.connection_id in proto.connids
    result = await client.request_scrape()

    for hash, stats in result.responses.items():
        assert proto.stats[hash[0:40]]["seeders"] == stats.seeders
        assert proto.stats[hash[0:40]]["leechers"] == stats.leechers
        assert proto.stats[hash[0:40]]["completed"] == stats.completed
