"""
Heron Squawk - Heltec V3.1 Main Firmware
LoRa mesh node compatible with RYLR999 network and app.py

This firmware enables the Heltec V3.1 to communicate with RYLR999 modules
running the desktop app.py. It uses:
- RYLR999-compatible frame format: [Dest:2 LE][Src:2 LE][Len:1][Data]
- Same encryption as app.py (PBKDF2 + HKDF + AES-256-CBC + HMAC-SHA256)
- Same channel message format: CH:channel_name:content
- Base64 encoding for transmission
"""

import time
import gc
import struct

try:
    import ubinascii as binascii
except ImportError:
    import binascii

import config
from sx1262 import SX1262
from mesh_crypto import MeshCrypto
from mesh_packet import Packet, PacketFactory, MSG_TEXT, MSG_DISCOVER, MSG_ANNOUNCE, MSG_CHANNEL_ANNOUNCE, BROADCAST


class HeronSquawkNode:
    """Main Heron Squawk mesh node compatible with app.py"""

    def __init__(self):
        self.radio = None
        self.crypto = None
        self.factory = None
        self.running = False

        # Message tracking
        self.seen_packets = {}  # pkt_id: timestamp
        self.known_nodes = {}   # address: {'name': str, 'rssi': int, 'last_seen': timestamp}
        self.pending_chunks = {}  # For reassembling chunked messages
        self.chunk_timeout = 30
        self.channels = set()  # Joined channels

        # Load configuration
        self.address = config.get_address()
        self.network_id = config.get_network_id()
        self.passphrase = config.get_passphrase()
        self.node_name = config.get_node_name()

    def begin(self):
        """Initialize the node"""
        print("Initializing Heltec V3.1...")

        # Initialize SX1262 radio with Heltec V3.1 defaults
        self.radio = SX1262()

        # Get radio parameters from config
        freq_hz = config.get_frequency()
        freq_mhz = freq_hz / 1000000.0

        # Map bandwidth config value to kHz
        bw_map = {7: 125.0, 8: 250.0, 9: 500.0}
        bw_khz = bw_map.get(config.get_bandwidth(), 125.0)

        # Coding rate: config stores 1-4, driver expects 5-8
        cr = config.get_coding_rate() + 4

        # Initialize radio
        state = self.radio.begin(
            freq=freq_mhz,
            bw=bw_khz,
            sf=config.get_spreading_factor(),
            cr=cr,
            syncWord=0x12,  # Private network
            power=config.get_tx_power(),
            preambleLength=config.get_preamble(),
            tcxoVoltage=1.7,  # Heltec V3.1 TCXO voltage
            blocking=True
        )

        if state != 0:
            print(f"ERROR: Failed to initialize SX1262, state={state}")
            return False

        print(f"  Frequency: {freq_mhz} MHz")
        print(f"  SF: {config.get_spreading_factor()}")
        print(f"  BW: {bw_khz} kHz")
        print(f"  Address: {self.address}")
        print(f"  Network ID: {self.network_id}")

        # Initialize encryption if passphrase is set
        # Uses 100k iterations to match desktop - takes ~2-3 minutes on ESP32
        if self.passphrase:
            print("  Initializing encryption (this takes a few minutes)...")
            self.crypto = MeshCrypto(self.passphrase)
            print("  Encryption: ENABLED")
        else:
            print("  Encryption: DISABLED (no passphrase)")

        # Load joined channels
        channels = config.get_channels()
        if channels:
            self.channels = set(channels)
            print(f"  Channels: {list(self.channels)}")

        # Initialize packet factory
        self.factory = PacketFactory(self.address)

        print("Initialization complete!\n")
        return True

    def _build_rylr_frame(self, dest_addr, data):
        """
        Build RYLR999-compatible frame.

        Format: [Dest: 2 bytes LE] [Src: 2 bytes LE] [Len: 1 byte] [Data]
        """
        if isinstance(data, str):
            data = data.encode()

        header = struct.pack('<HHB', dest_addr, self.address, len(data))
        return header + data

    def _parse_rylr_frame(self, data):
        """
        Parse RYLR999 frame.

        Returns: (src_addr, dest_addr, payload) or None if invalid
        """
        if len(data) < 5:
            return None

        dest_addr, src_addr, length = struct.unpack('<HHB', data[:5])
        payload = data[5:5+length]

        return (src_addr, dest_addr, payload)

    def join_channel(self, channel_name):
        """Join a channel."""
        self.channels.add(channel_name)
        print(f"Joined channel: {channel_name}")

    def send_message(self, dest, message, channel=0):
        """Send a text message"""
        if not self.crypto:
            print("ERROR: Cannot send - no passphrase configured")
            return False

        # Create packet
        pkt = self.factory.create_text(dest, message, channel)

        # Encrypt
        encrypted = self.crypto.encrypt(pkt.pack())

        # Send raw encrypted bytes
        print(f"TX -> {dest}: {message[:30]}...")
        length, state = self.radio.send(encrypted)
        return state == 0

    def send_channel_message(self, channel_name, message):
        """Send a message to a channel (broadcast)

        Uses format: CH:channel_name:content
        Encrypted with mesh passphrase, base64 encoded for radio transmission.
        Compatible with desktop app.py.

        Messages are wrapped in RYLR999-compatible frames for interoperability.
        """
        if not self.crypto:
            print("ERROR: Cannot send - no passphrase configured")
            return False

        # Format message as CH:channel_name:content (matches app.py)
        channel_msg = f"CH:{channel_name}:{message}"

        # Encrypt with mesh passphrase
        encrypted = self.crypto.encrypt(channel_msg.encode())

        # Base64 encode for ASCII-safe radio transmission
        base64_data = binascii.b2a_base64(encrypted).strip().decode('ascii')

        # Build RYLR-compatible frame (dest=0 for broadcast)
        frame = self._build_rylr_frame(0, base64_data)

        print(f"TX -> #{channel_name}: {message[:30]}...")
        length, state = self.radio.send(frame)
        return state == 0

    def send_discover(self):
        """Send node discovery broadcast"""
        if not self.crypto:
            return False

        pkt = self.factory.create_discover()
        encrypted = self.crypto.encrypt(pkt.pack())

        print("TX -> DISCOVER broadcast")
        length, state = self.radio.send(encrypted)
        return state == 0

    def send_announce(self):
        """Announce this node to the network"""
        if not self.crypto:
            return False

        pkt = self.factory.create_announce(self.node_name)
        encrypted = self.crypto.encrypt(pkt.pack())

        print(f"TX -> ANNOUNCE: {self.node_name}")
        length, state = self.radio.send(encrypted)
        return state == 0

    def handle_packet(self, data, rssi, snr):
        """Handle received packet.

        Supports two formats:
        1. RYLR frame with base64 channel message (from app.py)
        2. Raw encrypted mesh packet (DMs, announcements)
        """
        try:
            if not self.crypto:
                print(f"RX: Cannot decrypt (no passphrase)")
                return

            # First try to parse as RYLR frame
            parsed = self._parse_rylr_frame(data)
            if parsed:
                src_addr, dest_addr, payload = parsed

                # Ignore our own messages
                if src_addr == self.address:
                    return

                # Try to decode as base64 channel message (from app.py)
                try:
                    encrypted_bytes = binascii.a2b_base64(payload)
                    decrypted = self.crypto.decrypt(encrypted_bytes)
                    plaintext = decrypted.decode()

                    # Check for channel message format: CH:channel_name:content
                    if plaintext.startswith('CH:'):
                        parts = plaintext.split(':', 2)
                        if len(parts) >= 3:
                            channel_name = parts[1]
                            message_content = parts[2]

                            # Check if we're in this channel
                            if channel_name not in self.channels:
                                print(f"RX <- #{channel_name} (not joined) from {src_addr}")
                                return

                            # Handle chunked messages
                            if message_content.startswith('[') and ']' in message_content[:20]:
                                self._handle_chunk(src_addr, channel_name, message_content, rssi, snr)
                                return

                            # Single message
                            print(f"RX <- #{channel_name} [{src_addr}] RSSI:{rssi} SNR:{snr}")
                            print(f"       {message_content}")
                            return

                except Exception:
                    # Not a base64 channel message, try as raw packet
                    pass

            # Try as raw encrypted mesh packet
            try:
                decrypted = self.crypto.decrypt(data)
                pkt = Packet.unpack(decrypted)

                # Check for duplicate
                pkt_key = (pkt.src, pkt.pkt_id)
                now = time.time()
                if pkt_key in self.seen_packets:
                    if now - self.seen_packets[pkt_key] < 60:
                        return  # Duplicate within 60 seconds
                self.seen_packets[pkt_key] = now

                # Clean old entries
                self._clean_seen_packets()

                # Handle based on type
                if pkt.msg_type == MSG_TEXT:
                    self._handle_text(pkt, rssi, snr)
                elif pkt.msg_type == MSG_DISCOVER:
                    self._handle_discover(pkt, rssi)
                elif pkt.msg_type == MSG_ANNOUNCE:
                    self._handle_announce(pkt, rssi)
                elif pkt.msg_type == MSG_CHANNEL_ANNOUNCE:
                    self._handle_channel_announce(pkt, rssi)
                else:
                    print(f"RX <- {pkt.src}: Unknown type 0x{pkt.msg_type:02X}")

            except ValueError as e:
                print(f"RX: Decrypt failed - {e}")
                return

        except Exception as e:
            print(f"RX: Error - {e}")

    def _handle_chunk(self, src_addr, channel_name, message_content, rssi, snr):
        """Handle chunked message reassembly."""
        try:
            # Parse: [msg_id:chunk_num/total]content
            header_end = message_content.index(']')
            header = message_content[1:header_end]
            content = message_content[header_end+1:]

            msg_id_part, chunk_part = header.split(':')
            msg_id = int(msg_id_part)
            chunk_num, total_chunks = map(int, chunk_part.split('/'))

            # Initialize storage for this message
            if msg_id not in self.pending_chunks:
                self.pending_chunks[msg_id] = {
                    "chunks": {},
                    "total": total_chunks,
                    "from": src_addr,
                    "channel": channel_name,
                    "timestamp": time.time()
                }

            # Store chunk
            self.pending_chunks[msg_id]["chunks"][chunk_num] = content
            print(f"Chunk {chunk_num}/{total_chunks} of msg {msg_id}")

            # Check if complete
            if len(self.pending_chunks[msg_id]["chunks"]) == total_chunks:
                # Reassemble
                full_message = ""
                for i in range(1, total_chunks + 1):
                    full_message += self.pending_chunks[msg_id]["chunks"][i]

                print(f"RX <- #{channel_name} [{src_addr}] RSSI:{rssi} SNR:{snr}")
                print(f"       {full_message}")
                del self.pending_chunks[msg_id]

            # Cleanup old chunks
            self._cleanup_chunks()

        except Exception as e:
            print(f"Chunk parse error: {e}")

    def _cleanup_chunks(self):
        """Remove timed-out incomplete messages."""
        now = time.time()
        expired = [msg_id for msg_id, data in self.pending_chunks.items()
                   if now - data["timestamp"] > self.chunk_timeout]
        for msg_id in expired:
            print(f"Timeout: Abandoned incomplete message {msg_id}")
            del self.pending_chunks[msg_id]

    def _handle_channel_announce(self, pkt, rssi):
        """Handle channel announcement."""
        try:
            channel_name = pkt.payload.decode()
            print(f"RX <- {pkt.src}: Channel announced: '{channel_name}' RSSI:{rssi}")
        except:
            print(f"RX <- {pkt.src}: Channel announce (decode failed)")

    def _handle_text(self, pkt, rssi, snr):
        """Handle text message"""
        try:
            text = pkt.payload.decode()
        except UnicodeDecodeError:
            text = pkt.payload.hex()

        ch_str = f"CH{pkt.channel}" if pkt.channel else "DM"
        print(f"RX <- {pkt.src} [{ch_str}] RSSI:{rssi} SNR:{snr}")
        print(f"       {text}")

    def _handle_discover(self, pkt, rssi):
        """Handle discovery request - respond with announce"""
        print(f"RX <- {pkt.src}: DISCOVER request")
        self.known_nodes[pkt.src] = {
            'name': f'Node-{pkt.src}',
            'rssi': rssi,
            'last_seen': time.time()
        }
        # Respond with our announcement
        time.sleep_ms(100 + (self.address % 500))  # Random delay to avoid collisions
        self.send_announce()

    def _handle_announce(self, pkt, rssi):
        """Handle node announcement"""
        try:
            name = pkt.payload.decode()
        except UnicodeDecodeError:
            name = f'Node-{pkt.src}'

        print(f"RX <- {pkt.src}: ANNOUNCE '{name}' RSSI:{rssi}")
        self.known_nodes[pkt.src] = {
            'name': name,
            'rssi': rssi,
            'last_seen': time.time()
        }

    def _clean_seen_packets(self):
        """Remove old entries from seen packets"""
        now = time.time()
        to_remove = [k for k, v in self.seen_packets.items() if now - v > 120]
        for k in to_remove:
            del self.seen_packets[k]

    def listen(self, timeout_ms=1000):
        """Listen for a packet (blocking with timeout)"""
        data, state = self.radio.recv(timeout_en=True, timeout_ms=timeout_ms)
        if state == 0 and data:
            rssi = self.radio.getRSSI()
            snr = self.radio.getSNR()
            self.handle_packet(data, rssi, snr)
            return True
        return False

    def run(self):
        """Main loop"""
        self.running = True

        print("Listening for packets...")
        print("Use send_to_channel(ch, msg) to send messages\n")

        # Announce ourselves on startup
        if self.crypto:
            time.sleep(1)
            self.send_announce()

        last_gc = time.time()

        while self.running:
            # Listen for packets
            self.listen(timeout_ms=100)

            # Periodic garbage collection
            if time.time() - last_gc > 30:
                gc.collect()
                last_gc = time.time()

    def stop(self):
        """Stop the node"""
        self.running = False
        if self.radio:
            self.radio.sleep()


# Global node instance for easy access
_node = None


def init():
    """Initialize the node"""
    global _node
    config.print_config()

    # Check if passphrase is configured
    if not config.get_passphrase():
        print("WARNING: No passphrase configured!")
        print("Set with: config.set_passphrase('your_passphrase')")
        print("Then: config.save()\n")

    _node = HeronSquawkNode()
    if not _node.begin():
        print("Failed to initialize. Check hardware connections.")
        return False
    return True


def join_channel(channel_name):
    """Join a channel to receive messages."""
    global _node
    if _node is None:
        print("Call init() first")
        return False
    _node.join_channel(channel_name)
    return True


def send_to_channel(channel_name, message):
    """Send a message to a channel by name"""
    global _node
    if _node is None:
        print("Call init() first")
        return False

    # Channel name is required (string)
    if not isinstance(channel_name, str):
        print("Channel must be a name (string), e.g. 'Unit 1'")
        return False

    return _node.send_channel_message(channel_name, message)


def send_dm(dest_addr, message):
    """Send a direct message"""
    global _node
    if _node is None:
        print("Call init() first")
        return False
    return _node.send_message(dest_addr, message, channel=0)


def broadcast(message):
    """Broadcast a message to all nodes"""
    global _node
    if _node is None:
        print("Call init() first")
        return False
    return _node.send_message(BROADCAST, message, channel=0)


def discover():
    """Send discovery request"""
    global _node
    if _node is None:
        print("Call init() first")
        return False
    return _node.send_discover()


def announce():
    """Announce this node"""
    global _node
    if _node is None:
        print("Call init() first")
        return False
    return _node.send_announce()


def listen(timeout_ms=1000):
    """Listen for incoming packets"""
    global _node
    if _node is None:
        print("Call init() first")
        return False
    return _node.listen(timeout_ms)


def run():
    """Run the main loop"""
    global _node
    if _node is None:
        if not init():
            return
    try:
        _node.run()
    except KeyboardInterrupt:
        print("\nStopping...")
        _node.stop()


def nodes():
    """List known nodes"""
    global _node
    if _node is None:
        print("Call init() first")
        return
    if _node.known_nodes:
        print("\nKnown nodes:")
        for addr, info in _node.known_nodes.items():
            print(f"  {addr}: {info['name']} (RSSI: {info['rssi']})")
        print()
    else:
        print("No nodes discovered yet")


# Auto-start BLE mode on boot
if __name__ == '__main__' or True:  # Always run on import (boot)
    print("\n=== Heron Squawk - Heltec V3.1 ===\n")
    print("Starting BLE mode...")

    try:
        import ble_main
        ble_main.start()
        ble_main.run()
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        print(f"BLE error: {e}")
        print("\nFalling back to manual mode.")
        print("Commands: init(), join_channel('name'), send_to_channel('name', 'msg'), run()")