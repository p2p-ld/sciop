import asyncio
import binascii
import struct
from asyncio import DatagramProtocol, DatagramTransport, Event
from datetime import datetime, timedelta
from random import randint
from types import TracebackType
from typing import Any, Optional, TypedDict

import pytest
import pytest_asyncio

from sciop.logging import init_logger

__all__ = [
    "MockTrackerProtocol",
    "MockUDPServer",
    "RequestBatch",
    "tracker",
    "tracker_factory",
]


class RequestBatch(TypedDict):
    transaction_id: int
    connection_id: int
    infohashes: list[str]


class MockTrackerProtocol(DatagramProtocol):
    def __init__(self, loop: Optional[asyncio.AbstractEventLoop] = None, *args: Any, **kwargs: Any):
        self.events = {}
        self.stats = {}
        self.transport = None
        self.connection_lost_received = Event()
        self.logger = init_logger("mock.tracker")
        self.connids: dict[int, datetime] = {}
        self.activity: dict[tuple, datetime] = {}
        self.batches: list[RequestBatch] = []
        self.loop = loop or asyncio.get_event_loop()
        self.logger.info("Mock tracker initialized")

        super().__init__(*args, **kwargs)

    def connection_made(self, transport: DatagramTransport) -> None:
        self.logger.info(f"Connection made {transport}")
        self.transport = transport

    def datagram_received(self, data: bytes, addr: tuple) -> None:
        self.logger.debug("Datagram received")
        if len(data) < 16:
            self.logger.warning("Datagram smaller than 16 bytes.")
            return

        connid, action, tid = struct.unpack("!qII", data[:16])

        if action == 0:
            res = self.process_connect(addr, connid, tid, data[16:])
        elif action == 1:
            res = self.error(tid, "Announces are not implemented")
        elif action == 2:
            res = self.process_scrape(addr, connid, tid, data[16:])
        else:
            res = self.error(tid, "Unrecognized action")

        if res is not None:
            self.transport.sendto(res, addr)

    def error(self, tid: int, msg: str | bytes) -> bytes:
        if isinstance(msg, str):
            msg = msg.encode("utf-8")
        self.logger.error(f"Error: {msg.decode('utf-8')}")
        return struct.pack("!II", 3, tid) + msg

    def process_connect(self, addr: tuple, connid: int, tid: int, data: bytes) -> bytes:
        self.logger.info("Received connect message.")
        if connid == 0x41727101980:
            connid = randint(-(2**32), 2**32)
            self.connids[connid] = datetime.now()
            self.activity[addr] = datetime.now()
            return struct.pack("!IIq", 0, tid, connid)
        else:
            return self.error(tid, "Invalid protocol identifier")

    def process_scrape(self, addr: tuple, connid: int, tid: int, data: bytes) -> bytes:
        # make sure the provided connection identifier is valid
        timestamp = self.connids.get(connid, None)
        last_valid = datetime.now() - timedelta(minutes=2)
        if not timestamp:
            # we didn't generate that connection identifier
            return self.error(tid, "Invalid connection identifier.")
        elif timestamp < last_valid:
            # we did generate that identifier, but it's too
            # old. remove it and send an error.
            return self.error(tid, "Old connection identifier.")

        hashes = [
            binascii.b2a_hex(data[i : i + 20]).decode("ascii") for i in range(0, len(data), 20)
        ]
        self.logger.info("Received scrape for hashes: %s", hashes)
        self.batches.append({"transaction_id": tid, "connection_id": connid, "infohashes": hashes})
        return_msg = struct.pack("!II", 2, tid)
        for hash in hashes:
            if hash not in self.stats:
                self.stats[hash] = {
                    "seeders": randint(0, 2**32),
                    "completed": randint(0, 2**32),
                    "leechers": randint(0, 2**32),
                }

            return_msg += struct.pack(
                "!III",
                self.stats[hash]["seeders"],
                self.stats[hash]["completed"],
                self.stats[hash]["leechers"],
            )

        return return_msg


class MockUDPServer:
    def __init__(
        self,
        protocol: type[DatagramProtocol],
        host: str = "0.0.0.0",
        port: int = 6881,
        loop: Optional[asyncio.AbstractEventLoop] = None,
    ):
        self.host = host
        self.port = port
        self.loop = loop or asyncio.get_event_loop()
        self.protocol = protocol
        self.transport = None

    async def __aenter__(self) -> tuple[DatagramTransport, DatagramProtocol]:
        transport, proto = await self.loop.create_datagram_endpoint(
            lambda: self.protocol(), local_addr=(self.host, self.port)
        )
        self.transport = transport
        return transport, proto

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ):
        self.transport.close()
        self.transport = None


@pytest_asyncio.fixture(loop_scope="module")
async def tracker(unused_udp_port: int) -> tuple[DatagramTransport, MockTrackerProtocol, int]:
    async with MockUDPServer(MockTrackerProtocol, port=unused_udp_port) as server:
        transport, proto = server
        yield transport, proto, unused_udp_port


@pytest.fixture
def tracker_factory(unused_udp_port: int) -> MockTrackerProtocol:
    def _tracker_factory(port: Optional[int] = unused_udp_port) -> MockTrackerProtocol:
        mock = MockUDPServer(MockTrackerProtocol, port=port)
        return mock, port

    return _tracker_factory
