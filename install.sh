#!/bin/bash

echo "Installing Lenovo Control Center..."

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed. Please install Python 3 first."
    exit 1
fi

# Check if pip is installed
if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null; then
    echo "Error: pip is not installed. Please install pip first."
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt

# Make the main script executable
chmod +x main.py

# Create desktop entry
DESKTOP_FILE="$HOME/.local/share/applications/lenovo-control-center.desktop"
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=Lenovo Control Center
Comment=System control and monitoring for Lenovo laptops
Exec=python3 $(pwd)/main.py
Icon=computer
Terminal=false
Type=Application
Categories=System;Settings;
EOF

echo "Desktop entry created at: $DESKTOP_FILE"

# Check for required system files
echo "Checking system compatibility..."

if [ -d "/sys/class/power_supply" ]; then
    echo "✓ Power supply interface found"
else
    echo "⚠ Power supply interface not found - battery features may not work"
fi

if [ -d "/sys/devices/system/cpu/cpu0/cpufreq" ]; then
    echo "✓ CPU frequency scaling found"
else
    echo "⚠ CPU frequency scaling not found - governor control may not work"
fi

if [ -d "/sys/class/backlight" ]; then
    echo "✓ Backlight control found"
else
    echo "⚠ Backlight control not found - brightness control may not work"
fi

echo ""
echo "Installation complete!"
echo "You can now run the application with: python3 main.py"
echo "Or find it in your applications menu as 'Lenovo Control Center'"