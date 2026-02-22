"""
Heron Squawk Mesh Node for Heltec V3.1

True mesh network with multi-hop routing.
Messages are relayed through intermediate nodes to reach distant destinations.

Features:
- Flood-based mesh routing with TTL
- Duplicate message detection (prevents loops)
- Automatic message forwarding
- Compatible with app.py

Mesh Header Format (prepended to encrypted payload):
  M[origin:2][msg_id:2][ttl:1][hops:1] + encrypted_data
  - 'M' = mesh marker byte (0x4D)
  - origin = original sender address (2 bytes, big-endian)
  - msg_id = unique message ID from origin (2 bytes, big-endian)
  - ttl = time-to-live / remaining hops (1 byte)
  - hops = hop count so far (1 byte)

Usage:
    import mesh_node

    # Initialize with passphrase (must match app.py)
    node = mesh_node.MeshNode("my_secret_passphrase", address=12345)

    # Join a channel
    node.join_channel("Unit 1")

    # Send to channel (will be relayed by other nodes)
    node.send_channel("Unit 1", "Hello from Heltec!")

    # Listen for messages (automatically relays for others)
    node.listen()
"""

from sx1262 import SX1262
import struct
import time
import os

try:
    import ubinascii as binascii
except ImportError:
    import binascii

# Import our mesh modules
from mesh_crypto import MeshCrypto, get_crypto_cached
from mesh_packet import Packet, PacketFactory, MSG_TEXT, MSG_CHANNEL_ANNOUNCE, BROADCAST

# Global radio instance
sx = None


# Mesh routing constants
MESH_MARKER = 0x4D  # 'M' - identifies mesh-routed packets
MESH_HEADER_SIZE = 7  # M + origin(2) + msg_id(2) + ttl(1) + hops(1)
DEFAULT_TTL = 5  # Max 5 hops
SEEN_CACHE_SIZE = 100  # Remember last 100 messages to prevent loops
SEEN_CACHE_TIMEOUT = 60  # Forget seen messages after 60 seconds


class MeshNode:
    """
    True mesh network node with multi-hop routing.

    Message format:
    - Mesh header: M[origin:2][msg_id:2][ttl:1][hops:1]
    - Followed by: base64(encrypted("CH:channel_name:message"))

    Messages are automatically relayed when:
    - TTL > 0
    - We haven't seen this message before (origin + msg_id combo)
    """

    def __init__(self, passphrase, address=None, crypto=None):
        """
        Initialize mesh node.

        Args:
            passphrase: Network passphrase (must match app.py)
            address: Node address (1-65535, random if None)
            crypto: Pre-initialized MeshCrypto (skips key derivation if provided)

        Note: Key derivation uses 100k iterations and takes ~2-3 minutes on ESP32
        """
        global sx

        # Generate random address if not specified
        if address is None:
            address = int.from_bytes(os.urandom(2), 'big')
            if address == 0:
                address = 1  # Avoid broadcast address

        self.address = address
        self.passphrase = passphrase
        self.channels = set()  # Joined channels
        self.pending_chunks = {}  # For reassembling chunked messages
        self.chunk_timeout = 30  # Seconds before abandoning incomplete message
        self._pkt_counter = 0

        # Mesh routing: seen messages cache {(origin, msg_id): timestamp}
        self._seen_messages = {}
        self._msg_counter = int.from_bytes(os.urandom(2), 'big')  # Random start

        # Initialize crypto (use provided or derive)
        print(f"Node address: {self.address}")
        if crypto is not None:
            self.crypto = crypto
        else:
            self.crypto = get_crypto_cached(passphrase)

        # Initialize radio
        self._init_radio()

    def _init_radio(self):
        """Initialize SX1262 with RYLR999-compatible settings."""
        global sx

        if sx is None:
            print("Initializing SX1262...")
            sx = SX1262()

            sx.begin(
                freq=915.0,
                bw=125.0,
                sf=9,
                cr=5,
                preambleLength=12,
                syncWord=0x12,  # Private LoRa sync word (matches RYLR999 Network ID 18)
                tcxoVoltage=1.7,
                blocking=True  # Blocking mode with short timeouts
            )
            print("Radio ready!")

        self.sx = sx

    def _recover_radio(self):
        """Recover radio from stuck state by doing a full reset and reinit."""
        global sx
        print("Recovering radio...")

        try:
            # Use the driver's built-in reset
            self.sx.reset()
            time.sleep(0.1)

            # Put into standby mode
            self.sx.standby()

            print("Radio recovered!")
        except Exception as e:
            print(f"Radio recovery failed: {e}")
            # If that didn't work, try full reinit
            try:
                self.sx.begin(
                    freq=915.0,
                    bw=125.0,
                    sf=9,
                    cr=5,
                    preambleLength=12,
                    syncWord=0x12,  # Private LoRa sync word (matches RYLR999 Network ID 18)
                    tcxoVoltage=1.7,
                    blocking=True
                )
                print("Radio reinitialized!")
            except Exception as e2:
                print(f"Full reinit failed: {e2}")

    def _next_pkt_id(self):
        """Get next packet ID."""
        self._pkt_counter = (self._pkt_counter + 1) % 65536
        return self._pkt_counter

    def _next_msg_id(self):
        """Get next mesh message ID."""
        self._msg_counter = (self._msg_counter + 1) % 65536
        return self._msg_counter

    def _build_mesh_header(self, msg_id, ttl=DEFAULT_TTL, hops=0):
        """
        Build mesh routing header.

        Format: M[origin:2][msg_id:2][ttl:1][hops:1]
        Returns 7 bytes.
        """
        return struct.pack('>BHHBB', MESH_MARKER, self.address, msg_id, ttl, hops)

    def _parse_mesh_header(self, data):
        """
        Parse mesh routing header.

        Returns: (origin, msg_id, ttl, hops, payload) or None if not a mesh packet.
        """
        if len(data) < MESH_HEADER_SIZE:
            return None

        if data[0] != MESH_MARKER:
            return None

        marker, origin, msg_id, ttl, hops = struct.unpack('>BHHBB', data[:MESH_HEADER_SIZE])
        payload = data[MESH_HEADER_SIZE:]

        return (origin, msg_id, ttl, hops, payload)

    def _have_seen(self, origin, msg_id):
        """Check if we've seen this message recently."""
        key = (origin, msg_id)
        if key in self._seen_messages:
            return True
        return False

    def _mark_seen(self, origin, msg_id):
        """Mark message as seen."""
        key = (origin, msg_id)
        self._seen_messages[key] = time.time()

        # Cleanup old entries if cache is too large
        if len(self._seen_messages) > SEEN_CACHE_SIZE:
            self._cleanup_seen()

    def _cleanup_seen(self):
        """Remove old entries from seen cache."""
        current_time = time.time()
        expired = [k for k, t in self._seen_messages.items()
                   if current_time - t > SEEN_CACHE_TIMEOUT]
        for k in expired:
            del self._seen_messages[k]

    def _build_rylr_frame(self, dest_addr, data):
        """
        Build RYLR999-compatible frame for transmission.

        RYLR999 packet format (reverse-engineered):
        [Dest: 2 bytes LE] [Src: 2 bytes LE] [Len: 1 byte] [Data]

        When RYLR999 receives this, it outputs:
        +RCV=<src_addr>,<len>,<data>,<rssi>,<snr>
        """
        if isinstance(data, str):
            data = data.encode()

        header = struct.pack('<HHB', dest_addr, self.address, len(data))
        return header + data

    def _send_rylr_packet(self, data):
        """
        Send data with RYLR999-compatible framing.

        Wraps data in RYLR frame format so RYLR999 receivers
        will see proper sender address.

        Args:
            data: bytes or str to send

        Returns:
            (length, state) tuple from radio
        """
        if isinstance(data, str):
            data = data.encode()

        # Build RYLR frame: [dest=0 broadcast][src=our_addr][len][data]
        frame = self._build_rylr_frame(0, data)  # 0 = broadcast

        print(f"  RYLR frame: {len(frame)} bytes (header=5 + data={len(data)})")

        return self.sx.send(frame)

    def _parse_rylr_frame(self, data):
        """
        Parse RYLR999 frame.

        Format: [Dest: 2 bytes LE] [Src: 2 bytes LE] [Len: 1 byte] [Data]
        Returns: (src_addr, dest_addr, payload) or None if invalid

        Validation:
        - Length field must exactly match remaining data
        - Source address must be non-zero (0 is broadcast, not a valid source)
        - First byte must NOT be 'M' (0x4D) which indicates base64 mesh data
        """
        if len(data) < 6:  # Need header + at least 1 byte payload
            return None

        # If data starts with 'M', it's likely base64 mesh data, not RYLR frame
        if data[0] == 0x4D:  # 'M' = mesh marker
            return None

        dest_addr, src_addr, length = struct.unpack('<HHB', data[:5])

        # Critical validation: length must exactly match remaining data
        remaining = len(data) - 5
        if length != remaining:
            return None

        # Source address must be valid (non-zero)
        if src_addr == 0:
            return None

        payload = data[5:5+length]
        return (src_addr, dest_addr, payload)

    def join_channel(self, channel_name):
        """Join a channel."""
        self.channels.add(channel_name)
        print(f"Joined channel: {channel_name}")

    def leave_channel(self, channel_name):
        """Leave a channel."""
        self.channels.discard(channel_name)
        print(f"Left channel: {channel_name}")

    def send_channel(self, channel_name, message):
        """
        Send message to a channel with mesh routing.

        Format:
        - Mesh header: M[origin:2][msg_id:2][ttl:1][hops:1]
        - Payload: base64(encrypted("CH:channel_name:message"))

        Messages will be relayed by other nodes in the mesh.
        """
        if channel_name not in self.channels:
            print(f"Warning: Not joined to channel '{channel_name}'")

        # Max chunk size to stay under 240 byte limit after mesh header + encryption + base64
        # Mesh header = 7 bytes, so we have less room
        max_chunk_size = 20

        # Split into chunks if needed
        chunks = []
        if len(message) <= max_chunk_size:
            chunks = [message]
        else:
            for i in range(0, len(message), max_chunk_size):
                chunks.append(message[i:i + max_chunk_size])

        # Generate message ID for chunking (separate from mesh msg_id)
        chunk_id = int.from_bytes(os.urandom(2), 'big') % 9000 + 1000
        total_chunks = len(chunks)

        success_count = 0
        for chunk_num, chunk in enumerate(chunks, 1):
            # Format message (matches app.py format)
            if total_chunks > 1:
                chunk_msg = f"CH:{channel_name}:[{chunk_id}:{chunk_num}/{total_chunks}]{chunk}"
            else:
                chunk_msg = f"CH:{channel_name}:{chunk}"

            # Encrypt with mesh crypto
            encrypted = self.crypto.encrypt(chunk_msg.encode())

            # Build mesh header (each chunk gets unique mesh msg_id)
            mesh_msg_id = self._next_msg_id()
            mesh_header = self._build_mesh_header(mesh_msg_id, ttl=DEFAULT_TTL, hops=0)

            # Mark as seen so we don't relay our own message
            self._mark_seen(self.address, mesh_msg_id)

            # Combine mesh header + encrypted, then base64 encode entire thing
            # This matches RYLR999 format: base64(mesh_header + encrypted)
            mesh_payload = mesh_header + encrypted
            base64_payload = binascii.b2a_base64(mesh_payload).strip().decode('ascii')

            # Check size (RYLR999 limit is 240 bytes for AT+SEND)
            if len(base64_payload) > 240:
                print(f"ERROR: Chunk too large ({len(base64_payload)} bytes)")
                return False

            # Send with RYLR999-compatible framing so receiver sees our address
            print(f"Sending chunk {chunk_num}/{total_chunks}: {len(base64_payload)} chars (TTL={DEFAULT_TTL})")
            print(f"  Payload preview: {base64_payload[:50]}...")

            # Try to send with RYLR framing, with recovery on failure
            try:
                length, state = self._send_rylr_packet(base64_payload)
            except Exception as e:
                print(f"Send exception: {e}, attempting recovery...")
                self._recover_radio()
                try:
                    length, state = self._send_rylr_packet(base64_payload)
                except Exception as e2:
                    print(f"Recovery failed: {e2}")
                    return False

            if state == 0:
                success_count += 1
                if chunk_num < total_chunks:
                    time.sleep(0.2)  # Delay between chunks
            else:
                print(f"Send failed: state={state}, attempting recovery...")
                self._recover_radio()
                try:
                    length, state = self._send_rylr_packet(base64_payload)
                    if state == 0:
                        success_count += 1
                        continue
                except:
                    pass
                print(f"Send failed after recovery")
                return False

        if success_count == total_chunks:
            print(f"Sent to #{channel_name}: {message}")
            return True
        return False

    def send_dm(self, dest_addr, message):
        """
        Send direct message to a specific node via mesh routing.

        DMs use format: DM:target_address:content
        They are broadcast with mesh headers so they can be relayed
        through intermediate nodes to reach the destination.
        """
        # Format: DM:target_address:content
        dm_msg = f"DM:{dest_addr}:{message}"

        # Encrypt with mesh key
        encrypted = self.crypto.encrypt(dm_msg.encode())

        # Build mesh header for multi-hop routing
        msg_id = self._next_msg_id()
        mesh_header = self._build_mesh_header(msg_id, DEFAULT_TTL, 0)
        mesh_payload = mesh_header + encrypted

        # Mark as seen so we don't process our own relayed messages
        self._mark_seen(self.address, msg_id)

        # Base64 encode entire mesh payload (compatible with RYLR999)
        b64_payload = binascii.b2a_base64(mesh_payload).strip().decode('ascii')

        print(f"Sending DM to {dest_addr}: {message}")
        length, state = self._send_rylr_packet(b64_payload)

        return state == 0

    def _process_message(self, src_addr, payload):
        """Process received message (channel or DM)."""
        try:
            # Payload could be:
            # 1. Binary encrypted bytes (from mesh header extraction)
            # 2. Base64 encoded encrypted bytes (legacy format)

            encrypted_bytes = None

            # First try: payload might already be binary encrypted bytes
            if isinstance(payload, bytes):
                try:
                    # Try to decrypt directly as binary
                    decrypted = self.crypto.decrypt(payload)
                    plaintext = decrypted.decode()
                    encrypted_bytes = payload  # Mark as successful
                except:
                    # Not valid encrypted binary, try base64 decode
                    try:
                        encrypted_bytes = binascii.a2b_base64(payload)
                        decrypted = self.crypto.decrypt(encrypted_bytes)
                        plaintext = decrypted.decode()
                    except:
                        encrypted_bytes = None
            else:
                # String payload - try base64 decode
                try:
                    encrypted_bytes = binascii.a2b_base64(payload)
                    decrypted = self.crypto.decrypt(encrypted_bytes)
                    plaintext = decrypted.decode()
                except:
                    encrypted_bytes = None

            if encrypted_bytes is not None:
                # Successfully decrypted - process the message

                # Check for channel message format: CH:channel_name:content
                if plaintext.startswith('CH:'):
                    parts = plaintext.split(':', 2)
                    if len(parts) >= 3:
                        channel_name = parts[1]
                        message_content = parts[2]

                        # Check if we're in this channel
                        if channel_name not in self.channels:
                            print(f"[{channel_name}] (not joined) from {src_addr}: {message_content[:50]}")
                            return

                        # Handle chunked messages
                        if message_content.startswith('[') and ']' in message_content[:20]:
                            return self._handle_chunk(src_addr, channel_name, message_content)

                        # Single message
                        print(f"[#{channel_name}] {src_addr}: {message_content}")
                        return

                # Check for DM format: DM:target_address:content
                elif plaintext.startswith('DM:'):
                    parts = plaintext.split(':', 2)
                    if len(parts) >= 3:
                        try:
                            target_addr = int(parts[1])
                            message_content = parts[2]

                            # Only process if this DM is for us
                            if target_addr == self.address:
                                print(f"[DM] {src_addr}: {message_content}")
                            else:
                                # DM not for us - already relayed if needed
                                print(f"[DM] for {target_addr}, not us ({self.address})")
                            return
                        except ValueError:
                            print(f"Invalid DM target address format")

                # Unknown format but decrypted
                print(f"[?] {src_addr}: {plaintext[:50]}")
                return

            # Try to parse as mesh packet (DM or announcement)
            try:
                pkt = Packet.unpack(payload)

                if pkt.msg_type == MSG_TEXT:
                    # DM - decrypt payload
                    try:
                        decrypted = self.crypto.decrypt(pkt.payload)
                        print(f"[DM] {pkt.src}: {decrypted.decode()}")
                    except:
                        print(f"[DM] {pkt.src}: (decryption failed)")

                elif pkt.msg_type == MSG_CHANNEL_ANNOUNCE:
                    channel_name = pkt.payload.decode()
                    print(f"[ANNOUNCE] {pkt.src} announces channel: {channel_name}")

                else:
                    print(f"[PKT] {pkt}")

            except Exception as e:
                # Not a valid packet either
                print(f"[RAW] {src_addr}: {payload.hex()[:40]}...")

        except Exception as e:
            print(f"Error processing message: {e}")

    def _handle_chunk(self, src_addr, channel_name, message_content):
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

                print(f"[#{channel_name}] {src_addr}: {full_message}")
                del self.pending_chunks[msg_id]

        except Exception as e:
            print(f"Chunk parse error: {e}")

    def _cleanup_chunks(self):
        """Remove timed-out incomplete messages."""
        current_time = time.time()
        expired = [msg_id for msg_id, data in self.pending_chunks.items()
                   if current_time - data["timestamp"] > self.chunk_timeout]
        for msg_id in expired:
            print(f"Timeout: Abandoned incomplete message {msg_id}")
            del self.pending_chunks[msg_id]

    def receive_one(self, timeout_ms=5000):
        """
        Receive and process one message (blocking with timeout).

        Handles mesh routing:
        - Processes message locally
        - Relays to other nodes if TTL > 0 and not seen before

        Supports two data formats:
        - RYLR frame from another Heltec: [Dest:2][Src:2][Len:1][base64_data]
        - Base64 data from RYLR999: Just base64(mesh_header + encrypted)

        Returns: True if message received, False if timeout/empty
        """
        self._cleanup_chunks()
        self._cleanup_seen()

        # Blocking receive with longer timeout to catch packets
        if timeout_ms > 0:
            data, state = self.sx.recv(timeout_en=True, timeout_ms=timeout_ms)
        else:
            data, state = self.sx.recv(timeout_en=False)

        if state != 0 or not data or len(data) < 5:
            return False

        rssi = self.sx.getRSSI()
        snr = self.sx.getSNR()

        print(f"\n=== RAW RX: {len(data)} bytes, RSSI={rssi}, SNR={snr} ===")
        try:
            print(f"  Hex: {data[:30].hex()}")
            print(f"  ASCII: {data[:30]}")
        except:
            print(f"  Raw: {data[:30]}")

        # Try to parse as RYLR frame first (from another Heltec with framing)
        parsed = self._parse_rylr_frame(data)
        if parsed:
            src_addr, dest_addr, frame_payload = parsed
            print(f"  RYLR frame: src={src_addr}, dest={dest_addr}, payload={len(frame_payload)} bytes")

            # Ignore our own transmissions
            if src_addr == self.address:
                print(f"  Ignoring own transmission")
                return True

            # The frame payload is base64 encoded mesh data
            try:
                payload = binascii.a2b_base64(frame_payload)
                print(f"  Base64 decoded: {len(payload)} bytes")
            except:
                print(f"  Base64 decode failed, using raw payload")
                payload = frame_payload
        else:
            # Not RYLR frame - likely base64 from RYLR999 (no framing header)
            print(f"  Not RYLR frame - trying as raw base64 from RYLR999")
            src_addr = 0  # Will be extracted from mesh header

            # RYLR999 sends ASCII base64 string
            try:
                # Data is ASCII base64 text
                payload = binascii.a2b_base64(data)
                print(f"  Base64 decoded: {len(payload)} bytes")
            except Exception as e:
                print(f"  Base64 decode failed: {e}")
                # Not valid base64, try as raw data
                payload = data

        # Check if this is a mesh-routed packet (binary mesh header)
        print(f"  Payload first byte: 0x{payload[0]:02x} (mesh marker=0x{MESH_MARKER:02x})")
        mesh_info = self._parse_mesh_header(payload)

        if mesh_info:
            origin, msg_id, ttl, hops, inner_payload = mesh_info
            print(f"  Mesh header: origin={origin}, msg_id={msg_id}, ttl={ttl}, hops={hops}")

            # Ignore if we're the origin
            if origin == self.address:
                print(f"  Ignoring own message")
                return True

            # Check if we've seen this message before
            if self._have_seen(origin, msg_id):
                print(f"  Already seen - ignoring")
                return True

            # Mark as seen
            self._mark_seen(origin, msg_id)

            print(f"\n--- Mesh packet from {origin} (hops={hops}, TTL={ttl}, RSSI={rssi}) ---")

            # Process the message locally - inner_payload is still encrypted
            self._process_message(origin, inner_payload)

            # Relay if TTL > 0
            if ttl > 0:
                self._relay_message(origin, msg_id, ttl - 1, hops + 1, inner_payload)

        else:
            # No mesh header - try as legacy/direct data
            print(f"  No mesh header found")
            print(f"\n--- Legacy packet from {src_addr} (RSSI: {rssi}, SNR: {snr}) ---")
            self._process_message(src_addr, payload)

        return True

    def _relay_message(self, origin, msg_id, ttl, hops, payload):
        """
        Relay a mesh message to other nodes.

        Decrements TTL, increments hop count, and re-broadcasts.
        """
        # Build new mesh header with updated TTL and hops
        new_header = struct.pack('>BHHBB', MESH_MARKER, origin, msg_id, ttl, hops)
        mesh_payload = new_header + payload

        # Base64 encode for RYLR999 compatibility
        b64_payload = binascii.b2a_base64(mesh_payload).strip().decode('ascii')

        # Small random delay to avoid collisions when multiple nodes relay
        delay = (self.address % 10) * 0.05  # 0-0.45 seconds based on address
        time.sleep(delay)

        print(f"  -> Relaying for {origin} (TTL={ttl}, hops={hops})")
        length, state = self._send_rylr_packet(b64_payload)

        if state != 0:
            print(f"  -> Relay failed: state={state}")

    def listen(self, count=None):
        """
        Listen for messages continuously.

        Args:
            count: Number of messages to receive (None = forever)
        """
        print(f"\nListening as node {self.address}...")
        print(f"Joined channels: {self.channels or '(none)'}")
        print("Press Ctrl+C to stop\n")

        received = 0
        try:
            while count is None or received < count:
                if self.receive_one(timeout_ms=1000):
                    received += 1
        except KeyboardInterrupt:
            print(f"\nStopped. Received {received} messages.")


# Quick setup functions
_node = None

def init(passphrase, address=None):
    """Initialize the mesh node."""
    global _node
    _node = MeshNode(passphrase, address=address)
    return _node

def join(channel_name):
    """Join a channel."""
    if _node is None:
        print("Error: Call init() first")
        return
    _node.join_channel(channel_name)

def send(channel_name, message):
    """Send to a channel."""
    if _node is None:
        print("Error: Call init() first")
        return
    return _node.send_channel(channel_name, message)

def dm(address, message):
    """Send a DM."""
    if _node is None:
        print("Error: Call init() first")
        return
    return _node.send_dm(address, message)

def listen():
    """Listen for messages."""
    if _node is None:
        print("Error: Call init() first")
        return
    _node.listen()


if __name__ == '__main__':
    print("=== Heron Squawk Mesh Node ===")
    print("")
    print("Usage:")
    print("  from mesh_node import init, join, send, listen")
    print("")
    print("  # Initialize (use same passphrase as app.py)")
    print("  init('my_secret_passphrase')")
    print("")
    print("  # Join a channel")
    print("  join('Unit 1')")
    print("")
    print("  # Send a message")
    print("  send('Unit 1', 'Hello from Heltec!')")
    print("")
    print("  # Listen for messages")
    print("  listen()")
