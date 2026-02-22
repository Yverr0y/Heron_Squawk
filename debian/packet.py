import struct

MSG_TEXT = 0x01
MSG_GPS = 0x02
MSG_ACK = 0x03
MSG_RREQ = 0x10
MSG_RREP = 0x11
MSG_PING = 0x20
MSG_DISCOVER = 0x21
MSG_ANNOUNCE = 0x22
MSG_CHANNEL_ANNOUNCE = 0x23  # Channel announcement (name only, no passkey)

BROADCAST = 0  # RYLR999 uses address 0 for broadcast to all addresses (0-65535)
DM_CHANNEL = 0

HEADER_FORMAT = '>HHHBBB'
HEADER_SIZE = 9


class Packet:
    def __init__(self, src=0, dst=0, pkt_id=0, ttl=5, msg_type=MSG_TEXT, channel=0, payload=b''):
        self.src = src
        self.dst = dst
        self.pkt_id = pkt_id
        self.ttl = ttl
        self.msg_type = msg_type
        self.channel = channel
        self.payload = payload if isinstance(payload, bytes) else payload.encode()
    
    def pack(self):
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
        return self.pack().hex().upper()
    
    @classmethod
    def unpack(cls, data):
        if isinstance(data, str):
            data = bytes.fromhex(data)
        
        if len(data) < HEADER_SIZE:
            raise ValueError(f"Data too short: {len(data)} bytes, need {HEADER_SIZE}")
        
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
            MSG_ANNOUNCE: 'ANNOUNCE'
        }
        type_name = type_names.get(self.msg_type, f'0x{self.msg_type:02X}')
        dst_str = 'BROADCAST' if self.dst == BROADCAST else str(self.dst)
        ch_str = 'DM' if self.channel == 0 else f'CH{self.channel}'
        
        try:
            payload_str = self.payload.decode()
        except UnicodeDecodeError:
            payload_str = self.payload.hex()
        
        return (f"Packet(src={self.src}, dst={dst_str}, id={self.pkt_id}, "
                f"ttl={self.ttl}, type={type_name}, channel={ch_str}, payload='{payload_str}')")


class PacketFactory:
    def __init__(self, my_address, default_ttl=5):
        self.my_address = my_address
        self.default_ttl = default_ttl
        self._pkt_counter = 0
    
    def _next_id(self):
        self._pkt_counter = (self._pkt_counter + 1) % 65536
        return self._pkt_counter
    
    def create_text(self, dst, message, channel=0):
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
        return Packet(
            src=self.my_address,
            dst=dst,
            pkt_id=self._next_id(),
            ttl=self.default_ttl,
            msg_type=MSG_TEXT,
            channel=DM_CHANNEL,
            payload=message
        )
    
    def create_discover(self):
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
        return Packet(
            src=self.my_address,
            dst=BROADCAST,
            pkt_id=self._next_id(),
            ttl=self.default_ttl,
            msg_type=MSG_ANNOUNCE,
            channel=0,
            payload=node_name
        )
    
    def create_ack(self, dst, original_pkt_id):
        return Packet(
            src=self.my_address,
            dst=dst,
            pkt_id=self._next_id(),
            ttl=self.default_ttl,
            msg_type=MSG_ACK,
            channel=0,
            payload=struct.pack('>H', original_pkt_id)
        )
    
    def create_ping(self, dst=BROADCAST):
        return Packet(
            src=self.my_address,
            dst=dst,
            pkt_id=self._next_id(),
            ttl=self.default_ttl,
            msg_type=MSG_PING,
            channel=0,
            payload=b''
        )

    def create_channel_announce(self, channel_name):
        """
        Create channel announcement packet.
        Payload: channel name (str)
        NOTE: Does NOT include passkey (passkey is private)
        """
        return Packet(
            src=self.my_address,
            dst=BROADCAST,
            pkt_id=self._next_id(),
            ttl=self.default_ttl,
            msg_type=MSG_CHANNEL_ANNOUNCE,
            channel=0,
            payload=channel_name.encode() if isinstance(channel_name, str) else channel_name
        )


if __name__ == '__main__':
    print("=== Packet Module Test ===\n")
    
    factory = PacketFactory(my_address=1)
    
    dm = factory.create_dm(dst=2, message="Private message")
    print(f"DM: {dm}")
    print(f"Packed: {dm.to_hex()}")
    print(f"Size: {len(dm.pack())} bytes\n")
    
    ch_msg = factory.create_channel_message(channel=1, message="Hello Unit 1!")
    print(f"Channel: {ch_msg}")
    print(f"Packed: {ch_msg.to_hex()}")
    print(f"Size: {len(ch_msg.pack())} bytes\n")
    
    discover = factory.create_discover()
    print(f"Discover: {discover}\n")
    
    announce = factory.create_announce("BaseCAMP")
    print(f"Announce: {announce}\n")
    
    unpacked = Packet.unpack(ch_msg.pack())
    print(f"Unpacked: {unpacked}")