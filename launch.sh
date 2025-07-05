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

# Check if virtual environment exists
if [ ! -d "lenovo-venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv lenovo-venv
    echo "Installing dependencies..."
    source lenovo-venv/bin/activate
    pip install PyQt6 psutil
    deactivate
fi

# Activate virtual environment and launch
echo "Launching Lenovo Control Center..."
source lenovo-venv/bin/activate
python main.py
deactivate

echo "Lenovo Control Center closed."