# Heron Squawk - Debian 13 Installation Guide

Complete installation guide for running Heron Squawk on Debian 13.

---

## Prerequisites

### 1. Update System
```bash
sudo apt update
sudo apt upgrade -y
```

### 2. Install Required Packages
```bash
sudo apt install -y python3 python3-pip python3-tk python3-venv git
```

### 3. Install Python Dependencies
```bash
pip3 install --user pyserial fastapi uvicorn websockets pycryptodome pyinstaller
```

---

## Installation Methods

### Method 1: GUI Application Launcher (Recommended)

This creates a clickable application that appears in your application menu.

#### Step 1: Build the Executable
```bash
chmod +x build_linux.sh
./build_linux.sh
```

#### Step 2: Install System-Wide
```bash
sudo cp dist/HeronSquawk /usr/local/bin/
sudo cp HeronSquawk.desktop /usr/share/applications/
sudo chmod +x /usr/local/bin/HeronSquawk
```

#### Step 3: Launch
- Open your application menu (GNOME Activities, KDE Menu, etc.)
- Search for "Heron Squawk"
- Click to launch the GUI

**Alternative: User-Level Installation (No sudo)**
```bash
mkdir -p ~/.local/bin ~/.local/share/applications
cp dist/HeronSquawk ~/.local/bin/
chmod +x ~/.local/bin/HeronSquawk
cp HeronSquawk.desktop ~/.local/share/applications/
sed -i 's|/usr/local/bin/HeronSquawk|'$HOME'/.local/bin/HeronSquawk|' ~/.local/share/applications/HeronSquawk.desktop
update-desktop-database ~/.local/share/applications/
```

---

### Method 2: Command Line Launch Scripts

#### Option A: GUI Launcher (Python)
```bash
python3 launcher_gui.py
```

#### Option B: Shell Script
```bash
chmod +x launch.sh
./launch.sh
```

---

### Method 3: Direct Command Line

Run the web UI directly:
```bash
python3 app.py <COM_PORT> <ADDRESS> <PASSPHRASE> [WEB_PORT]
```

**Example:**
```bash
python3 app.py /dev/ttyUSB0 1 mysecretkey 8000
```

Then open browser to: `http://localhost:8000`

---

## Hardware Setup

### 1. Connect LoRa Module

Connect your RYLR999 LoRa module to your Debian system via USB-to-Serial adapter.

### 2. Find Serial Port

```bash
# List USB serial devices
ls /dev/ttyUSB*
# or
ls /dev/ttyACM*

# Check device info
dmesg | grep tty
```

Common port names:
- `/dev/ttyUSB0`
- `/dev/ttyACM0`
- `/dev/serial/by-id/...`

### 3. Grant Serial Port Permissions

**Temporary (current session only):**
```bash
sudo chmod 666 /dev/ttyUSB0
```

**Permanent (recommended):**
```bash
# Add your user to dialout group
sudo usermod -a -G dialout $USER

# Log out and log back in for changes to take effect
```

Verify membership:
```bash
groups
```

You should see `dialout` in the list.

---

## Configuration

### First Launch Settings

When launching Heron Squawk for the first time, you'll need:

1. **COM Port**: Your serial port (e.g., `/dev/ttyUSB0`)
2. **Node Address**: Unique number 0-65535 (e.g., `1`)
3. **Mesh Passphrase**: Secret encryption key (same across all your nodes)
4. **Web Port**: HTTP port for web interface (default: `8000`)

**Security Note:** The passphrase is used for AES-256 encryption. Keep it secret and use the same passphrase on all nodes that should communicate.

---

## Running on System Startup (Optional)

### Create Systemd Service

1. **Create service file:**
```bash
sudo nano /etc/systemd/system/heronsquawk.service
```

2. **Add this content:**
```ini
[Unit]
Description=Heron Squawk LoRa Mesh Network
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/heronsquawk
ExecStart=/usr/bin/python3 /path/to/heronsquawk/app.py /dev/ttyUSB0 1 YOUR_PASSPHRASE 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. **Update the file:**
   - Replace `YOUR_USERNAME` with your username
   - Replace `/path/to/heronsquawk` with actual path
   - Update COM port, address, and passphrase as needed

4. **Enable and start:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable heronsquawk.service
sudo systemctl start heronsquawk.service
```

5. **Check status:**
```bash
sudo systemctl status heronsquawk.service
```

6. **View logs:**
```bash
sudo journalctl -u heronsquawk.service -f
```

---

## Troubleshooting

### Issue: "Permission denied" on serial port

**Solution:**
```bash
sudo usermod -a -G dialout $USER
```
Then log out and back in.

### Issue: "Module not found" errors

**Solution:**
```bash
pip3 install --user pyserial fastapi uvicorn websockets pycryptodome
```

### Issue: Can't find the application in menu

**Solution:**
```bash
# Refresh desktop database
update-desktop-database ~/.local/share/applications/
# or
sudo update-desktop-database /usr/share/applications/
```

### Issue: LoRa module not responding

**Check connection:**
```bash
python3 rylr999.py /dev/ttyUSB0
```

This will test the connection and display module info.

### Issue: Web UI won't open

**Check if port is already in use:**
```bash
sudo netstat -tulpn | grep :8000
```

Try a different port:
```bash
python3 app.py /dev/ttyUSB0 1 mysecretkey 8001
```

---

## Uninstalling

### Remove Application Launcher
```bash
# System-wide
sudo rm /usr/local/bin/HeronSquawk
sudo rm /usr/share/applications/HeronSquawk.desktop

# User-level
rm ~/.local/bin/HeronSquawk
rm ~/.local/share/applications/HeronSquawk.desktop
```

### Remove Systemd Service
```bash
sudo systemctl stop heronsquawk.service
sudo systemctl disable heronsquawk.service
sudo rm /etc/systemd/system/heronsquawk.service
sudo systemctl daemon-reload
```

### Remove Python Packages
```bash
pip3 uninstall -y pyserial fastapi uvicorn websockets pycryptodome pyinstaller
```

---

## Network Configuration

### Firewall Setup (if needed)

If you want to access the web UI from other devices on your network:

```bash
# UFW (Uncomplicated Firewall)
sudo ufw allow 8000/tcp

# iptables
sudo iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

### Access from Other Devices

Find your Debian machine's IP:
```bash
ip addr show
```

Then access from another device:
```
http://YOUR_DEBIAN_IP:8000
```

---

## Performance Tips

### 1. Reduce Latency
Run with higher priority:
```bash
sudo nice -n -10 python3 app.py /dev/ttyUSB0 1 mysecretkey 8000
```

### 2. Monitor Resources
```bash
# CPU and memory usage
htop

# Serial port activity
sudo cat /dev/ttyUSB0
```

---

## Additional Resources

- **Project Files:**
  - `app.py` - Main application
  - `rylr999.py` - LoRa radio driver
  - `crypto.py` - Encryption module
  - `packet.py` - Packet structure
  - `storage.py` - Data persistence

- **Test LoRa Module:**
  ```bash
  python3 rylr999.py /dev/ttyUSB0
  ```

- **Check Python Version:**
  ```bash
  python3 --version
  ```
  (Python 3.9+ recommended)

---

## Support

For issues, questions, or contributions, refer to the project documentation or open an issue on the project repository.

---

**Heron Squawk** - Secure LoRa Mesh Networking for Debian 13
