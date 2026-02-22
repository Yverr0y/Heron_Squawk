#!/bin/bash
# Heron Squawk - Debian 13 (Trixie) Installer
# Run with: chmod +x install.sh && ./install.sh

set -e

echo "======================================"
echo "  HERON SQUAWK INSTALLER"
echo "  Debian 13 (Trixie)"
echo "======================================"
echo ""

# Check if running as root
if [ "$EUID" -eq 0 ]; then
    echo "Please run this script as a regular user (not root)."
    echo "The script will ask for sudo when needed."
    exit 1
fi

# Check for Debian
if [ ! -f /etc/debian_version ]; then
    echo "Warning: This script is designed for Debian-based systems."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "[1/5] Installing system dependencies..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-tk

echo ""
echo "[2/5] Adding user to dialout group for serial port access..."
if groups $USER | grep -q dialout; then
    echo "User already in dialout group."
else
    sudo usermod -a -G dialout $USER
    echo "Added $USER to dialout group."
    echo "NOTE: You may need to log out and back in for this to take effect."
fi

echo ""
echo "[3/5] Creating Python virtual environment..."
cd "$(dirname "$0")"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

echo ""
echo "[4/5] Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pyserial pycryptodome cryptography

echo ""
echo "[5/5] Installation complete!"
echo ""
echo "======================================"
echo "  USAGE"
echo "======================================"
echo ""
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Find your serial port:"
echo "   ls /dev/ttyUSB* /dev/ttyACM*"
echo ""
echo "3. Run the application:"
echo "   python3 app.py /dev/ttyUSB0 yourpassphrase"
echo ""
echo "   With custom port:"
echo "   python3 app.py /dev/ttyUSB0 yourpassphrase 8080"
echo ""
echo "   With HTTPS:"
echo "   python3 app.py /dev/ttyUSB0 yourpassphrase 8080 --https"
echo ""
echo "4. Or use the GUI launcher:"
echo "   python3 launcher_gui.py"
echo ""
echo "======================================"
echo ""

# Check if reboot/relogin needed for dialout
if ! groups | grep -q dialout; then
    echo "IMPORTANT: Log out and back in for serial port access!"
fi
