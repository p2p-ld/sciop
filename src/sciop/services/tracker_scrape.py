import asyncio
import binascii
import enum
import struct
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from logging import Logger
from types import TracebackType
from typing import Any, Optional
from urllib.parse import urlparse

import aiodns
import sqlalchemy as sqla
from sqlmodel import select, update

from sciop.config import config
from sciop.exceptions import (
    DNSException,
    ScrapeErrorType,
    ScrapeUnpackException,
    TrackerConnectionException,
    TrackerURLException,
    UDPTrackerException,
)
from sciop.logging import init_logger
from sciop.models import TorrentFile, TorrentTrackerLink, Tracker

MAGIC_VALUE = 0x41727101980
MAX_SCRAPE = 70


@dataclass
class ScrapeResponse:
    infohash: str
    announce_url: str
    seeders: int
    completed: int
    leechers: int


@dataclass
class ScrapeError:
    msg: str
    type: ScrapeErrorType
    announce_url: Optional[str] = None
    infohash: Optional[str] = None


@dataclass
class PivotedResponses:
    """Long-wise responses, with one list per type of result, for batch updates"""

    infohash: list[str]
    announce_url: list[str]
    seeders: list[int]
    completed: list[int]
    leechers: list[int]


@dataclass
class ScrapeResult:
    """Mappings from infohashes to outcomes"""

    errors: list[ScrapeError] = field(default_factory=list)
    responses: dict[str, ScrapeResponse] = field(default_factory=dict)

    def __add__(self, other: "ScrapeResult") -> "ScrapeResult":
        if not isinstance(other, ScrapeResult):
            raise TypeError("Can only add scrape results together!")
        return ScrapeResult(
            errors=[*self.errors, *other.errors],
            responses={**self.responses, **other.responses},
        )

    def __len__(self) -> int:
        return len(self.errors) + len(self.responses)

    def pivot(self) -> PivotedResponses:
        pivoted = defaultdict(list)
        for res in self.responses.values():
            for key, val in asdict(res):
                pivoted[key].append(val)
        return PivotedResponses(**pivoted)

    @classmethod
    def merge(cls, items: list["ScrapeResult"]) -> "ScrapeResult":
        """
        FIXME: Needs to store items as a list not a dict to avoid clobbering matching entries
        """
        item = items[0]
        for anitem in items[1:]:
            item += anitem
        return item


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

        self.logger = init_logger("tracker.udp.protocol")

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport
        self.transport.sendto(self.message)

    def datagram_received(self, data: bytes, addr: tuple[str | Any, int]) -> None:
        self.result = (data, addr)
        self.success.set_result(True)

    def error_received(self, exc: OSError) -> None:
        self.logger.debug(f"UDP Error: {str(exc)}")
        self.success.set_result(False)

    def connection_lost(self, exc: OSError) -> None:
        if exc:
            self.success.set_result(True)


class UDPTrackerClient:
    def __init__(
        self,
        ip: str,
        port: int,
        host: str,
        max_scrape: int = MAX_SCRAPE,
        action: ACTIONS = ACTIONS.REQUEST_ID,
        timeout: int = 30,
    ):
        self.ip: str = ip
        self.port: int = port
        self.host: str = host
        self.max_scrape: int = max_scrape
        self.action: Optional[ACTIONS] = action
        self.lock = UDPReadWriteLock()
        self.loop = asyncio.get_event_loop()
        self.timeout = timeout
        self.logger = init_logger("tracker.udp.client")

        self._transaction_id: Optional[int] = None
        self._connection_id: Optional[int] = None
        self._connection_id_created: Optional[datetime] = None

    @classmethod
    async def from_url(cls, url: str, **kwargs: Any) -> "UDPTrackerClient":
        ip, port = await resolve_host(url)
        return UDPTrackerClient(ip, port, host=url, **kwargs)

    @property
    async def connection_id(self) -> Optional[int]:
        if self._connection_id is None or (
            self._connection_id_created
            and self._connection_id_created < (datetime.now() - timedelta(minutes=1))
        ):
            try:
                db, self._transaction_id = await counter.next()
                self._connection_id = await self._initiate_connection(self._transaction_id)
                self._connection_id_created = datetime.now()
            except UDPTrackerException as e:
                raise TrackerConnectionException("Could not initiate connection to tracker") from e
        return self._connection_id

    @staticmethod
    def udp_create_connection_msg(transaction_id: int) -> bytes:
        return struct.pack("!qII", MAGIC_VALUE, ACTIONS.REQUEST_ID, transaction_id)

    async def udp_create_announce_msg(self, transaction_id: int) -> bytes:
        return struct.pack(
            "!qII", await self.connection_id, ACTIONS.REQUEST_ANNOUNCE, transaction_id
        )

    async def udp_create_scrape_msg(self, infohashes: list[str]) -> tuple[bytes, list[str]]:
        # so we can only do around 74 at a time here: see https://www.bittorrent.org/beps/bep_0015.html
        # that's not particularly specific, so let's use an internal value and keep track
        # of who we scraped.
        async with await self.lock.read:
            if len(infohashes) > self.max_scrape:
                raise ValueError(
                    f"Can only scrape {self.max_scrape} infohashes in a single request"
                )

        # now!  Pack it up into bytes.
        msg = struct.pack(
            "!qII", await self.connection_id, ACTIONS.REQUEST_SCRAPE, self._transaction_id
        )
        for hash in infohashes:
            # trackers expect 20-byte truncated hashes
            msg += binascii.a2b_hex(hash)[0:20]
        return msg, infohashes

    async def tracker_send_and_receive(
        self, protocol: UDPProtocolHandler, timeout: Optional[int] = None
    ) -> tuple[asyncio.DatagramTransport, UDPProtocolHandler]:
        if timeout is None:
            timeout = self.timeout

        transport, protocol = await self.loop.create_datagram_endpoint(
            lambda: protocol, remote_addr=(self.ip, self.port)
        )
        try:
            await asyncio.wait_for(protocol.success, timeout=timeout)
        except TimeoutError as e:
            self.logger.debug("Timeout exception communicating with tracker: %s", e)
            raise e
        finally:  # cleanup, basically.
            if transport.is_closing():
                transport.abort()
            else:
                try:
                    transport.close()
                except Exception as e:
                    self.logger.debug("Exception closing transport: %s", e)
                    raise UDPTrackerException("Exception closing transport") from e
        return transport, protocol

    async def _initiate_connection(self, tid: int) -> bytes:

        msg = self.udp_create_connection_msg(tid)

        self.logger.debug(
            f"Sending action: {ACTIONS.REQUEST_ID} w/ ID of {tid} "
            f"to IP:PORT {self.ip}:{self.port}"
        )

        future = self.loop.create_future()
        protocol = UDPProtocolHandler(msg, tid, future)
        transport, protocol = await self.tracker_send_and_receive(
            protocol, timeout=config.tracker_scraping.connection_timeout
        )

        if protocol.result is None:
            raise TrackerConnectionException("UDP protocol result was None")

        resp_action, resp_id, connection_id = struct.unpack_from("!IIq", protocol.result[0])
        if resp_action != ACTIONS.REQUEST_ID or resp_id != tid:
            raise TrackerConnectionException(
                "Response action and id must match in request and response.\n"
                f"response_action: {resp_action}\n"
                f"request_action: {ACTIONS.REQUEST_ID}\n"
                f"response_id: {resp_id}\n",
                f"request_id: {tid}",
            )
        self.logger.debug(
            f"""RESPONSE from {self.ip}:{self.port}:
                Action:         {resp_action}
                Transaction ID: {resp_id}
                Connection ID:  {connection_id}
                Tracker URL:    {self.host}
                """
        )
        return connection_id

    async def announce_to_tracker(self) -> None:
        raise NotImplementedError(
            "We don't use this class to announce ourselves as clients who wish to download."
        )

    async def scrape(self, infohashes: list[str]) -> ScrapeResult:
        """
        Scrape a set of infohashes from the configured tracker.

        If more than 70 infohashes are passed, will be batched across multiple requests
        """

        self.logger.debug(
            msg=f"Sending action: {ACTIONS.REQUEST_SCRAPE} w/ ID of {self._transaction_id} "
            f"to IP:PORT {self.ip}:{self.port}"
        )
        results = ScrapeResult()
        for i in range(0, len(infohashes), self.max_scrape):
            results += await self._scrape_page(infohashes[i : i + self.max_scrape])

        return results

    async def _scrape_page(self, infohashes: list[str]) -> ScrapeResult:
        """Scrape a single page of 70 infohashes"""

        try:
            msg, hashes = await self.udp_create_scrape_msg(infohashes)
            future = self.loop.create_future()
            protocol = UDPProtocolHandler(msg, self._transaction_id, future)
            transport, protocol = await self.tracker_send_and_receive(protocol)

            if protocol.result is None:
                raise TrackerConnectionException("UDP protocol result was none when scraping")

            try:
                data = protocol.result[0]
                resp_action, resp_id = struct.unpack_from("!II", data)
                assert resp_action == ACTIONS.REQUEST_SCRAPE
                assert resp_id == self._transaction_id
                return self._unpack_scrape_result(data, infohashes)
            except Exception as e:
                raise ScrapeUnpackException(f"Error unpacking scrape result: {msg(e)}") from e

        except TrackerConnectionException as e:
            return ScrapeResult(
                errors=[ScrapeError(type="connection", announce_url=self.host, msg=str(e))]
            )
        except ScrapeUnpackException as e:
            return ScrapeResult(
                errors=[ScrapeError(type="unpack", announce_url=self.host, msg=str(e))]
            )
        except TimeoutError as e:
            return ScrapeResult(
                errors=[ScrapeError(type="timeout", announce_url=self.host, msg=str(e))]
            )
        except Exception as e:
            return ScrapeResult(
                errors=[ScrapeError(type="default", announce_url=self.host, msg=str(e))]
            )

    def _unpack_scrape_result(self, data: bytes, infohashes: list[str]) -> ScrapeResult:
        """
        Args:
            data: tracker response with header bits stripped off, a set of 3 32-bit integers
            infohashes: list of infohashes that corresponds to the scrape result
        """
        offset = 8
        length_per_hash = 12
        responses = {}
        errors = []

        for hash in infohashes:
            if offset + length_per_hash > len(data):
                msg = f"Response not enough long enough to get scrape result from {hash}"
                errors.append(ScrapeError(type="unpack", infohash=hash, msg=msg))
                self.logger.debug(msg)
                continue

            seeds, completed, peers = struct.unpack_from("!III", data, offset)
            responses[hash] = ScrapeResponse(
                infohash=hash,
                announce_url=self.host,
                seeders=int(seeds),
                completed=int(completed),
                leechers=int(peers),  # they're not leeches, they're your siblings
                # tru but we should still call them leechers bc that's what the spec does lol
            )

            offset += length_per_hash

        results = ScrapeResult(responses=responses, errors=errors)
        return results


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
    if parsed.hostname == "localhost":
        return "127.0.0.1", port

    try:
        resolver = aiodns.DNSResolver()
        result = await resolver.query(hostname, "A")
        ip = result[0].host
        return ip, port
    except Exception as e:
        logger = init_logger("udp")
        msg = f"Error resolving host: {str(e)}"
        logger.debug(msg)
        raise DNSException(msg) from e


async def scrape_torrent_stats() -> None:
    """
    Main job for periodic scraping torrent stats.

    - Gathers torrents due for updating according to the update interval in config,
      plus any exponential backoff from unresponsive trackers
    - Dispatches jobs per tracker with lists of infohashes to scrape
    - scrapes in batches
    - updates db
    """
    logger = init_logger("jobs.scrape_stats")
    to_scrape = gather_scrapable_torrents()
    sem = asyncio.Semaphore(value=config.tracker_scraping.n_workers)
    logger.debug("Scraping torrent stats for: %s", to_scrape)
    results = await asyncio.gather(
        *[
            scrape_tracker(url=tracker, infohashes=infohashes, semaphore=sem)
            for tracker, infohashes in to_scrape.items()
        ]
    )
    total = sum([len(r.responses) for r in results])
    errors = sum([len(r.errors) for r in results])
    logger.info(
        "Scraped %s trackers to update %s torrent/tracker pairs. %s errors",
        len(results),
        total,
        errors,
    )
    logger.debug("Scrape results: %s", results)


def gather_scrapable_torrents() -> dict[str, list[str]]:
    """
    Gather scrapable torrents as a {"announce_url": ["infohash", ...]} dict.
    """
    from sciop.db import get_session

    last_scrape_time = datetime.now(UTC) - timedelta(minutes=config.tracker_scraping.interval)
    statement = (
        select(TorrentFile.infohash, Tracker.announce_url)
        .join(TorrentFile.tracker_links)
        .join(TorrentTrackerLink.tracker)
        .filter(
            Tracker.protocol == "udp",
            sqla.and_(
                sqla.or_(
                    TorrentTrackerLink.last_scraped_at == None,  # noqa: E711
                    TorrentTrackerLink.last_scraped_at <= last_scrape_time,
                ),
                sqla.or_(
                    Tracker.next_scrape_after == None,  # noqa: E711
                    Tracker.next_scrape_after < datetime.now(UTC),
                ),
            ),
        )
    )
    with next(get_session()) as session:
        results = session.exec(statement).all()

    # group by tracker
    gathered = defaultdict(list)
    for res in results:
        gathered[res.announce_url].append(res.infohash)
    return gathered


async def scrape_tracker(
    url: str, infohashes: list[str], semaphore: asyncio.Semaphore
) -> ScrapeResult:
    logger = init_logger("jobs.scrape_stats.scrape_tracker")
    logger.debug("scraping tracker %s with %s", url, infohashes)
    async with semaphore:
        try:
            client = await UDPTrackerClient.from_url(
                url, timeout=config.tracker_scraping.scrape_timeout
            )
            results = await client.scrape(infohashes)
        except DNSException as e:
            results = ScrapeResult(errors=[ScrapeError(type="dns", announce_url=url, msg=str(e))])
        except Exception as e:
            msg = str(e)
            logger.debug(msg)
            results = ScrapeResult(errors=[ScrapeError(type="default", announce_url=url, msg=msg)])

    _update_scrape_results(results, logger=logger)
    _handle_tracker_error(results, logger=logger)
    _touch_tracker(url, results)
    return results


def _update_scrape_results(results: ScrapeResult, logger: Logger) -> None:
    from sciop.db import get_session

    if len(results.responses) == 0:
        return

    # FIXME: assuming we are storing a collection from a single tracker,
    # which are are most of the time
    # revisit using `sqla.tuple_(col1, col2).in([(val1, val2) for ...])
    announce_url = set([r.announce_url for r in results.responses.values()])
    if len(announce_url) > 1:
        raise ValueError("Can only store one tracker's worth of results at a time")
    if len(announce_url) == 0:
        logger.warning("no announce url found in responses")
        return
    announce_url = list(announce_url)[0]

    update_select_stmt = (
        select(TorrentTrackerLink.torrent_file_id, TorrentTrackerLink.tracker_id)
        .join(TorrentFile.tracker_links)
        .join(TorrentTrackerLink.tracker)
        .where(
            Tracker.announce_url == announce_url,
            TorrentFile.infohash.in_([res.infohash for res in results.responses.values()]),
        )
    )
    with next(get_session()) as session:
        scrape_time = datetime.now(UTC)
        link_ids = session.exec(update_select_stmt).all()
        session.exec(
            update(TorrentTrackerLink),
            params=[
                {
                    "torrent_file_id": tllid.torrent_file_id,
                    "tracker_id": tllid.tracker_id,
                    "seeders": res.seeders,
                    "leechers": res.leechers,
                    "completed": res.completed,
                    "last_scraped_at": scrape_time,
                }
                for tllid, res in zip(link_ids, results.responses.values())
            ],
        )
        session.commit()


def _handle_tracker_error(results: ScrapeResult, logger: Logger) -> None:
    from sciop.db import get_session

    tracker_errors = [e for e in results.errors if e.announce_url and e.infohash is None]
    if not tracker_errors:
        return
    with next(get_session()) as session:
        for e in tracker_errors:
            tracker = session.exec(
                select(Tracker).where(Tracker.announce_url == e.announce_url)
            ).first()
            if e.type != tracker.error_type:
                tracker.n_errors = 0
            tracker.n_errors += 1
            next_scrape = datetime.now(UTC) + timedelta(
                minutes=_compute_backoff(tracker.n_errors, e.type)
            )
            tracker.next_scrape_after = next_scrape
            tracker.error_type = e.type
            session.add(tracker)
            logger.debug(
                "Backing off tracker %s - %s errors - next scrape at %s",
                e.announce_url,
                tracker.n_errors,
                next_scrape,
            )
        session.commit()


def _compute_backoff(
    n_errors: int = 1, error_type: ScrapeErrorType = ScrapeErrorType.default
) -> float:
    if isinstance(error_type, ScrapeErrorType):
        error_type = error_type.value
    multipliers = config.tracker_scraping.backoff.model_dump()

    multiplier = multipliers.get(error_type, multipliers.get("default", 1))
    backoff = config.tracker_scraping.interval * multiplier * (2**n_errors)
    return min(backoff, config.tracker_scraping.max_backoff)


def _touch_tracker(url: str, results: ScrapeResult) -> None:
    from sciop.db import get_session

    errors = [e for e in results.errors]
    any_errors = any([e.announce_url == url for e in errors])

    params = {"last_scraped_at": datetime.now(UTC)}
    if not any_errors:
        params.update({"n_errors": 0, "error_type": None, "next_scrape_after": None})

    with next(get_session()) as session:
        session.exec(update(Tracker).where(Tracker.announce_url == url), params=params)
        session.commit()
