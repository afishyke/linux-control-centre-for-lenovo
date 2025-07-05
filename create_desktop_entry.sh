#!/bin/bash

# Create desktop entry for Lenovo Control Center
echo "Creating desktop entry for Lenovo Control Center..."

# Get the current directory (where the app is located)
APP_DIR="$(cd "$(dirname "$0")" && pwd)"

# Create the desktop entry
DESKTOP_FILE="$HOME/.local/share/applications/lenovo-control-center.desktop"
mkdir -p "$HOME/.local/share/applications"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Lenovo Control Center
Comment=System control and monitoring for Lenovo laptops
Exec=$APP_DIR/launch.sh
Icon=$APP_DIR/lenovo-control-center.svg
Terminal=false
Categories=System;Settings;HardwareSettings;
Keywords=lenovo;system;monitor;battery;cpu;power;
StartupNotify=true
MimeType=
EOF

# Make the desktop file executable
chmod +x "$DESKTOP_FILE"

echo "Desktop entry created successfully!"
echo "Location: $DESKTOP_FILE"
echo ""
echo "You can now:"
echo "1. Find 'Lenovo Control Center' in your applications menu"
echo "2. Pin it to your taskbar/favorites"
echo "3. Launch it from the desktop"
echo ""

# Optional: Create a desktop shortcut
read -p "Do you want to create a desktop shortcut? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    DESKTOP_SHORTCUT="$HOME/Desktop/lenovo-control-center.desktop"
    cp "$DESKTOP_FILE" "$DESKTOP_SHORTCUT"
    chmod +x "$DESKTOP_SHORTCUT"
    echo "Desktop shortcut created: $DESKTOP_SHORTCUT"
fi

echo "Setup complete!"