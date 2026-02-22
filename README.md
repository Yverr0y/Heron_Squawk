<p align="center">
  <img src="HWL_MEDIA/icon1.jpg" alt="Hog Worxs Labs" width="200">
</p>

<h3 align="center">A project by Hog Worxs Labs LLC</h3>
<p align="center"><a href="https://www.hogworxslabs.com">www.hogworxslabs.com</a></p>

---

# HeronSquawk

An encrypted LoRa mesh network for anonymous, long-range communication -- no internet, no cell service, no infrastructure required.

## Why This Exists

LoRa has always fascinated me. Long-range wireless communication at no recurring cost, just hardware you can buy off Amazon. I already had a few Heltec V3.1 ESP32-S3 boards with built-in SX1262 LoRa radios, but then my brother sent me a link to the RYLR999 -- a LoRa module that puts out 30 dBm (1 watt), the legal maximum without a license. I ordered a pair immediately.

The problem: the RYLR999 and Heltec V3.1 are completely incompatible out of the box. The obvious choice would be Meshtastic, but the RYLR999 runs proprietary baked-in firmware and only accepts AT commands over serial. There's no way to flash Meshtastic onto it. So I set out to build my own.

Getting these two radios to talk to each other required reverse engineering. The RYLR999 documentation doesn't fully describe its on-air packet format, so I used an SDR (software-defined radio) to capture and analyze the actual RF output. From there I was able to decode the framing, match LoRa parameters between the SX1262 and the RYLR999, and build a compatible packet format that both devices understand.

The result is HeronSquawk -- a more secure, encrypted alternative to Meshtastic built around a specific use case: **the RYLR999 acts as a base station running a web UI on a laptop or desktop, while Heltec V3.1 (or other ESP32-based LoRa) devices are carried on person and controlled from a phone over BLE.** All nodes share a passphrase decided in person, device IDs are randomized on every startup for anonymity, and all traffic is encrypted end-to-end.

It's not up to Meshtastic's level of polish -- there are probably still some bugs -- but for long-range anonymous encrypted messaging, it works. Both the web UI and the Android app are functional. The web UI is the smoother experience since the Heltec V3.1 hardware takes some time to derive encryption keys and form the mesh, but both get the job done.

## How It Works

### Architecture

```
┌──────────────────┐     LoRa (915 MHz)     ┌──────────────────┐
│   RYLR999 Base   │◄──────────────────────►│  Heltec V3.1     │
│   Station        │     up to 10+ km       │  Portable Node   │
│                  │                         │                  │
│  USB Serial ▼    │                         │  BLE ▼           │
│  ┌────────────┐  │                         │  ┌────────────┐  │
│  │  app.py    │  │                         │  │  Android   │  │
│  │  Web UI    │  │                         │  │  App       │  │
│  └────────────┘  │                         │  └────────────┘  │
└──────────────────┘                         └──────────────────┘
        ▲                                            ▲
        │              LoRa mesh routing             │
        └────────────────────────────────────────────┘
         Messages hop through intermediate nodes
```

### The Mesh

Every node participates in flood-based mesh routing. When a message is sent, nearby nodes receive it, decrement the TTL, and reforward it. This lets messages hop through intermediate nodes to reach destinations beyond direct radio range. Each node maintains a seen-cache of recent message IDs to prevent routing loops -- if you've already forwarded a message, you drop the duplicate.

Mesh header format (prepended to every encrypted payload):
```
M [origin:2] [msg_id:2] [ttl:1] [hops:1] + encrypted_data
```

### Encryption

Security was a priority from the start. All mesh traffic is encrypted before transmission:

1. **Key Derivation:** A shared passphrase is run through PBKDF2 (100,000 iterations, SHA-256) to produce a master key, then HKDF derives separate encryption and HMAC keys
2. **Encryption:** AES-256-CBC with a random 16-byte IV per message
3. **Authentication:** HMAC-SHA256 over the ciphertext prevents tampering
4. **Per-Channel Keys:** Channels derive independent encryption keys from their own passphrases (50,000 PBKDF2 iterations), so different groups on the same mesh stay private
5. **Anonymity:** Node addresses are randomized on every startup -- no persistent identity tied to hardware

The same encryption runs on both desktop Python (PyCryptodome) and MicroPython on the Heltec V3.1 (ucryptolib + hand-rolled PBKDF2/HKDF). Getting identical ciphertext output across both platforms was one of the harder parts of this project.

### RYLR999 Reverse Engineering

The RYLR999 is a LoRa module with proprietary firmware that speaks AT commands (`AT+SEND`, `AT+ADDRESS`, etc.). It handles its own packet framing internally, which means you can't just flash custom firmware onto it like you can with a raw SX1262. To make it interoperate with the Heltec V3.1's SX1262 radio, I had to:

- Capture the RYLR999's RF output using an SDR to understand the actual on-air frame format
- Match LoRa modulation parameters (spreading factor, bandwidth, coding rate, sync word) between both radios
- Reverse-engineer the RYLR999's internal framing: `[Dest:2 LE][Src:2 LE][Len:1][Payload]`
- Build a compatible binary frame format that the Heltec firmware can construct and the RYLR999 will accept (and vice versa)
- Align the network ID / sync word so both devices see each other's transmissions

## Components

### RYLR999 Base Station (root directory)

A Python FastAPI server with an embedded web UI for sending and receiving encrypted mesh messages through a serial-connected RYLR999 module. The entire frontend (HTML, CSS, JavaScript) is served from a single `app.py` file -- no build tools, no npm, no framework. Plug in a RYLR999, run the script, open a browser.

| File | Purpose |
|------|---------|
| `app.py` | Web server, WebSocket handler, mesh router, embedded UI (~2100 lines) |
| `rylr999.py` | RYLR999 AT command serial driver |
| `crypto.py` | AES-256-CBC + HMAC-SHA256 encryption with PBKDF2/HKDF key derivation |
| `packet.py` | Binary packet structure and serialization (9-byte header) |
| `storage.py` | In-memory message, channel, and DM storage |
| `launcher_gui.py` | Tkinter GUI launcher for users who prefer not to use the command line |
| `radio_test.py` | Two-terminal radio test utility |

### Heltec V3.1 Firmware (`heltec_v3.1/`)

MicroPython firmware for the Heltec WiFi LoRa 32 V3.1. These are the portable mesh nodes -- battery-powered, carried on person, controlled from a phone over BLE. The firmware includes:

- **SX1262 LoRa driver** (`sx1262.py`, `sx126x.py`) -- direct hardware SPI control of the radio
- **Mesh routing** (`mesh_node.py`) -- same flood routing and seen-cache as the desktop app
- **MicroPython crypto** (`mesh_crypto.py`) -- PBKDF2, HKDF, AES-256-CBC, HMAC-SHA256 ported to run on an ESP32
- **BLE interface** (`ble_handler.py`, `ble_uart.py`) -- Nordic UART Service for phone connectivity
- **Persistent config** (`config.py`) -- frequency, address, passphrase, node name stored in flash

Upload all `.py` files to the Heltec using `mpremote` (see `upload.bat`).

### Android App (`android/`)

A Jetpack Compose companion app that connects to a Heltec V3.1 node over BLE. Provides a native mobile interface for channels, direct messages, device scanning, and settings. Built with:

- Kotlin + Jetpack Compose + Material Design 3
- Native Android BLE (no third-party library)
- Room database for local message persistence
- Dark and light theme support

A pre-built release APK is available at `android/app/release/app-release.apk`.

See [android/ARCHITECTURE.md](android/ARCHITECTURE.md) for detailed architecture documentation.

## Quick Start

### Requirements

- Python 3.9+
- RYLR999 LoRa module connected via USB-to-serial adapter
- Serial port access (add your user to the `dialout` group on Linux)

### Installation

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# For the GUI launcher, also install tkinter:
# Debian/Ubuntu: sudo apt install python3-tk
```

### Running

```bash
# Command line
python3 app.py /dev/ttyUSB0 your_passphrase

# With custom web port
python3 app.py /dev/ttyUSB0 your_passphrase 8080

# With HTTPS
python3 app.py /dev/ttyUSB0 your_passphrase 8080 --https

# GUI launcher
python3 launcher_gui.py
```

Then open `http://localhost:8000` in your browser.

### Heltec V3.1 Setup

1. Flash MicroPython onto the Heltec V3.1
2. Upload all `.py` files from `heltec_v3.1/` using `mpremote`:
   ```bash
   mpremote connect /dev/ttyUSB0 cp heltec_v3.1/*.py :
   mpremote connect /dev/ttyUSB0 reset
   ```
3. The node will start and begin listening for BLE connections and LoRa traffic

### Android Setup

Install `android/app/release/app-release.apk` on your phone. Open the app, scan for BLE devices with the "HSQ-" prefix, connect, and start messaging.

## HTTPS / Self-Signed Certificates

HeronSquawk can serve the web UI over HTTPS. Pass `--https` and the app will auto-generate `cert.pem` and `key.pem` if they don't exist (requires the `cryptography` Python package).

To generate certificates manually:

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes \
  -subj "/CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

Your browser will show a security warning for self-signed certificates -- click "Advanced" and "Proceed" to continue.

## Messaging Features

- **Channels:** Group messaging with per-channel passphrases for access control
- **Direct Messages:** Private 1-to-1 communication between any two nodes
- **Broadcast:** Send to all nodes on the mesh
- **Node Discovery:** Automatic detection and announcement of active nodes
- **Multi-Hop Routing:** Messages relay through intermediate nodes (configurable TTL, default 5 hops)
- **Chunk Reassembly:** Large messages are automatically split and reassembled

## Debian Installation

See [INSTALL_LINUX.md](INSTALL_LINUX.md) and [DEBIAN_INSTALL.md](DEBIAN_INSTALL.md) for detailed installation instructions including systemd service setup, PyInstaller builds, and desktop launcher integration.

## Current Status

This is a working project, not a polished product. The core functionality -- encrypted mesh messaging across RYLR999 and Heltec V3.1 hardware -- is tested and functional. The web UI is the most reliable interface. The Android app works but the initial mesh formation is slower on the Heltec hardware due to the time it takes to derive encryption keys on an ESP32. There are likely still some edge-case bugs. Contributions and bug reports are welcome.

## License

This project is licensed under the [MIT License](LICENSE).
