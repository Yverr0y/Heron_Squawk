"""
BLE Command Handler for Heltec V3.1

Parses commands from the mobile app and executes mesh node operations.
Bridges BLE UART to the mesh_node module.
"""

import json
import config
from ble_uart import get_ble_uart

# Error codes
ERR_INVALID_FORMAT = "E001"
ERR_UNKNOWN_CMD = "E002"
ERR_MISSING_PARAM = "E003"
ERR_INVALID_PARAM = "E004"
ERR_NOT_INITIALIZED = "E005"
ERR_SEND_FAILED = "E006"
ERR_SAVE_FAILED = "E007"
ERR_NOT_FOUND = "E008"


class BleHandler:
    """
    Handles BLE commands and bridges to mesh node functionality.

    Command format: COMMAND:param1:param2:...
    Response format: RESPONSE:data or ERR:code:message
    """

    def __init__(self, ble_uart=None, mesh_node=None):
        """
        Initialize BLE handler.

        Args:
            ble_uart: BleUart instance (will create if None)
            mesh_node: MeshNode instance (can be None initially)
        """
        self.ble = ble_uart or get_ble_uart()
        self.node = mesh_node
        self.listening = False
        self.pending_init = False  # Flag for deferred INIT processing
        self.pending_send = None   # Tuple (channel, message) for deferred SEND
        self.pending_dm = None     # Tuple (address, message) for deferred DM

        # Set up command callback
        self.ble.set_callback(self._on_command)

        # Command handlers
        self._commands = {
            'PING': self._cmd_ping,
            'CONFIG': self._cmd_config,
            'JOIN': self._cmd_join,
            'LEAVE': self._cmd_leave,
            'SEND': self._cmd_send,
            'DM': self._cmd_dm,
            'LISTEN': self._cmd_listen,
            'DISCOVER': self._cmd_discover,
            'ANNOUNCE': self._cmd_announce,
            'STATUS': self._cmd_status,
            'NODES': self._cmd_nodes,
            'INIT': self._cmd_init,
        }

    def _send(self, response):
        """Send response to app."""
        self.ble.send(response)

    def _error(self, code, message):
        """Send error response."""
        self._send(f"ERR:{code}:{message}")

    def _on_command(self, command):
        """Handle incoming command from app."""
        print(f"BLE CMD: {command}")

        try:
            # Parse command
            parts = command.split(':', 1)
            cmd = parts[0].upper()
            args = parts[1] if len(parts) > 1 else ""

            # Find handler
            if cmd in self._commands:
                self._commands[cmd](args)
            else:
                self._error(ERR_UNKNOWN_CMD, f"Unknown command: {cmd}")

        except Exception as e:
            print(f"Command error: {e}")
            self._error(ERR_INVALID_FORMAT, str(e))

    def _cmd_ping(self, args):
        """Handle PING command."""
        self._send("PONG")

    def _cmd_config(self, args):
        """Handle CONFIG commands: GET, SET, SAVE."""
        parts = args.split(':', 2)
        subcmd = parts[0].upper() if parts[0] else ""

        if subcmd == "GET":
            # Return full config as JSON (hide passphrase for security)
            passphrase = config.get_passphrase()
            cfg = {
                'address': config.get_address(),
                'network_id': config.get_network_id(),
                'frequency': config.get_frequency(),
                'spreading_factor': config.get_spreading_factor(),
                'bandwidth': config.get_bandwidth(),
                'coding_rate': config.get_coding_rate(),
                'preamble': config.get_preamble(),
                'tx_power': config.get_tx_power(),
                'passphrase': '***' if passphrase else '',  # Hide actual passphrase
                'passphrase_set': bool(passphrase),  # Just indicate if set
                'node_name': config.get_node_name(),
            }
            self._send(f"CONFIG:{json.dumps(cfg)}")

        elif subcmd == "SET":
            if len(parts) < 3:
                self._error(ERR_MISSING_PARAM, "Usage: CONFIG:SET:key:value")
                return

            key = parts[1]
            value = parts[2]

            try:
                # Handle different config types
                if key == 'address':
                    config.set_address(int(value))
                elif key == 'network_id':
                    config.set_network_id(int(value))
                elif key == 'frequency':
                    config.set_frequency(int(value))
                elif key == 'spreading_factor':
                    config.set_spreading_factor(int(value))
                elif key == 'bandwidth':
                    config.set_bandwidth(int(value))
                elif key == 'coding_rate':
                    config.set_coding_rate(int(value))
                elif key == 'preamble':
                    config.set_preamble(int(value))
                elif key == 'tx_power':
                    config.set_tx_power(int(value))
                elif key == 'passphrase':
                    config.set_passphrase(value)
                    # Clear key cache so INIT will re-derive
                    try:
                        import os
                        os.remove('key_cache.dat')
                        print("Key cache cleared")
                    except:
                        pass  # Cache didn't exist
                    # Clear current node so user must re-INIT
                    self.node = None
                elif key == 'node_name':
                    config.set_node_name(value)
                else:
                    self._error(ERR_INVALID_PARAM, f"Unknown config key: {key}")
                    return

                self._send("OK")

            except ValueError as e:
                self._error(ERR_INVALID_PARAM, str(e))

        elif subcmd == "SAVE":
            if config.save():
                self._send("OK")
            else:
                self._error(ERR_SAVE_FAILED, "Failed to save config")

        else:
            self._error(ERR_INVALID_FORMAT, "Usage: CONFIG:GET or CONFIG:SET:key:value or CONFIG:SAVE")

    def _cmd_join(self, args):
        """Handle JOIN:channel_name command."""
        if not args:
            self._error(ERR_MISSING_PARAM, "Usage: JOIN:channel_name")
            return

        channel_name = args

        # Add to node if initialized
        if self.node:
            self.node.join_channel(channel_name)

        self._send(f"JOINED:{channel_name}")

    def _cmd_leave(self, args):
        """Handle LEAVE:channel_name command."""
        if not args:
            self._error(ERR_MISSING_PARAM, "Usage: LEAVE:channel_name")
            return

        channel_name = args

        # Remove from node if initialized
        if self.node:
            self.node.leave_channel(channel_name)

        self._send(f"LEFT:{channel_name}")

    def _cmd_send(self, args):
        """Handle SEND:channel_name:message command - deferred to main loop."""
        parts = args.split(':', 1)
        if len(parts) < 2:
            self._error(ERR_MISSING_PARAM, "Usage: SEND:channel_name:message")
            return

        channel_name = parts[0]
        message = parts[1]

        if not self.node:
            self._error(ERR_NOT_INITIALIZED, "Node not initialized. Set passphrase first.")
            return

        # Defer to main loop (radio operations can't run from BLE IRQ context)
        self.pending_send = (channel_name, message)
        print(f"SEND: Scheduled for main loop - {channel_name}: {message[:20]}...")

    def do_send(self):
        """Actually perform SEND - called from main loop, not IRQ context."""
        if not self.pending_send:
            return

        channel_name, message = self.pending_send
        self.pending_send = None

        if not self.node:
            self._error(ERR_NOT_INITIALIZED, "Node not initialized")
            return

        print(f"SEND: Executing send to {channel_name}")
        if self.node.send_channel(channel_name, message):
            self._send(f"SENT:{channel_name}")
        else:
            self._error(ERR_SEND_FAILED, "Failed to send message")

    def _cmd_dm(self, args):
        """Handle DM:address:message command - deferred to main loop."""
        parts = args.split(':', 1)
        if len(parts) < 2:
            self._error(ERR_MISSING_PARAM, "Usage: DM:address:message")
            return

        try:
            address = int(parts[0])
        except ValueError:
            self._error(ERR_INVALID_PARAM, "Address must be a number")
            return

        message = parts[1]

        if not self.node:
            self._error(ERR_NOT_INITIALIZED, "Node not initialized. Set passphrase first.")
            return

        # Defer to main loop (radio operations can't run from BLE IRQ context)
        self.pending_dm = (address, message)
        print(f"DM: Scheduled for main loop - to {address}")

    def do_dm(self):
        """Actually perform DM - called from main loop, not IRQ context."""
        if not self.pending_dm:
            return

        address, message = self.pending_dm
        self.pending_dm = None

        if not self.node:
            self._error(ERR_NOT_INITIALIZED, "Node not initialized")
            return

        print(f"DM: Executing send to {address}")
        if self.node.send_dm(address, message):
            self._send(f"SENT_DM:{address}")
        else:
            self._error(ERR_SEND_FAILED, "Failed to send DM")

    def _cmd_listen(self, args):
        """Handle LISTEN:START or LISTEN:STOP command."""
        subcmd = args.upper()

        if subcmd == "START":
            self.listening = True
            self._send("OK")
        elif subcmd == "STOP":
            self.listening = False
            self._send("OK")
        else:
            self._error(ERR_INVALID_FORMAT, "Usage: LISTEN:START or LISTEN:STOP")

    def _cmd_discover(self, args):
        """Handle DISCOVER command."""
        if not self.node:
            self._error(ERR_NOT_INITIALIZED, "Node not initialized")
            return

        # Send discovery if the node supports it
        if hasattr(self.node, 'send_discover'):
            self.node.send_discover()
        self._send("OK")

    def _cmd_announce(self, args):
        """Handle ANNOUNCE command."""
        if not self.node:
            self._error(ERR_NOT_INITIALIZED, "Node not initialized")
            return

        # Send announcement if the node supports it
        if hasattr(self.node, 'send_announce'):
            self.node.send_announce()
        self._send("OK")

    def _cmd_status(self, args):
        """Handle STATUS command."""
        status = {
            'initialized': self.node is not None,
            'listening': self.listening,
            'connected': self.ble.is_connected(),
            'address': config.get_address(),
            'node_name': config.get_node_name(),
        }

        if self.node:
            status['channels'] = list(self.node.channels)

        self._send(f"STATUS:{json.dumps(status)}")

    def _cmd_nodes(self, args):
        """Handle NODES command."""
        nodes = []

        if self.node and hasattr(self.node, 'known_nodes'):
            for addr, info in self.node.known_nodes.items():
                nodes.append({
                    'addr': addr,
                    'name': info.get('name', ''),
                    'rssi': info.get('rssi', 0),
                })

        self._send(f"NODES:{json.dumps(nodes)}")

    def _cmd_init(self, args):
        """Handle INIT command - set flag for deferred processing outside IRQ context."""
        passphrase = config.get_passphrase()
        if not passphrase:
            self._error(ERR_NOT_INITIALIZED, "No passphrase configured")
            return

        # Set flag for main loop to process (avoids stack overflow in IRQ context)
        self.pending_init = True
        self._send("KEY:DERIVING")
        print("INIT: Scheduled for main loop processing")

    def do_init(self):
        """Actually perform INIT - called from main loop, not IRQ context."""
        import gc

        self.pending_init = False
        print("INIT: Starting...")

        passphrase = config.get_passphrase()
        if not passphrase:
            self._error(ERR_NOT_INITIALIZED, "No passphrase configured")
            return

        gc.collect()
        print(f"INIT: Free mem: {gc.mem_free()} bytes")

        try:
            from mesh_crypto import get_crypto_cached

            # Derive crypto (most memory intensive)
            crypto = get_crypto_cached(passphrase)
            gc.collect()
            print(f"INIT: Crypto done, free mem: {gc.mem_free()} bytes")

            # Import mesh_node module
            import mesh_node
            gc.collect()

            address = config.get_address()
            if address == 0:
                address = None

            print("INIT: Creating MeshNode...")
            # MeshNode handles radio initialization with non-blocking/IRQ mode
            self.node = mesh_node.MeshNode(passphrase, address=address, crypto=crypto)
            gc.collect()

            # Patch node to forward messages to BLE
            self._patch_node_for_ble()

            # Update config with actual address (in case it was generated)
            if config.get_address() == 0:
                config.set_address(self.node.address)
                config.save()

            self._send("KEY:READY")
            self._send(f"STATUS:{json.dumps({'initialized': True, 'address': self.node.address})}")

        except Exception as e:
            print(f"Init error: {e}")
            self._error(ERR_NOT_INITIALIZED, str(e))

    def set_node(self, node):
        """Set the mesh node instance."""
        self.node = node
        if node:
            self._patch_node_for_ble()

    def _patch_node_for_ble(self):
        """Patch the node to forward received messages to BLE."""
        if not self.node:
            return

        handler = self  # Capture reference for closure
        original_process = self.node._process_message

        def patched_process(src_addr, payload):
            # Call original processing
            original_process(src_addr, payload)

            # Try to forward to BLE
            try:
                # payload is already encrypted bytes (not base64)
                # Try direct decryption first
                try:
                    decrypted = handler.node.crypto.decrypt(payload)
                    plaintext = decrypted.decode()
                except:
                    # Maybe it's base64 encoded
                    try:
                        import ubinascii as binascii
                        encrypted_bytes = binascii.a2b_base64(payload)
                        decrypted = handler.node.crypto.decrypt(encrypted_bytes)
                        plaintext = decrypted.decode()
                    except:
                        return  # Can't decrypt, skip forwarding

                if plaintext.startswith('CH:'):
                    parts = plaintext.split(':', 2)
                    if len(parts) >= 3:
                        channel_name = parts[1]
                        message_content = parts[2]

                        # Handle chunked messages - extract content after chunk header
                        if message_content.startswith('[') and ']' in message_content[:20]:
                            try:
                                header_end = message_content.index(']')
                                message_content = message_content[header_end+1:]
                            except:
                                pass

                        rssi = handler.node.sx.getRSSI() if hasattr(handler.node, 'sx') else 0
                        snr = handler.node.sx.getSNR() if hasattr(handler.node, 'sx') else 0
                        handler.forward_message(channel_name, src_addr, message_content, rssi, snr)

                elif plaintext.startswith('DM:'):
                    parts = plaintext.split(':', 2)
                    if len(parts) >= 3:
                        try:
                            target_addr = int(parts[1])
                            message_content = parts[2]
                            # Only forward if DM is for us
                            if target_addr == handler.node.address:
                                rssi = handler.node.sx.getRSSI() if hasattr(handler.node, 'sx') else 0
                                snr = handler.node.sx.getSNR() if hasattr(handler.node, 'sx') else 0
                                handler.forward_dm(src_addr, message_content, rssi, snr)
                        except:
                            pass
            except Exception as e:
                print(f"BLE forward error: {e}")

        self.node._process_message = patched_process
        print("Node patched for BLE message forwarding")

    def forward_message(self, channel, src_addr, content, rssi=0, snr=0):
        """Forward a received mesh message to the app."""
        if self.ble.is_connected():
            # Format src_addr as hex (Android app expects hex)
            addr_hex = f"{src_addr:X}"
            print(f"BLE FWD: MSG:{channel}:{addr_hex}:{rssi}:{snr}:{content[:30]}")
            self._send(f"MSG:{channel}:{addr_hex}:{rssi}:{snr}:{content}")

    def forward_dm(self, src_addr, content, rssi=0, snr=0):
        """Forward a received DM to the app."""
        if self.ble.is_connected():
            # Format src_addr as hex (Android app expects hex)
            addr_hex = f"{src_addr:X}"
            print(f"BLE FWD: DM:{addr_hex}:{rssi}:{snr}:{content[:30]}")
            self._send(f"DM:{addr_hex}:{rssi}:{snr}:{content}")


# Singleton instance
_handler = None

def get_handler(ble_uart=None, mesh_node=None):
    """Get or create the BLE handler singleton."""
    global _handler

    if _handler is None:
        _handler = BleHandler(ble_uart=ble_uart, mesh_node=mesh_node)
    elif mesh_node is not None:
        _handler.set_node(mesh_node)

    return _handler


if __name__ == '__main__':
    # Test mode
    from ble_uart import get_ble_uart

    print("BLE Handler Test Mode")
    print("Connect with nRF Connect and send commands.")
    print("Examples: PING, CONFIG:GET, STATUS")

    ble = get_ble_uart(name="HSQ-Test")
    handler = get_handler(ble_uart=ble)
    ble.start_advertising()

    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopped.")
