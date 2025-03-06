import asyncio
import struct
import aiodns
import enum
from urllib.parse import urlparse

from typing import Callable, Optional, Any
from sciop.logging import init_logger
from sciop.exceptions import SciOpException

loop = asyncio.get_event_loop()
logger = init_logger('udp.tracker')

resolver = aiodns.DNSResolver()
MAGIC_VALUE = 0x41727101980

# https://www.bittorrent.org/beps/bep_0015.html
class ACTIONS(enum.IntEnum):
    REQUEST_ID = 0
    REQUEST_ANNOUNCE = 1
    REQUEST_SCRAPE = 2
    ERROR = 4 # oh uh

class TrackerURLException(SciOpException):
    """Exception when something went wrong with the URL given"""

class UDPTrackerException(SciOpException):
    """Exception when an error has been encountered with the UDPTrackerClient"""

class UDPReadLock(asyncio.Queue):
    async def __aenter__(self):
        self.put_nowait(None)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self.get_nowait()
        self.task_done()
        return None

class UDPReadWriteLock:
    """A slightly tested read/write lock for our dictionary of torrent hashes"""
    def __init__(self):
        self._lock = asyncio.Lock()
        self._read = UDPReadLock()

    @property
    async def read(self):
        # first try and get the lock; if we're waiting on a write, it'll be locked already
        async with self._lock:
            pass # we do not want to hold the lock while reading
        return self._read

    async def __aenter__(self):
        await self._lock.acquire() # get the lock, no matter what
        if not self._read.empty():
            await self._read.join() # wait for the queue to to empty if things are reading.

    async def __aexit__(self, exc_type, exc, tb):
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
            if self._tracker_trans_id > 4294967295: # 32 bit int, I think
                self._tracker_trans_id = 0
                self._db_prefix += 1
            else:
                self._tracker_trans_id += 1
            id = self._tracker_trans_id
            db = self._db_prefix
        return db, id

    async def current(self):
        async with self.lock:
            id = self._tracker_trans_id
            db = self._db_prefix
        return db, id

counter = SciOpUDPCounter()

class UDPProtocolHandler(asyncio.DatagramProtocol):
    def __init__(self, message: bytes, transaction_id: int, active: asyncio.Future):
        self.message: bytes = message
        self.id: int = transaction_id
        self.success: asyncio.Future = active
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.result: Optional[tuple[bytes, tuple[str | Any, int]]] = None # this might be _too_ strong of typing.

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        self.transport.sendto(self.message)

    def datagram_received(self, data: bytes, addr: tuple[str | Any, int]):
        self.result = (data, addr)
        self.success.set_result(True)

    def error_received(self, exc):
        self.success.set_result(False)

    def connection_lost(self, exc):
        if exc:
            self.success.set_result(True)

class UDPTrackerClient:
    def __init__(self, url: Optional[str] = None, ip: Optional[str] = None, port: Optional[int] = None, torrents: dict = {}, action: ACTIONS = ACTIONS.REQUEST_ID):
        if url is None and ip is None:
            raise UDPTrackerException("Either url or ip must be set.")
        if url is not None:
            _ip, _port = asyncio.run(resolve_host(url)) # we don't want to use async in an init
            if ip is None: # if an IP is set, we don't want to override it
                ip = _ip
            if port is None: # Same with the port
                port = _port
        assert(ip is not None)
        assert(port is not None) # oh my gawwwd pyright stop kvetching, this is pointless
        self.url: Optional[str] = url
        self.ip: str = ip
        self.port: int = port
        self.connection_id: Optional[int] = None
        self._torrents: dict = torrents
        self.action: Optional[ACTIONS] = action
        self.lock = UDPReadWriteLock()

    async def gen_torrents(self):
        async with await self.lock.read:
            for torrent in self._torrents:
                yield torrent

    async def set_torrents(self, torrents: dict):
        async with self.lock:
            self._torrents = torrents
    
    @staticmethod
    def udp_create_connection_msg(transaction_id: int) -> bytes:
        return struct.pack("!qII", MAGIC_VALUE, ACTIONS.REQUEST_ID, transaction_id)

    def udp_create_announce_msg(self, transaction_id: int) -> bytes:
        return struct.pack("!qII", self.connection_id, ACTIONS.REQUEST_ANNOUNCE, transaction_id)

    # def datagram_received(self, data, addr):
    #     self.data = data
    #     action, resp_trans_id, conn_id = struct.unpack_from("!IIq", data)
    #     assert(self.action == action)
    #     if action == ACTIONS.REQUEST_ID:
    #         # initializing connection
    #         self.connection_id = conn_id
    #         logger.debug(f"""RESPONSE from {self.host}:
    #                 Action:         {0}
    #                 Transaction ID: {resp_trans_id}
    #                 Connection ID:  {conn_id}""")
    #     self.on_end.set_result(True)
    #     # asyncio.create_task(self.response_handler(data))

    async def tracker_send_and_receive(self, protocol: UDPProtocolHandler, timeout: int = 5) -> tuple[asyncio.DatagramTransport, UDPProtocolHandler]:
        transport, protocol = await loop.create_datagram_endpoint(lambda: protocol, remote_addr=(self.ip, self.port))
        try:
            await asyncio.wait_for(protocol.success, timeout=timeout)
        except:
            pass
        finally: # cleanup, basically.
            if transport.is_closing():
                transport.abort()
            else:
                try:
                    transport.close()
                except:
                    pass
        return transport, protocol

    async def initiate_connection(self):

        db, id = await counter.next()
        msg = self.udp_create_connection_msg(id)
        
        logger.debug(f"Sending action: {0} w/ ID of {db}:{id} to IP: {self.ip} on port 451")

        future = loop.create_future()
        protocol = UDPProtocolHandler(msg, id, future)
        transport, protocol = await self.tracker_send_and_receive(protocol)

        assert(protocol.result is not None) # oh my goddddd pyright more like pywrong
        result = struct.unpack_from("!IIq", protocol.result[0])
        connection_id = result[2]
        logger.debug(f"STORED CONNECTION ID: {connection_id}")
        self.connection_id = connection_id

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
        result = await resolver.query(hostname, 'A')
        ip = result[0].host
        return ip, port
    except:
        raise


