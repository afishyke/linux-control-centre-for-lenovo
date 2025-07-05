#!/bin/bash

# Lenovo Control Center Launcher
echo "Starting Lenovo Control Center..."

# Change to the correct directory
cd "$(dirname "$0")"

# Check if DISPLAY is set (for GUI)
if [ -z "$DISPLAY" ]; then
    echo "Warning: DISPLAY not set. GUI may not work properly."
    export DISPLAY=:0
fi

# Check dependencies
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is required but not installed."
    exit 1
fi

if ! python3 -c "import psutil" &> /dev/null; then
    echo "Installing required dependencies..."
    pip3 install psutil
fi

# Launch the application
echo "Launching Lenovo Control Center..."
python3 main_tkinter.py

echo "Lenovo Control Center closed."