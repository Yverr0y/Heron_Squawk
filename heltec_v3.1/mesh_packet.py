"""
Heron Squawk Mesh Packet Format (MicroPython)

Packet header (9 bytes, big-endian):
    [src: 2 bytes] [dst: 2 bytes] [pkt_id: 2 bytes] [ttl: 1 byte] [msg_type: 1 byte] [channel: 1 byte]

This sits INSIDE the RYLR frame payload.
"""

import struct

# Message types
MSG_TEXT = 0x01
MSG_GPS = 0x02
MSG_ACK = 0x03
MSG_RREQ = 0x10
MSG_RREP = 0x11
MSG_PING = 0x20
MSG_DISCOVER = 0x21
MSG_ANNOUNCE = 0x22
MSG_CHANNEL_ANNOUNCE = 0x23

BROADCAST = 0
DM_CHANNEL = 0

HEADER_FORMAT = '>HHHBBB'
HEADER_SIZE = 9


class Packet:
    """Mesh network packet."""

    def __init__(self, src=0, dst=0, pkt_id=0, ttl=5, msg_type=MSG_TEXT, channel=0, payload=b''):
        self.src = src
        self.dst = dst
        self.pkt_id = pkt_id
        self.ttl = ttl
        self.msg_type = msg_type
        self.channel = channel
        self.payload = payload if isinstance(payload, bytes) else payload.encode()

    def pack(self):
        """Pack into bytes."""
        header = struct.pack(
            HEADER_FORMAT,
            self.src,
            self.dst,
            self.pkt_id,
            self.ttl,
            self.msg_type,
            self.channel
        )
        return header + self.payload

    def to_hex(self):
        """Pack and return as hex string."""
        return self.pack().hex().upper()

    @classmethod
    def unpack(cls, data):
        """Unpack from bytes."""
        if isinstance(data, str):
            data = bytes.fromhex(data)

        if len(data) < HEADER_SIZE:
            raise ValueError(f"Data too short: {len(data)} bytes")

        src, dst, pkt_id, ttl, msg_type, channel = struct.unpack(
            HEADER_FORMAT,
            data[:HEADER_SIZE]
        )

        payload = data[HEADER_SIZE:]

        return cls(
            src=src,
            dst=dst,
            pkt_id=pkt_id,
            ttl=ttl,
            msg_type=msg_type,
            channel=channel,
            payload=payload
        )

    def __repr__(self):
        type_names = {
            MSG_TEXT: 'TEXT',
            MSG_GPS: 'GPS',
            MSG_ACK: 'ACK',
            MSG_RREQ: 'RREQ',
            MSG_RREP: 'RREP',
            MSG_PING: 'PING',
            MSG_DISCOVER: 'DISCOVER',
            MSG_ANNOUNCE: 'ANNOUNCE',
            MSG_CHANNEL_ANNOUNCE: 'CH_ANN'
        }
        type_name = type_names.get(self.msg_type, f'0x{self.msg_type:02X}')
        dst_str = 'BCAST' if self.dst == BROADCAST else str(self.dst)
        ch_str = 'DM' if self.channel == 0 else f'CH{self.channel}'

        try:
            payload_str = self.payload.decode()[:20]
        except:
            payload_str = self.payload.hex()[:20]

        return f"Pkt({self.src}->{dst_str} {type_name} {ch_str} '{payload_str}')"


class PacketFactory:
    """Factory for creating mesh packets."""

    def __init__(self, my_address, default_ttl=5):
        self.my_address = my_address
        self.default_ttl = default_ttl
        self._pkt_counter = 0

    def _next_id(self):
        self._pkt_counter = (self._pkt_counter + 1) % 65536
        return self._pkt_counter

    def create_text(self, dst, message, channel=0):
        """Create text message packet."""
        return Packet(
            src=self.my_address,
            dst=dst,
            pkt_id=self._next_id(),
            ttl=self.default_ttl,
            msg_type=MSG_TEXT,
            channel=channel,
            payload=message
        )

    def create_channel_message(self, channel, message):
        """Create channel broadcast message."""
        return Packet(
            src=self.my_address,
            dst=BROADCAST,
            pkt_id=self._next_id(),
            ttl=self.default_ttl,
            msg_type=MSG_TEXT,
            channel=channel,
            payload=message
        )

    def create_dm(self, dst, message):
        """Create direct message (channel 0)."""
        return Packet(
            src=self.my_address,
            dst=dst,
            pkt_id=self._next_id(),
            ttl=self.default_ttl,
            msg_type=MSG_TEXT,
            channel=DM_CHANNEL,
            payload=message
        )

    def create_ping(self, dst=BROADCAST):
        """Create ping packet."""
        return Packet(
            src=self.my_address,
            dst=dst,
            pkt_id=self._next_id(),
            ttl=self.default_ttl,
            msg_type=MSG_PING,
            channel=0,
            payload=b''
        )

    def create_discover(self):
        """Create discover packet."""
        return Packet(
            src=self.my_address,
            dst=BROADCAST,
            pkt_id=self._next_id(),
            ttl=self.default_ttl,
            msg_type=MSG_DISCOVER,
            channel=0,
            payload=b''
        )

    def create_announce(self, node_name):
        """Create announce packet."""
        return Packet(
            src=self.my_address,
            dst=BROADCAST,
            pkt_id=self._next_id(),
            ttl=self.default_ttl,
            msg_type=MSG_ANNOUNCE,
            channel=0,
            payload=node_name
        )
