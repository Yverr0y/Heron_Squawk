"""
BLE Main Entry Point for Heltec V3.1

Starts the BLE service and handles both BLE commands and mesh radio messages.
This is the main entry point for BLE-enabled operation.

Usage:
    import ble_main
    ble_main.start()

Or for auto-start on boot, add to main.py:
    import ble_main
    ble_main.start()
"""

import time
import gc
import config
from ble_uart import get_ble_uart
from ble_handler import get_handler


# Global state
_running = False
_node = None
_handler = None
_ble = None


def start():
    """Start BLE service."""
    global _running, _node, _handler, _ble

    print("\n=== Heron Squawk BLE Mode ===\n")

    # Get device name from config
    node_name = config.get_node_name()
    address = config.get_address()

    # Create BLE name with address suffix for uniqueness
    if address and address != 0:
        ble_name = f"HSQ-{address:04X}"
    else:
        ble_name = f"HSQ-{node_name[:4]}"

    # Initialize BLE
    print(f"Initializing BLE as '{ble_name}'...")
    _ble = get_ble_uart(name=ble_name)
    _handler = get_handler(ble_uart=_ble)

    # Start advertising
    _ble.start_advertising()

    print("\nBLE service ready!")
    print("Connect with app and use INIT to initialize mesh.")
    print()

    _node = None
    _running = True
    return True


def run():
    """
    Main loop - handles BLE and radio messages.

    This blocks and runs until stop() is called or Ctrl+C.
    """
    global _running, _node, _handler

    if not _running:
        start()

    print("Running main loop. Press Ctrl+C to stop.\n")

    last_gc = time.time()
    gc_interval = 30  # Run GC every 30 seconds

    try:
        while _running:
            # Check for pending operations (deferred from BLE IRQ context)
            if _handler:
                if _handler.pending_init:
                    _handler.do_init()
                if _handler.pending_send:
                    _handler.do_send()
                if _handler.pending_dm:
                    _handler.do_dm()

            # Get node from handler (it may have been initialized via INIT command)
            node = _handler.node if _handler else None

            # Check for incoming radio messages if node is initialized
            if node:
                try:
                    # Blocking receive with 5 second timeout
                    node.receive_one(timeout_ms=5000)
                except Exception as e:
                    print(f"Radio RX error: {e}")

            # Small sleep to prevent busy loop
            time.sleep(0.02)

            # Periodic garbage collection
            now = time.time()
            if now - last_gc > gc_interval:
                gc.collect()
                last_gc = now

    except KeyboardInterrupt:
        print("\nStopping...")

    _running = False
    print("BLE service stopped.")


def stop():
    """Stop the BLE service."""
    global _running
    _running = False


def is_running():
    """Check if BLE service is running."""
    return _running


def get_node():
    """Get the mesh node instance."""
    return _node


def send_to_app(message):
    """Send a message to the connected app."""
    if _ble and _ble.is_connected():
        _ble.send(message)
        return True
    return False


# Patch mesh_node to forward messages to BLE
def _patch_node_for_ble():
    """Patch the mesh node to forward received messages to BLE."""
    global _node, _handler

    if _node is None:
        return

    # Store original process_message
    original_process = _node._process_message

    def patched_process(src_addr, payload):
        # Call original
        original_process(src_addr, payload)

        # Also try to forward to BLE if we got a channel message
        # This is a simplified approach - ideally we'd hook deeper
        try:
            import ubinascii as binascii
            encrypted_bytes = binascii.a2b_base64(payload)
            decrypted = _node.crypto.decrypt(encrypted_bytes)
            plaintext = decrypted.decode()

            if plaintext.startswith('CH:'):
                parts = plaintext.split(':', 2)
                if len(parts) >= 3:
                    channel_name = parts[1]
                    message_content = parts[2]

                    # Handle chunked messages (skip for now, just forward complete)
                    if not message_content.startswith('['):
                        rssi = _node.sx.getRSSI() if hasattr(_node, 'sx') else 0
                        snr = _node.sx.getSNR() if hasattr(_node, 'sx') else 0
                        _handler.forward_message(channel_name, src_addr, message_content, rssi, snr)
        except:
            pass  # Silently ignore errors in forwarding

    _node._process_message = patched_process


# Simple usage
if __name__ == '__main__':
    start()
    run()
