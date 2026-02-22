#!/bin/bash
# Build script for Linux executable

echo "Building Heron Squawk for Linux..."

# Install PyInstaller if not already installed
pip3 install pyinstaller

# Build the executable
pyinstaller --onefile \
    --windowed \
    --name HeronSquawk \
    launcher_gui.py

echo ""
echo "Build complete! Executable is in dist/HeronSquawk"
echo ""
echo "To install system-wide:"
echo "  sudo cp dist/HeronSquawk /usr/local/bin/"
echo "  sudo cp HeronSquawk.desktop /usr/share/applications/"
echo "  sudo chmod +x /usr/local/bin/HeronSquawk"
echo ""
echo "Then you can launch from your application menu!"
