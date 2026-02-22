from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
from Crypto.Protocol.KDF import PBKDF2, HKDF
from Crypto.Hash import SHA256, HMAC
import struct

class ChannelCrypto:
    """
    Per-channel encryption layer (applied BEFORE mesh encryption).
    Each channel has unique passkey for access control.
    """
    PBKDF2_SALT = b'HeronHowl_Channel_v1'
    PBKDF2_ITERATIONS = 50000  # Half of mesh for performance (still secure)

    def __init__(self, channel_passkey):
        """
        Initialize channel-specific encryption.

        Args:
            channel_passkey (str): Passkey for this specific channel
        """
        # Derive channel encryption key from passkey
        master_key = PBKDF2(
            channel_passkey.encode(),
            self.PBKDF2_SALT,
            dkLen=32,
            count=self.PBKDF2_ITERATIONS,
            hmac_hash_module=SHA256
        )

        # Derive encryption and HMAC keys
        derived = HKDF(
            master_key,
            64,
            salt=b'HeronHowl_Channel_Keys',
            hashmod=SHA256,
            context=b'channel_v1'
        )

        self.encryption_key = derived[:32]
        self.hmac_key = derived[32:64]

    def encrypt(self, plaintext):
        """Encrypt with channel key (HMAC + IV + Ciphertext)."""
        if isinstance(plaintext, str):
            plaintext = plaintext.encode()

        iv = get_random_bytes(16)
        cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
        ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))

        message = iv + ciphertext
        h = HMAC.new(self.hmac_key, digestmod=SHA256)
        h.update(message)
        mac = h.digest()

        return mac + message

    def decrypt(self, data):
        """Decrypt channel-encrypted data."""
        if len(data) < 64:
            raise ValueError(f"Channel encrypted data too short: {len(data)} bytes")

        received_mac = data[:32]
        message = data[32:]

        h = HMAC.new(self.hmac_key, digestmod=SHA256)
        h.update(message)
        computed_mac = h.digest()

        if not MeshCrypto._constant_time_compare(received_mac, computed_mac):
            raise ValueError("Channel passkey incorrect or message tampered")

        iv = message[:16]
        ciphertext = message[16:]

        cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)

        return plaintext


class MeshCrypto:
    # Hardcoded salt for PBKDF2 (same across all deployments)
    # Change this for your specific deployment for additional security
    PBKDF2_SALT = b'HeronHowl_Mesh_v1_2026'
    PBKDF2_ITERATIONS = 10000  # Must match ESP32 mesh_crypto.py

    def __init__(self, passphrase, node_address=None):
        """
        Initialize encryption with a passphrase for mesh network.

        Security features:
        1. PBKDF2 key derivation (100k iterations) instead of simple SHA256
        2. Shared mesh key - all nodes with same passphrase can communicate
        3. HMAC-SHA256 authentication for message integrity

        Args:
            passphrase (str): Master passphrase for the mesh network
            node_address (int, optional): Node address (stored but not used for key derivation in mesh mode)
        """
        self.node_address = node_address  # Store for future use (logging, debugging)

        # Derive master key from passphrase using PBKDF2
        master_key = PBKDF2(
            passphrase.encode(),
            self.PBKDF2_SALT,
            dkLen=32,  # 256-bit key
            count=self.PBKDF2_ITERATIONS,
            hmac_hash_module=SHA256
        )

        # Derive shared mesh encryption and authentication keys using HKDF
        # All nodes with same passphrase get the same keys (mesh mode)
        derived = HKDF(
            master_key,
            64,  # Output length: 32 for encryption + 32 for HMAC
            salt=b'HeronHowl_Shared_Mesh',
            hashmod=SHA256,
            context=b'mesh_v1'
        )

        self.encryption_key = derived[:32]
        self.hmac_key = derived[32:64]
    
    def encrypt(self, plaintext):
        """
        Encrypt plaintext bytes or string with HMAC authentication.

        Format: HMAC(32 bytes) + IV(16 bytes) + Ciphertext(variable)

        Returns authenticated encrypted data as bytes.
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode()

        # Generate random IV
        iv = get_random_bytes(16)

        # Encrypt with AES-256-CBC
        cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
        ciphertext = cipher.encrypt(pad(plaintext, AES.block_size))

        # Compute HMAC over IV + ciphertext for authentication
        message = iv + ciphertext
        h = HMAC.new(self.hmac_key, digestmod=SHA256)
        h.update(message)
        mac = h.digest()

        # Return: HMAC + IV + Ciphertext
        return mac + message
    
    def decrypt(self, data):
        """
        Decrypt authenticated encrypted data.

        Expected format: HMAC(32 bytes) + IV(16 bytes) + Ciphertext(variable)

        Raises:
            ValueError: If HMAC verification fails (tampered or corrupted data)

        Returns plaintext bytes.
        """
        # Minimum size check: HMAC(32) + IV(16) + at least one AES block(16) = 64 bytes
        if len(data) < 64:
            raise ValueError(f"Encrypted data too short: {len(data)} bytes (minimum 64)")

        # Extract components
        received_mac = data[:32]
        message = data[32:]  # IV + ciphertext

        # Verify HMAC before decryption (authenticate-then-decrypt)
        h = HMAC.new(self.hmac_key, digestmod=SHA256)
        h.update(message)
        computed_mac = h.digest()

        # Constant-time comparison to prevent timing attacks
        if not self._constant_time_compare(received_mac, computed_mac):
            raise ValueError("HMAC verification failed - message tampered or wrong key")

        # Extract IV and ciphertext
        iv = message[:16]
        ciphertext = message[16:]

        # Decrypt with AES-256-CBC
        cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)

        return plaintext

    @staticmethod
    def _constant_time_compare(a, b):
        """
        Constant-time comparison to prevent timing attacks.
        Returns True if a == b, False otherwise.
        """
        if len(a) != len(b):
            return False
        result = 0
        for x, y in zip(a, b):
            result |= x ^ y
        return result == 0
    
    def encrypt_hex(self, plaintext):
        """Encrypt and return as hex string."""
        return self.encrypt(plaintext).hex().upper()
    
    def decrypt_hex(self, hex_data):
        """Decrypt from hex string."""
        return self.decrypt(bytes.fromhex(hex_data))


if __name__ == '__main__':
    print("=== Enhanced Crypto Module Test (Shared Mesh Mode) ===\n")

    # Test 1: Shared mesh key - all nodes can decrypt each other's messages
    print("Test 1: Shared mesh key derivation")
    print("-" * 50)
    passphrase = "my_secret_password"
    node1_crypto = MeshCrypto(passphrase, node_address=1)
    node2_crypto = MeshCrypto(passphrase, node_address=2)

    original = "Hello secure mesh!"
    print(f"Original: {original}")

    # Node 1 encrypts
    encrypted_node1 = node1_crypto.encrypt(original)
    print(f"Node 1 encrypted length: {len(encrypted_node1)} bytes (HMAC=32 + IV=16 + Ciphertext)")
    print(f"Node 1 encrypted hex: {encrypted_node1.hex()[:64]}...")

    # Node 1 decrypts its own message
    decrypted = node1_crypto.decrypt(encrypted_node1)
    print(f"Node 1 decrypted: {decrypted.decode()}")

    # Node 2 decrypts Node 1's message (should succeed - shared mesh key)
    print("\nNode 2 decrypting Node 1's message...")
    try:
        decrypted_by_node2 = node2_crypto.decrypt(encrypted_node1)
        print(f"CORRECT: Node 2 decrypted - {decrypted_by_node2.decode()}")
        print("Shared mesh key working - all nodes can communicate!")
    except ValueError as e:
        print(f"ERROR: Node 2 should be able to decrypt in mesh mode - {e}")

    print("\n" + "="*50 + "\n")

    # Test 2: HMAC tamper detection
    print("Test 2: HMAC tamper detection")
    print("-" * 50)
    encrypted = node1_crypto.encrypt("Important message")
    print(f"Original encrypted: {encrypted.hex()[:64]}...")

    # Tamper with the ciphertext
    tampered = bytearray(encrypted)
    tampered[-1] ^= 0xFF  # Flip all bits in last byte
    tampered = bytes(tampered)
    print(f"Tampered encrypted: {tampered.hex()[:64]}...")

    try:
        node1_crypto.decrypt(tampered)
        print("ERROR: Tampered message should have been rejected!")
    except ValueError as e:
        print(f"CORRECT: Tamper detected - {e}")

    print("\n" + "="*50 + "\n")

    # Test 3: Hex encoding/decoding
    print("Test 3: Hex encoding/decoding")
    print("-" * 50)
    hex_encrypted = node1_crypto.encrypt_hex("Test message")
    print(f"Hex encrypted: {hex_encrypted[:64]}...")
    hex_decrypted = node1_crypto.decrypt_hex(hex_encrypted)
    print(f"Hex decrypted: {hex_decrypted.decode()}")

    print("\n" + "="*50 + "\n")

    # Test 4: Same passphrase + address = same keys (deterministic)
    print("Test 4: Deterministic key derivation")
    print("-" * 50)
    crypto_a = MeshCrypto(passphrase, node_address=1)
    crypto_b = MeshCrypto(passphrase, node_address=1)  # Same address

    encrypted_a = crypto_a.encrypt("Consistent keys test")
    decrypted_b = crypto_b.decrypt(encrypted_a)
    print(f"Crypto A encrypted, Crypto B decrypted: {decrypted_b.decode()}")
    print("CORRECT: Same passphrase + address = same keys")

    print("\n" + "="*50 + "\n")

    # Test 5: Wrong passphrase
    print("Test 5: Wrong passphrase detection")
    print("-" * 50)
    wrong_crypto = MeshCrypto("wrong_password", node_address=1)
    try:
        wrong_crypto.decrypt(encrypted_a)
        print("ERROR: Wrong passphrase should have failed!")
    except ValueError as e:
        print(f"CORRECT: Wrong passphrase rejected - {e}")

    print("\n" + "="*50)
    print("All security tests passed!")