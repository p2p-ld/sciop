import asyncio
import struct
import aiodns
from typing import Callable
from sciop.logging import init_logger
import enum

# buddy, they don't even let _me_ download the car

logger = init_logger('udp.tracker')

resolver = aiodns.DNSResolver()
MAGIC_VALUE = 0x41727101980

# https://www.bittorrent.org/beps/bep_0015.html
class ACTIONS(enum.IntEnum):
    REQUEST_ID = 0
    REQUEST_ANNOUNCE = 1
    REQUEST_SCRAPE = 2
    ERROR = 4 # oh uh

class SciOpUDPCounter():
    """
    Thread safe class for generating unique 32 bit transaction IDs.  A
    prefix may be used and generated for ensuring uniqueness.
    """
    def __init__(self, starting: int = 0, db_start: int = 0):
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

class UDPTrackerClient(asyncio.DatagramProtocol):
    def __init__(self, message: bytes, host: str, on_end: asyncio.Future, action: ACTIONS = ACTIONS.REQUEST_ID, connection_id: int | None = None):
        self.message: bytes = message
        self.host = host
        self.on_end: asyncio.Future = on_end
        self.transport = None
        self.connection_id: int | None = connection_id
        self._torrent_hashes: dict = {}
        self._action: ACTIONS = action

    @property
    def action(self):
        return self._action

    @action.setter
    def action(self, action: ACTIONS):
        self._action = action

    @property
    def torrents(self):
        return self._torrent_hashes

    @torrents.setter
    def torrents(self, torrent_hashes: dict):
        self._torrent_hashes = torrent_hashes

    def reset_future(self, on_end: asyncio.Future):
        self.on_end = on_end

    def connection_made(self, transport):
        self.transport = transport
        self.transport.sendto(self.message)

    def datagram_received(self, data, addr):
        self.data = data
        _action, resp_trans_id, conn_id = struct.unpack_from("!IIq", data)
        action = ACTIONS(_action)
        assert(self.action == action)
        if action == ACTIONS.REQUEST_ID:
            # initializing connection
            self.connection_id = conn_id
            logger.debug(f"""RESPONSE from {self.host}:
                    Action:         {0}
                    Transaction ID: {resp_trans_id}
                    Connection ID:  {conn_id}""")
        self.on_end.set_result(True)
        # asyncio.create_task(self.response_handler(data))

    def error_received(self, exc):
        self.on_end.set_result(True)
        # self.error_handler(exc)

    def connection_lost(self, exc):
        if exc:
            self.on_end.set_result(True)
            # self.error_handler(exc)


async def resolve_host(hostname: str) -> str:
    try:
        result = await resolver.query(hostname, 'A')
        ip = result[0].host
        return ip
    except:
        raise

def udp_create_connection_msg(transaction_id: int) -> bytes:
    return struct.pack("!qII", MAGIC_VALUE, ACTIONS.REQUEST_ID, transaction_id)

def udp_create_announce_msg(connection_id: int, transaction_id: int) -> bytes:
    return struct.pack("!qII", connection_id, ACTIONS.REQUEST_ANNOUNCE, transaction_id)

async def udp_send_and_receive(host: str, msg: bytes, timeout: int = 5):
    loop = asyncio.get_event_loop()
    on_end = loop.create_future()
    transport, protocol = await loop.create_datagram_endpoint(lambda: UDPTrackerClient(msg, host, on_end), remote_addr=(host, 451))
    try:
        await asyncio.wait_for(on_end, timeout=timeout)
    except:
        pass
    return protocol

async def tracker_send_and_receive(protocol: UDPTrackerClient, timeout: int = 5):
    loop = asyncio.get_event_loop()
    on_end = loop.create_future()
    transport, protocol = await loop.create_datagram_endpoint(lambda: protocol, remote_addr=(protocol.host, 451))
    try:
        await asyncio.wait_for(on_end, timeout=timeout)
    except:
        pass
    return protocol

async def initiate_connection(hostname: str):
    loop = asyncio.get_event_loop()
    db, id = await counter.next()
    msg = udp_create_connection_msg(id)

    ip = await resolve_host('tracker.torrent.eu.org')
    
    logger.debug(f"Sending action: {0} w/ ID of {db}:{id} to IP: {ip} on port 451")
    protocol = await udp_send_and_receive(ip, msg)

    logger.debug(f"STORED CONNECTION ID: {protocol.connection_id}")

    # reset the future, set a new action and message
    on_end = loop.create_future()
    protocol.reset_future(on_end)
    # protocol.action = ACTIONS.REQUEST_ANNOUNCE
    # protocol.message = 
    # for now, just prove we can re-use it.
    protocol = await tracker_send_and_receive(protocol)
    # protocol = await 

    return protocol


