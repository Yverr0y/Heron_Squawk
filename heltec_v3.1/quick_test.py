"""
Quick Test Script for Heltec V3.1 Mesh Node

Upload this to the Heltec and run interactively.

Usage in REPL:
    from quick_test import *

    # Initialize with your passphrase (must match app.py!)
    setup("my_passphrase")

    # Join a channel
    join("Unit 1")

    # Send a message
    msg("Unit 1", "Hello from Heltec!")

    # Listen for messages
    rx()
"""

from mesh_node import MeshNode

# Global node instance
node = None


def setup(passphrase, address=None):
    """
    Initialize the mesh node.

    Args:
        passphrase: Must match app.py passphrase
        address: Node address (random if None)

    Note: Key derivation takes ~2-3 minutes (100k iterations for security)
    """
    global node
    print("Initializing mesh node (key derivation takes a few minutes)...")
    node = MeshNode(passphrase, address=address)
    print(f"\nNode ready! Address: {node.address}")
    return node


def join(channel_name):
    """Join a channel."""
    if node is None:
        print("Run setup('passphrase') first!")
        return
    node.join_channel(channel_name)


def msg(channel_name, message):
    """Send a channel message."""
    if node is None:
        print("Run setup('passphrase') first!")
        return
    return node.send_channel(channel_name, message)


def dm(address, message):
    """Send a direct message."""
    if node is None:
        print("Run setup('passphrase') first!")
        return
    return node.send_dm(address, message)


def rx(count=None):
    """
    Receive messages.

    Args:
        count: Number of messages to receive (None = forever)
    """
    if node is None:
        print("Run setup('passphrase') first!")
        return
    node.listen(count=count)


def rx1():
    """Receive one message."""
    if node is None:
        print("Run setup('passphrase') first!")
        return
    return node.receive_one(timeout_ms=5000)


# Print help on import
print("""
=== Heltec Mesh Node Quick Test ===

Commands:
    setup("passphrase")     - Initialize (must match app.py!)
    join("channel")         - Join a channel
    msg("channel", "text")  - Send channel message
    dm(address, "text")     - Send direct message
    rx()                    - Listen for messages
    rx1()                   - Receive one message

Example:
    setup("my_secret_key")
    join("Unit 1")
    msg("Unit 1", "Hello!")
    rx()
""")
