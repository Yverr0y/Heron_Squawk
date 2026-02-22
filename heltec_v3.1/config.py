"""
Configuration Storage for Heltec V3.1
Persistent settings stored in flash
"""

import json

CONFIG_FILE = '/config.json'

# Default configuration
_defaults = {
    'address': 0,
    'network_id': 18,
    'frequency': 915000000,
    'spreading_factor': 9,
    'bandwidth': 7,  # 7 = 125kHz
    'coding_rate': 1,  # 1 = 4/5
    'preamble': 12,
    'tx_power': 22,
    'passphrase': '',
    'node_name': 'Heltec',
}

_config = None


def _load():
    """Load configuration from file"""
    global _config
    try:
        with open(CONFIG_FILE, 'r') as f:
            _config = json.load(f)
            # Ensure all defaults exist
            for key, value in _defaults.items():
                if key not in _config:
                    _config[key] = value
    except (OSError, ValueError):
        _config = _defaults.copy()
    return _config


def _save():
    """Save configuration to file"""
    global _config
    if _config is None:
        _config = _defaults.copy()
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(_config, f)
        return True
    except OSError as e:
        print(f"Failed to save config: {e}")
        return False


def get(key, default=None):
    """Get configuration value"""
    global _config
    if _config is None:
        _load()
    return _config.get(key, default if default is not None else _defaults.get(key))


def set(key, value):
    """Set configuration value (not saved until save() is called)"""
    global _config
    if _config is None:
        _load()
    _config[key] = value


def save():
    """Save current configuration to flash"""
    return _save()


def load():
    """Reload configuration from flash"""
    return _load()


def reset():
    """Reset to defaults"""
    global _config
    _config = _defaults.copy()
    return _save()


# Convenience functions for common settings

def get_address():
    return get('address')


def set_address(addr):
    if not 0 <= addr <= 65535:
        raise ValueError("Address must be 0-65535")
    set('address', addr)


def get_network_id():
    return get('network_id')


def set_network_id(net_id):
    if net_id not in [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18]:
        raise ValueError("Network ID must be 3-15 or 18")
    set('network_id', net_id)


def get_frequency():
    return get('frequency')


def set_frequency(freq):
    # Basic validation for common ISM bands
    if not (860000000 <= freq <= 930000000):
        raise ValueError("Frequency must be 860-930 MHz")
    set('frequency', freq)


def get_passphrase():
    return get('passphrase')


def set_passphrase(passphrase):
    set('passphrase', passphrase)


def get_node_name():
    return get('node_name')


def set_node_name(name):
    if len(name) > 20:
        raise ValueError("Node name max 20 characters")
    set('node_name', name)


def get_spreading_factor():
    return get('spreading_factor')


def set_spreading_factor(sf):
    if not 5 <= sf <= 12:
        raise ValueError("SF must be 5-12")
    set('spreading_factor', sf)


def get_bandwidth():
    return get('bandwidth')


def set_bandwidth(bw):
    if bw not in [7, 8, 9]:
        raise ValueError("Bandwidth must be 7(125kHz), 8(250kHz), or 9(500kHz)")
    set('bandwidth', bw)


def get_coding_rate():
    return get('coding_rate')


def set_coding_rate(cr):
    if not 1 <= cr <= 4:
        raise ValueError("Coding rate must be 1-4")
    set('coding_rate', cr)


def get_preamble():
    return get('preamble')


def set_preamble(preamble):
    if not 4 <= preamble <= 24:
        raise ValueError("Preamble must be 4-24")
    set('preamble', preamble)


def get_tx_power():
    return get('tx_power')


def set_tx_power(power):
    if not -9 <= power <= 22:
        raise ValueError("TX power must be -9 to 22 dBm")
    set('tx_power', power)


def print_config():
    """Print current configuration"""
    global _config
    if _config is None:
        _load()

    print("\n=== Heltec V3.1 Configuration ===")
    print(f"  Address:     {_config['address']}")
    print(f"  Network ID:  {_config['network_id']}")
    print(f"  Frequency:   {_config['frequency']} Hz")
    print(f"  SF:          {_config['spreading_factor']}")
    print(f"  Bandwidth:   {['', '', '', '', '', '', '', '125kHz', '250kHz', '500kHz'][_config['bandwidth']]}")
    print(f"  Coding Rate: 4/{_config['coding_rate'] + 4}")
    print(f"  Preamble:    {_config['preamble']}")
    print(f"  TX Power:    {_config['tx_power']} dBm")
    print(f"  Node Name:   {_config['node_name']}")
    print(f"  Passphrase:  {'*' * len(_config['passphrase']) if _config['passphrase'] else '(not set)'}")
    print()


# Auto-load on import
_load()
