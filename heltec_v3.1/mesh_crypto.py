"""
Heron Squawk Mesh Crypto (MicroPython)

Simplified encryption compatible with desktop crypto.py
Uses ucryptolib (built into MicroPython) for AES.

NOTE: This is a simplified version. Full PBKDF2/HKDF would be
computationally expensive on ESP32. For testing, we use a simpler
key derivation. For production, pre-compute keys on desktop.
"""

import hashlib
import os

try:
    from ucryptolib import aes
    MICROPYTHON = True
except ImportError:
    # Running on desktop Python for testing
    from Crypto.Cipher import AES
    MICROPYTHON = False


def _hmac_sha256(key, message):
    """HMAC-SHA256 implementation."""
    block_size = 64

    if len(key) > block_size:
        key = hashlib.sha256(key).digest()
    if len(key) < block_size:
        key = key + b'\x00' * (block_size - len(key))

    o_key_pad = bytes([k ^ 0x5c for k in key])
    i_key_pad = bytes([k ^ 0x36 for k in key])

    inner = hashlib.sha256(i_key_pad + message).digest()
    return hashlib.sha256(o_key_pad + inner).digest()


def _pbkdf2_sha256(password, salt, iterations, dklen, show_progress=True, progress_callback=None):
    """Simple PBKDF2-SHA256 implementation with progress bar."""
    import gc

    if isinstance(password, str):
        password = password.encode()

    def prf(p, s):
        return _hmac_sha256(p, s)

    dk = b''
    block_num = 1

    # Progress bar settings
    bar_width = 30
    update_interval = iterations // 100  # Update every 1%
    if update_interval < 1:
        update_interval = 1

    # GC every 5% to prevent memory exhaustion
    gc_interval = iterations // 20
    if gc_interval < 1000:
        gc_interval = 1000

    while len(dk) < dklen:
        u = prf(password, salt + block_num.to_bytes(4, 'big'))
        result = bytearray(u)  # Use bytearray for in-place XOR

        for i in range(iterations - 1):
            u = prf(password, u)
            # In-place XOR to save memory
            for j in range(len(result)):
                result[j] ^= u[j]

            # Show progress every 10%
            if (i + 1) % update_interval == 0:
                progress = (i + 1) / iterations
                percent = int(progress * 100)
                if show_progress and percent % 10 == 0:
                    filled = int(bar_width * progress)
                    bar = '=' * filled + '-' * (bar_width - filled)
                    print(f'[{bar}] {percent}%')
                if progress_callback:
                    progress_callback(percent)

            # Periodic garbage collection
            if (i + 1) % gc_interval == 0:
                gc.collect()

        dk += bytes(result)
        block_num += 1
        gc.collect()

    if show_progress:
        print(f'[{"=" * bar_width}] 100%')
    if progress_callback:
        progress_callback(100)

    return dk[:dklen]


def _hkdf_expand(prk, info, length):
    """HKDF expand step (simplified)."""
    hash_len = 32
    n = (length + hash_len - 1) // hash_len

    okm = b''
    t = b''

    for i in range(1, n + 1):
        t = _hmac_sha256(prk, t + info + bytes([i]))
        okm += t

    return okm[:length]


def _pkcs7_pad(data, block_size=16):
    """PKCS7 padding."""
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def _pkcs7_unpad(data):
    """PKCS7 unpadding."""
    pad_len = data[-1]
    if pad_len > 16 or pad_len == 0:
        raise ValueError("Invalid padding")
    for i in range(pad_len):
        if data[-(i+1)] != pad_len:
            raise ValueError("Invalid padding")
    return data[:-pad_len]


class MeshCrypto:
    """
    Mesh network encryption compatible with desktop crypto.py

    Uses same key derivation:
    - PBKDF2 with salt 'HeronHowl_Mesh_v1_2026'
    - HKDF to derive encryption + HMAC keys
    - AES-256-CBC with PKCS7 padding
    - HMAC-SHA256 authentication
    """

    PBKDF2_SALT = b'HeronHowl_Mesh_v1_2026'
    PBKDF2_ITERATIONS = 10000  # With BLE off during derivation, can use more iterations
    HKDF_SALT = b'HeronHowl_Shared_Mesh'
    HKDF_INFO = b'mesh_v1'

    def __init__(self, passphrase, iterations=None, progress_callback=None):
        """
        Initialize mesh crypto.

        Args:
            passphrase: Network passphrase
            iterations: Override PBKDF2 iterations (lower for testing)
            progress_callback: Optional callback(percent) for progress updates
        """
        if iterations is None:
            iterations = self.PBKDF2_ITERATIONS

        # Derive master key
        print(f"Deriving key ({iterations} iterations)...")
        master_key = _pbkdf2_sha256(
            passphrase,
            self.PBKDF2_SALT,
            iterations,
            32,
            progress_callback=progress_callback
        )

        # HKDF to get encryption + HMAC keys
        prk = _hmac_sha256(self.HKDF_SALT, master_key)
        derived = _hkdf_expand(prk, self.HKDF_INFO, 64)

        self.encryption_key = derived[:32]
        self.hmac_key = derived[32:64]
        print("Key derivation complete")

    def encrypt(self, plaintext):
        """
        Encrypt with HMAC authentication.

        Format: HMAC(32) + IV(16) + Ciphertext
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode()

        # Random IV
        iv = os.urandom(16)

        # Pad and encrypt
        padded = _pkcs7_pad(plaintext)

        if MICROPYTHON:
            cipher = aes(self.encryption_key, 2, iv)  # Mode 2 = CBC
            ciphertext = cipher.encrypt(padded)
        else:
            cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
            ciphertext = cipher.encrypt(padded)

        # HMAC over IV + ciphertext
        message = iv + ciphertext
        mac = _hmac_sha256(self.hmac_key, message)

        return mac + message

    def decrypt(self, data):
        """
        Decrypt authenticated data.

        Expected format: HMAC(32) + IV(16) + Ciphertext
        """
        if len(data) < 64:
            raise ValueError(f"Data too short: {len(data)} bytes")

        received_mac = data[:32]
        message = data[32:]

        # Verify HMAC
        computed_mac = _hmac_sha256(self.hmac_key, message)

        if received_mac != computed_mac:
            raise ValueError("HMAC verification failed")

        iv = message[:16]
        ciphertext = message[16:]

        # Decrypt
        if MICROPYTHON:
            cipher = aes(self.encryption_key, 2, iv)
            padded = cipher.decrypt(ciphertext)
        else:
            cipher = AES.new(self.encryption_key, AES.MODE_CBC, iv)
            padded = cipher.decrypt(ciphertext)

        return _pkcs7_unpad(padded)

    def encrypt_hex(self, plaintext):
        """Encrypt and return as hex."""
        return self.encrypt(plaintext).hex().upper()

    def decrypt_hex(self, hex_data):
        """Decrypt from hex."""
        return self.decrypt(bytes.fromhex(hex_data))


# Key cache file
KEY_CACHE_FILE = 'key_cache.dat'


def _hash_passphrase(passphrase):
    """Hash passphrase to check if cached key matches."""
    import hashlib
    return hashlib.sha256(passphrase.encode() if isinstance(passphrase, str) else passphrase).digest()[:16]


def save_keys_to_cache(passphrase, encryption_key, hmac_key):
    """Save derived keys to cache file."""
    try:
        pass_hash = _hash_passphrase(passphrase)
        with open(KEY_CACHE_FILE, 'wb') as f:
            f.write(pass_hash)
            f.write(encryption_key)
            f.write(hmac_key)
        print("Keys cached for fast startup")
    except Exception as e:
        print(f"Warning: Could not cache keys: {e}")


def load_keys_from_cache(passphrase):
    """Load cached keys if they match the passphrase."""
    try:
        pass_hash = _hash_passphrase(passphrase)
        with open(KEY_CACHE_FILE, 'rb') as f:
            cached_hash = f.read(16)
            if cached_hash == pass_hash:
                encryption_key = f.read(32)
                hmac_key = f.read(32)
                if len(encryption_key) == 32 and len(hmac_key) == 32:
                    return encryption_key, hmac_key
        return None
    except:
        return None


class CachedMeshCrypto(MeshCrypto):
    """MeshCrypto subclass that can be initialized with pre-derived keys."""

    def __init__(self, encryption_key, hmac_key):
        # Skip parent __init__ - just set the keys directly
        self.encryption_key = encryption_key
        self.hmac_key = hmac_key


def get_crypto_cached(passphrase, progress_callback=None):
    """
    Get MeshCrypto with cached keys if available.
    First run will derive keys (slow), subsequent runs use cache (instant).

    Args:
        passphrase: Network passphrase
        progress_callback: Optional callback(percent) for progress updates during derivation
    """
    # Try to load from cache
    cached = load_keys_from_cache(passphrase)
    if cached:
        print("Loading cached encryption keys...")
        enc_key, hmac_key = cached
        crypto = CachedMeshCrypto(enc_key, hmac_key)
        print("Keys loaded from cache!")
        if progress_callback:
            progress_callback(100)
        return crypto

    # No cache - derive keys (slow)
    print("No cached keys found - deriving (this takes a few minutes)...")
    crypto = MeshCrypto(passphrase, progress_callback=progress_callback)

    # Cache for next time
    save_keys_to_cache(passphrase, crypto.encryption_key, crypto.hmac_key)

    return crypto


if __name__ == '__main__':
    print("Testing MeshCrypto...")

    # Test with reduced iterations
    crypto = MeshCrypto("test_password", iterations=1000)

    original = "Hello mesh network!"
    print(f"Original: {original}")

    encrypted = crypto.encrypt(original)
    print(f"Encrypted: {len(encrypted)} bytes")
    print(f"Hex: {encrypted.hex()[:64]}...")

    decrypted = crypto.decrypt(encrypted)
    print(f"Decrypted: {decrypted.decode()}")

    if decrypted.decode() == original:
        print("SUCCESS!")
    else:
        print("FAILED!")
