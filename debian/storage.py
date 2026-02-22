from datetime import datetime


class MessageStorage:
    """
    In-memory storage for messages, channels, and DMs.
    Data is kept only while the application is running.
    """

    def __init__(self):
        """Initialize empty storage."""
        self.channels = {}  # {channel_name: {"messages": []}}
        self.dms = {}  # {node_addr: {"messages": []}}

    # Channel operations
    def create_channel(self, channel_name):
        """Create a new channel."""
        if channel_name in self.channels:
            return False  # Already exists

        self.channels[channel_name] = {
            'messages': []
        }
        return True

    def join_channel(self, channel_name):
        """
        Join existing channel (or create if doesn't exist).
        Returns True always (channels are open to all nodes with mesh passkey).
        """
        if channel_name not in self.channels:
            return self.create_channel(channel_name)
        return True

    def add_channel_message(self, channel_name, from_addr, payload, rssi=None, snr=None):
        """Add message to channel history."""
        if channel_name not in self.channels:
            return False

        message = {
            'from_addr': from_addr,
            'payload': payload,
            'time': datetime.now().strftime('%H:%M:%S')
        }

        if rssi is not None:
            message['rssi'] = rssi
        if snr is not None:
            message['snr'] = snr

        self.channels[channel_name]['messages'].append(message)
        return True

    def get_channel_messages(self, channel_name):
        """Get all messages for a channel."""
        if channel_name not in self.channels:
            return []
        return self.channels[channel_name].get('messages', [])

    def list_channels(self):
        """Get list of all channels."""
        return list(self.channels.keys())

    # DM operations
    def add_dm_message(self, node_addr, from_addr, payload, rssi=None, snr=None):
        """Add message to DM history."""
        addr_str = str(node_addr)

        if addr_str not in self.dms:
            self.dms[addr_str] = {'messages': []}

        message = {
            'from_addr': from_addr,
            'payload': payload,
            'time': datetime.now().strftime('%H:%M:%S')
        }

        if rssi is not None:
            message['rssi'] = rssi
        if snr is not None:
            message['snr'] = snr

        self.dms[addr_str]['messages'].append(message)
        return True

    def get_dm_messages(self, node_addr):
        """Get all messages for a DM conversation."""
        addr_str = str(node_addr)
        if addr_str not in self.dms:
            return []
        return self.dms[addr_str].get('messages', [])

    def list_dms(self):
        """Get list of all DM conversations (returns dict of addr: addr)."""
        return {addr: addr for addr in self.dms.keys()}
