import asyncio
import struct
import aiodns

async def udp_test():
    loop = asyncio.get_event_loop()
    loop.create_datagram_endpoint

    magic = 0x41727101980
    action = 0
    trans_id = 1234
    msg = struct.pack("!qII", magic, action, trans_id)

    resolver = aiodns.DNSResolver()
    try:
        result = await resolver.query('tracker.torrent.eu.org', 'A')
        ip = result[0].host
    except:
        raise

    async def on_success(data):
        action, resp_trans_id, connection_id = struct.unpack_from("!IIq", data)
        print(f"RESPONSE: {action} w/ trans ID: {resp_trans_id} and conn ID: {connection_id}")
        print(action, resp_trans_id)
    
    transport, protocol = await loop.create_datagram_endpoint(lambda: UDP(msg, on_success, None), remote_addr=(ip, 451))

    print(f"Sending action: {action} w/ ID of {trans_id} to IP: {ip} on port 451")
    return transport, protocol



# taken directly from https://github.com/mhdzumair/PyAsyncTracker/blob/main/src/pyasynctracker/scraper.py
class UDP(asyncio.DatagramProtocol):
    def __init__(self, message, response_handler, error_handler):
        self.message = message
        self.response_handler = response_handler
        self.error_handler = error_handler
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport
        self.transport.sendto(self.message)

    def datagram_received(self, data, addr):
        asyncio.create_task(self.response_handler(data))

    def error_received(self, exc):
        self.error_handler(exc)

    def connection_lost(self, exc):
        if exc:
            self.error_handler(exc)

