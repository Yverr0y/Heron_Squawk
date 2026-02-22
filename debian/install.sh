#!/bin/bash
# Heron Squawk - Debian 13 (Trixie) Installer
# Run with: chmod +x install.sh && ./install.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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

echo "[1/6] Installing system dependencies..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-tk

echo ""
echo "[2/6] Adding user to dialout group for serial port access..."
if groups $USER | grep -q dialout; then
    echo "User already in dialout group."
else
    sudo usermod -a -G dialout $USER
    echo "Added $USER to dialout group."
    NEED_RELOGIN=1
fi

echo ""
echo "[3/6] Creating Python virtual environment..."
cd "$SCRIPT_DIR"
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

echo ""
echo "[4/6] Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip
pip install fastapi "uvicorn[standard]" pyserial pycryptodome cryptography

echo ""
echo "[5/6] Creating run script..."
cat > "$SCRIPT_DIR/run.sh" << 'RUNEOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 launcher_gui.py
RUNEOF
chmod +x "$SCRIPT_DIR/run.sh"

echo ""
echo "[6/6] Setting up desktop launcher..."
# Update desktop file with correct path
sed -i "s|Exec=.*|Exec=$SCRIPT_DIR/run.sh|" "$SCRIPT_DIR/heronsquawk.desktop"

# Copy to user applications
mkdir -p ~/.local/share/applications
cp "$SCRIPT_DIR/heronsquawk.desktop" ~/.local/share/applications/

# Update desktop database
if command -v update-desktop-database &> /dev/null; then
    update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
fi

echo ""
echo "======================================"
echo "  INSTALLATION COMPLETE"
echo "======================================"
echo ""
echo "You can now run Heron Squawk in 3 ways:"
echo ""
echo "1. From application menu:"
echo "   Search for 'Heron Squawk' in your applications"
echo ""
echo "2. Double-click run.sh in the folder"
echo ""
echo "3. Command line:"
echo "   cd $SCRIPT_DIR"
echo "   source venv/bin/activate"
echo "   python3 app.py /dev/ttyUSB0 yourpassphrase"
echo ""
echo "======================================"

if [ "$NEED_RELOGIN" = "1" ]; then
    echo ""
    echo "IMPORTANT: Log out and back in for serial port access!"
fi