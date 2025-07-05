# Lenovo Control Center for Linux

A comprehensive system control and monitoring application for Lenovo laptops running Linux, with a modern and intuitive UI built with PyQt6.

![Screenshot](https://freeimage.host/i/FlA0MZP)  <!-- Replace with a real screenshot -->

## Features

- **Modern UI**: A sleek, dark-themed interface built with PyQt6 for a great user experience.
- **System Monitoring**: Real-time monitoring of:
    - CPU usage (overall and per-core)
    - Memory and swap usage
    - Disk space and I/O
    - System temperatures with color-coded warnings
    - Fan speeds (RPM)
- **Fan Control**:
    - Automatic and manual fan control modes.
    - Adjust fan speed with a slider (0-100%).
    - Safety warnings for low fan speeds.
- **Battery Management**:
    - Set charge start and stop thresholds to preserve battery health (on compatible ThinkPads).
    - View detailed battery information and status.
- **Power Control**:
    - Change CPU governor to balance performance and power consumption.
    - Adjust display brightness.
- **Cross-Platform**: While optimized for Lenovo laptops, it can run on other Linux systems with basic monitoring features.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/afishyke/linux-control-centre-for-lenovo.git
    cd linux-control-centre-for-lenovo
    ```

2.  **Run the launch script:**
    This script will automatically create a virtual environment and install the required dependencies.
    ```bash
    ./launch.sh
    ```

## Usage

After the initial setup, simply run the `launch.sh` script to start the application.

```bash
./launch.sh
```

## Requirements

- Python 3.6+
- PyQt6
- psutil
- `lm-sensors` (optional, for enhanced fan and temperature detection)

## Permissions

Certain features require root access to control hardware settings. The application uses `pkexec` to securely request elevated privileges for the following actions:

- Setting battery charge thresholds
- Changing the CPU governor
- Adjusting hardware display brightness
- Controlling fan speeds

You will be prompted for your password when these actions are performed.

## Compatibility

- **Full Feature Support**: Lenovo ThinkPad series laptops are expected to have the best compatibility and support for all features, including battery thresholds and fan control.
- **Partial Support**: Other Lenovo laptops and systems with standard `hwmon` interfaces should support most monitoring and control features.
- **Basic Support**: On generic Linux systems, the application will provide basic system monitoring.

## Contributing

Contributions, issues, and feature requests are welcome! Please feel free to open an issue or submit a pull request.
