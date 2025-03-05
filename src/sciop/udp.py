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

class UDPTrackerClient(asyncio.DatagramProtocol):
    def __init__(self, message: bytes, host: str, transaction_id: int, on_end: asyncio.Future, action: ACTIONS = ACTIONS.REQUEST_ID, connection_id: int | None = None):
        self.message: bytes = message
        self.host = host
        self.on_end: asyncio.Future = on_end
        self.transport = None
        self.connection_id: int | None = connection_id
        self._torrent_hashes: dict = {}
        self._action: ACTIONS = action
        self.failed = False

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
        self.failed = False
        self.on_end = on_end

    async def reset(self):
        loop = asyncio.get_event_loop()
        self.reset_future(loop.create_future())
        # self.message = msg
        # self.transaction_id = id
        # self.action = action
        pass

    def connection_made(self, transport):
        self.transport = transport
        self.transport.sendto(self.message)

    def datagram_received(self, data, addr):
        self.data = data
        action, resp_trans_id, conn_id = struct.unpack_from("!IIq", data)
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
        self.failed = True
        # self.error_handler(exc)

    def connection_lost(self, exc):
        if exc:
            self.on_end.set_result(True)
            self.failed = True
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

async def tracker_send_and_receive(protocol: UDPTrackerClient, timeout: int = 5):
    loop = asyncio.get_event_loop()
    transport, protocol = await loop.create_datagram_endpoint(lambda: protocol, remote_addr=(protocol.host, 451))
    try:
        await asyncio.wait_for(protocol.on_end, timeout=timeout)
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
    return protocol

async def initiate_connection(hostname: str):
    loop = asyncio.get_event_loop()
    db, id = await counter.next()
    msg = udp_create_connection_msg(id)

    ip = await resolve_host('tracker.torrent.eu.org')
    on_end = loop.create_future()
    
    logger.debug(f"Sending action: {0} w/ ID of {db}:{id} to IP: {ip} on port 451")
    protocol = UDPTrackerClient(msg, ip, id, on_end)
    protocol = await tracker_send_and_receive(protocol)

    logger.debug(f"STORED CONNECTION ID: {protocol.connection_id}")

    # reset the future, set a new action and message
    on_end = loop.create_future()
    protocol.reset_future(on_end)
    db, id = await counter.next()
    msg = udp_create_connection_msg(id)
    protocol.message = msg
    # protocol.action = ACTIONS.REQUEST_ANNOUNCE
    # protocol.message = 
    # for now, just prove we can re-use it.
    protocol = await tracker_send_and_receive(protocol)
    # protocol = await 

    return protocol


