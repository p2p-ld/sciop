import asyncio
import binascii
import enum
import struct
from types import TracebackType
from typing import Any, Optional
from urllib.parse import urlparse

import aiodns

from sciop.exceptions import TrackerURLException, UDPTrackerException
from sciop.logging import init_logger

loop = asyncio.get_event_loop()
logger = init_logger("tracker.udp")

resolver = aiodns.DNSResolver()
MAGIC_VALUE = 0x41727101980
MAX_SCRAPE = 70


# https://www.bittorrent.org/beps/bep_0015.html
class ACTIONS(enum.IntEnum):
    REQUEST_ID = 0
    REQUEST_ANNOUNCE = 1
    REQUEST_SCRAPE = 2
    ERROR = 4  # oh uh


class UDPReadLock(asyncio.Queue):
    async def __aenter__(self):
        self.put_nowait(None)
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ):
        self.get_nowait()
        self.task_done()
        return None


class UDPReadWriteLock:
    """A slightly tested read/write lock for our dictionary of torrent hashes"""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._read = UDPReadLock()

    @property
    async def read(self) -> UDPReadLock:
        # first try and get the lock; if we're waiting on a write, it'll be locked already
        async with self._lock:
            pass  # we do not want to hold the lock while reading
        return self._read

    async def __aenter__(self):
        await self._lock.acquire()  # get the lock, no matter what
        if not self._read.empty():
            await self._read.join()  # wait for the queue to to empty if things are reading.

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ):
        self._lock.release()


class SciOpUDPCounter:
    """
    Task safe class for generating unique 32 bit transaction IDs.  A
    prefix may be used and generated for ensuring uniqueness.
    """

    def __init__(self, starting: int = -1, db_start: int = 0):
        self._tracker_trans_id: int = starting
        self._db_prefix: int = db_start
        self.lock = asyncio.Lock()

    async def next(self) -> tuple[int, int]:
        async with self.lock:
            if self._tracker_trans_id > 4294967295:  # 32 bit int, I think
                self._tracker_trans_id = 0
                self._db_prefix += 1
            else:
                self._tracker_trans_id += 1
            id = self._tracker_trans_id
            db = self._db_prefix
        return db, id

    async def current(self) -> tuple[int, int]:
        async with self.lock:
            id = self._tracker_trans_id
            db = self._db_prefix
        return db, id


counter = SciOpUDPCounter()


# from https://github.com/mhdzumair/PyAsyncTracker/blob/main/src/pyasynctracker/scraper.py,
# with love
class UDPProtocolHandler(asyncio.DatagramProtocol):
    def __init__(self, message: bytes, transaction_id: int, active: asyncio.Future):
        self.message: bytes = message
        self.id: int = transaction_id
        self.success: asyncio.Future = active
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.result: Optional[tuple[bytes, tuple[str | Any, int]]] = (
            None  # this might be _too_ strong of typing.
        )

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport
        self.transport.sendto(self.message)

    def datagram_received(self, data: bytes, addr: tuple[str | Any, int]) -> None:
        self.result = (data, addr)
        self.success.set_result(True)

    def error_received(self, exc: OSError) -> None:
        self.success.set_result(False)

    def connection_lost(self, exc: OSError) -> None:
        if exc:
            self.success.set_result(True)


class UDPTrackerClient:
    def __init__(
        self,
        ip: str,
        port: int,
        torrents: dict,
        host: Optional[str] = None,
        max_scrape: int = MAX_SCRAPE,
        action: ACTIONS = ACTIONS.REQUEST_ID,
    ):
        self.ip: str = ip
        self.port: int = port
        self.host: Optional[str] = host
        self.connection_id: Optional[int] = None
        self._torrents: dict = torrents
        self._unscraped_hashes: list = list(torrents.keys())
        self.max_scrape: int = max_scrape
        self.action: Optional[ACTIONS] = action
        self.lock = UDPReadWriteLock()

    @staticmethod
    def udp_create_connection_msg(transaction_id: int) -> bytes:
        return struct.pack("!qII", MAGIC_VALUE, ACTIONS.REQUEST_ID, transaction_id)

    def udp_create_announce_msg(self, transaction_id: int) -> bytes:
        return struct.pack("!qII", self.connection_id, ACTIONS.REQUEST_ANNOUNCE, transaction_id)

    async def udp_create_scrape_msg(self, transaction_id: int) -> tuple[bytes, list[str]]:
        # so we can only do around 74 at a time here: see https://www.bittorrent.org/beps/bep_0015.html
        # that's not particularly specific, so let's use an internal value and keep track
        # of who we scraped.
        hashes = []
        async with await self.lock.read:
            if len(self._unscraped_hashes) <= self.max_scrape:
                hashes = self._unscraped_hashes
                logger.info(
                    f"Scraping all {len(self._unscraped_hashes)} hashes for tracker {self.host}"
                )
            else:
                # otherwise, copy into a new list...
                logger.info(
                    f"""
                    Unable to scrape all hashes for tracker {self.host}:
                        Hashes remaining: {len(self._unscraped_hashes) - self.max_scrape}"
                """
                )
                hashes = self._unscraped_hashes[: self.max_scrape - 1].copy()
                # ... then reslice the existing list.
                self._unscraped_hashes = self._unscraped_hashes[self.max_scrape :]
        # now!  Pack it up into bytes.
        msg = struct.pack("!qII", self.connection_id, ACTIONS.REQUEST_SCRAPE, transaction_id)
        for hash in hashes:
            msg += binascii.a2b_hex(hash)
        return msg, hashes

    async def tracker_send_and_receive(
        self, protocol: UDPProtocolHandler, timeout: int = 5
    ) -> tuple[asyncio.DatagramTransport, UDPProtocolHandler]:
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: protocol, remote_addr=(self.ip, self.port)
        )
        try:
            await asyncio.wait_for(protocol.success, timeout=timeout)
        except Exception as e:
            logger.exception("Exception communicating with tracker: %s", e)
        finally:  # cleanup, basically.
            if transport.is_closing():
                transport.abort()
            else:
                try:
                    transport.close()
                except Exception as e:
                    logger.exception("Exception closing transport: %s", e)
        return transport, protocol

    async def initiate_connection(self) -> None:

        db, id = await counter.next()
        msg = self.udp_create_connection_msg(id)

        logger.debug(
            f"Sending action: {ACTIONS.REQUEST_ID} w/ ID of {db}:{id} "
            f"to IP:PORT {self.ip}:{self.port}"
        )

        future = loop.create_future()
        protocol = UDPProtocolHandler(msg, id, future)
        transport, protocol = await self.tracker_send_and_receive(protocol)

        assert protocol.result is not None  # oh my goddddd pyright more like pywrong
        # initializing connection
        # TODO: Error handling!
        resp_action, resp_id, connection_id = struct.unpack_from("!IIq", protocol.result[0])
        assert resp_action == ACTIONS.REQUEST_ID
        assert resp_id == id
        logger.debug(
            f"""RESPONSE from {self.ip}:{self.port}:
                Action:         {resp_action}
                Transaction ID: {resp_id}
                Connection ID:  {connection_id}
                Tracker URL:    {self.host}
                """
        )
        self.connection_id = connection_id

    async def announce_to_tracker(self) -> None:
        if not self.connection_id:
            raise UDPTrackerException(
                "Connection ID is not set; initiate connection to tracker first!"
            )
        else:
            raise NotImplementedError(
                "We don't use this class to announce ourselves as clients who wish to download."
            )

    async def request_scrape(self) -> None:
        if not self.connection_id:
            raise UDPTrackerException(
                "Connection ID is not set; initiate connection to tracker first!"
            )
        db, id = await counter.next()
        msg, hashes = await self.udp_create_scrape_msg(id)

        logger.debug(
            msg=f"Sending action: {ACTIONS.REQUEST_SCRAPE} w/ ID of {db}:{id} "
            f"to IP:PORT {self.ip}:{self.port}"
        )

        future = loop.create_future()
        protocol = UDPProtocolHandler(msg, id, future)
        transport, protocol = await self.tracker_send_and_receive(protocol)

        assert protocol.result is not None
        # TODO: Error handling!
        resp_action, resp_id = struct.unpack_from("!II", protocol.result[0])
        assert resp_action == ACTIONS.REQUEST_SCRAPE
        assert resp_id == id

        offset = 8
        length_per_hash = 12
        results = {}

        for hash in hashes:
            if offset + length_per_hash > len(protocol.result[0]):
                logger.debug("Response not enough long enough")
                # should probably try and get this hash again
            seeds, completed, peers = struct.unpack_from("!iii", protocol.result[0], offset)
            results[hash] = {
                "seeds": seeds,
                "completed": completed,
                "peers": peers,  # they're not leeches, they're your siblings
            }

            offset += length_per_hash

        logger.debug(f"RESULTS FROM SCRAPE: {resp_action} {resp_id} {results}")


async def resolve_host(url: str) -> tuple[str, int]:
    parsed = urlparse(url)
    hostname = parsed.hostname
    port = parsed.port

    errors = []

    if hostname is None:
        errors.append("hostname unable to be parsed;")
    if port is None:
        errors.append("port unable to be parsed;")
    if parsed.scheme.lower() != "udp":
        errors.append("protocol is not udp;")
    if len(errors) != 0:
        raise TrackerURLException(f"Unable to parse given url of {url}: " + " ".join(errors))
    try:
        result = await resolver.query(hostname, "A")
        ip = result[0].host
        return ip, port
    except:
        raise


async def create_udp_tracker_client(url: str, torrents: dict) -> UDPTrackerClient:
    ip, port = await resolve_host(url)
    return UDPTrackerClient(ip, port, torrents, host=url)
