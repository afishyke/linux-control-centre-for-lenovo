# Lenovo Control Center for Linux

A comprehensive system control and monitoring application for Lenovo laptops running Linux.

## Features

- **System Monitoring**: Real-time CPU, memory, disk, and temperature monitoring
- **Battery Management**: Set charge thresholds to preserve battery health
- **Power Control**: Change CPU governor for performance/power balance
- **Display Control**: Adjust screen brightness
- **Dark Theme**: Lenovo-inspired red and black color scheme

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python main.py
```

## Features by Tab

### System Info
- Real-time CPU usage
- Memory usage monitoring
- Disk space monitoring
- Battery status
- Temperature readings

### Battery Control
- Set charge start/stop thresholds (ThinkPad compatible)
- View current battery information
- Preserve battery health with smart charging

### Power & Display
- CPU governor control (performance/powersave/ondemand)
- Display brightness control
- Power management settings

## Requirements

- Python 3.6+
- PyQt6
- psutil
- Linux with sysfs support
- Root access for hardware control features

## Permissions

Some features require root access:
- Battery charge thresholds
- CPU governor changes
- Brightness control

The app uses `pkexec` for secure privilege escalation.

## Compatibility

Tested on:
- ThinkPad series (full feature support)
- Other Lenovo laptops (basic features)
- Generic Linux systems (monitoring only)

## Contributing

Feel free to submit issues and enhancement requests!