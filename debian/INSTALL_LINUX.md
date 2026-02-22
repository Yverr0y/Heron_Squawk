# Heron Squawk - Debian 13 Installation Guide

## Quick Install (Recommended)

Run the automated installer:

```bash
chmod +x install.sh
./install.sh
```

This will:
- Install system dependencies (python3, pip, tk, venv)
- Add your user to the `dialout` group for serial port access
- Create a Python virtual environment
- Install all required Python packages

---

## Manual Installation

### Step 1: System Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-tk
```

### Step 2: Serial Port Access

Add your user to the `dialout` group to access USB serial devices:

```bash
sudo usermod -a -G dialout $USER
```

**Important:** Log out and back in for this to take effect.

### Step 3: Python Virtual Environment

```bash
cd /path/to/heronsquawk
python3 -m venv venv
source venv/bin/activate
```

### Step 4: Install Python Packages

```bash
pip install fastapi uvicorn pyserial pycryptodome cryptography
```

---

## Running Heron Squawk

### Activate Virtual Environment First

```bash
cd /path/to/heronsquawk
source venv/bin/activate
```

### Find Your Serial Port

```bash
ls /dev/ttyUSB* /dev/ttyACM*
```

Common ports:
- `/dev/ttyUSB0` - Most USB serial adapters
- `/dev/ttyACM0` - Some Arduino/CDC devices

### Command Line

```bash
# Basic usage
python3 app.py /dev/ttyUSB0 yourpassphrase

# Custom web port
python3 app.py /dev/ttyUSB0 yourpassphrase 8080

# With HTTPS
python3 app.py /dev/ttyUSB0 yourpassphrase 8080 --https
```

### GUI Launcher

```bash
python3 launcher_gui.py
```

---

## Troubleshooting

### Permission Denied on Serial Port

```
serial.serialutil.SerialException: [Errno 13] could not open port /dev/ttyUSB0
```

**Fix:** Make sure you're in the `dialout` group and have logged out/in:

```bash
groups  # Should show 'dialout'
```

If not showing, run `sudo usermod -a -G dialout $USER` and log out/in.

### Module Not Found Errors

Make sure you've activated the virtual environment:

```bash
source venv/bin/activate
```

### Tkinter Not Found (GUI Launcher)

```bash
sudo apt install python3-tk
```

---

## Uninstall

Simply delete the `heronsquawk` folder. No system files are modified.

```bash
rm -rf /path/to/heronsquawk
```
