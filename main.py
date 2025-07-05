#!/usr/bin/env python3

import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout, 
                             QHBoxLayout, QWidget, QLabel, QProgressBar, QPushButton,
                             QSlider, QComboBox, QTextEdit, QGroupBox, QGridLayout,
                             QMessageBox, QSpinBox)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
import subprocess
import json
import psutil
import platform

class SystemInfoThread(QThread):
    data_updated = pyqtSignal(dict)
    
    def run(self):
        while True:
            try:
                system_info = {
                    'cpu_percent': psutil.cpu_percent(interval=1),
                    'memory': psutil.virtual_memory(),
                    'disk': psutil.disk_usage('/'),
                    'battery': psutil.sensors_battery(),
                    'temperatures': psutil.sensors_temperatures(),
                    'fans': psutil.sensors_fans()
                }
                self.data_updated.emit(system_info)
            except Exception as e:
                print(f"Error collecting system info: {e}")
            self.msleep(2000)

class SystemInfoWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_monitoring()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # System Overview
        overview_group = QGroupBox("System Overview")
        overview_layout = QGridLayout()
        
        # CPU Info
        self.cpu_label = QLabel(f"CPU: {platform.processor()}")
        self.cpu_usage = QProgressBar()
        self.cpu_usage.setMaximum(100)
        overview_layout.addWidget(QLabel("CPU Usage:"), 0, 0)
        overview_layout.addWidget(self.cpu_usage, 0, 1)
        
        # Memory Info
        self.memory_usage = QProgressBar()
        self.memory_usage.setMaximum(100)
        overview_layout.addWidget(QLabel("Memory Usage:"), 1, 0)
        overview_layout.addWidget(self.memory_usage, 1, 1)
        
        # Disk Info
        self.disk_usage = QProgressBar()
        self.disk_usage.setMaximum(100)
        overview_layout.addWidget(QLabel("Disk Usage:"), 2, 0)
        overview_layout.addWidget(self.disk_usage, 2, 1)
        
        # Battery Info
        self.battery_label = QLabel("Battery: N/A")
        overview_layout.addWidget(self.battery_label, 3, 0, 1, 2)
        
        overview_group.setLayout(overview_layout)
        layout.addWidget(overview_group)
        
        # Temperature Info
        temp_group = QGroupBox("Temperatures")
        self.temp_text = QTextEdit()
        self.temp_text.setMaximumHeight(100)
        temp_group.setLayout(QVBoxLayout())
        temp_group.layout().addWidget(self.temp_text)
        layout.addWidget(temp_group)
        
        self.setLayout(layout)
    
    def init_monitoring(self):
        self.monitor_thread = SystemInfoThread()
        self.monitor_thread.data_updated.connect(self.update_system_info)
        self.monitor_thread.start()
    
    def update_system_info(self, data):
        # Update CPU
        self.cpu_usage.setValue(int(data['cpu_percent']))
        
        # Update Memory
        memory = data['memory']
        memory_percent = (memory.used / memory.total) * 100
        self.memory_usage.setValue(int(memory_percent))
        
        # Update Disk
        disk = data['disk']
        disk_percent = (disk.used / disk.total) * 100
        self.disk_usage.setValue(int(disk_percent))
        
        # Update Battery
        battery = data['battery']
        if battery:
            status = "Charging" if battery.power_plugged else "Discharging"
            self.battery_label.setText(f"Battery: {battery.percent}% ({status})")
        else:
            self.battery_label.setText("Battery: N/A")
        
        # Update Temperatures
        temps = data['temperatures']
        temp_text = ""
        for name, entries in temps.items():
            for entry in entries:
                temp_text += f"{name}: {entry.current}°C\n"
        self.temp_text.setText(temp_text)

class BatteryControlWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Battery Threshold Control
        threshold_group = QGroupBox("Battery Charge Thresholds")
        threshold_layout = QGridLayout()
        
        # Start threshold
        threshold_layout.addWidget(QLabel("Start Charging At:"), 0, 0)
        self.start_threshold = QSpinBox()
        self.start_threshold.setRange(40, 80)
        self.start_threshold.setValue(60)
        self.start_threshold.setSuffix("%")
        threshold_layout.addWidget(self.start_threshold, 0, 1)
        
        # Stop threshold
        threshold_layout.addWidget(QLabel("Stop Charging At:"), 1, 0)
        self.stop_threshold = QSpinBox()
        self.stop_threshold.setRange(60, 100)
        self.stop_threshold.setValue(80)
        self.stop_threshold.setSuffix("%")
        threshold_layout.addWidget(self.stop_threshold, 1, 1)
        
        # Apply button
        apply_btn = QPushButton("Apply Thresholds")
        apply_btn.clicked.connect(self.apply_battery_thresholds)
        threshold_layout.addWidget(apply_btn, 2, 0, 1, 2)
        
        threshold_group.setLayout(threshold_layout)
        layout.addWidget(threshold_group)
        
        # Battery Info
        info_group = QGroupBox("Battery Information")
        info_layout = QVBoxLayout()
        
        self.battery_info = QTextEdit()
        self.battery_info.setMaximumHeight(150)
        self.update_battery_info()
        
        info_layout.addWidget(self.battery_info)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        self.setLayout(layout)
    
    def apply_battery_thresholds(self):
        try:
            start_val = self.start_threshold.value()
            stop_val = self.stop_threshold.value()
            
            if start_val >= stop_val:
                QMessageBox.warning(self, "Invalid Range", 
                                  "Start threshold must be less than stop threshold!")
                return
            
            # Apply thresholds (requires root access)
            start_cmd = f"echo {start_val} | pkexec tee /sys/class/power_supply/BAT0/charge_start_threshold"
            stop_cmd = f"echo {stop_val} | pkexec tee /sys/class/power_supply/BAT0/charge_stop_threshold"
            
            subprocess.run(start_cmd, shell=True, check=True)
            subprocess.run(stop_cmd, shell=True, check=True)
            
            QMessageBox.information(self, "Success", 
                                  f"Battery thresholds set: {start_val}% - {stop_val}%")
            
        except subprocess.CalledProcessError:
            QMessageBox.critical(self, "Error", 
                               "Failed to apply battery thresholds. Make sure you have proper permissions.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error: {str(e)}")
    
    def update_battery_info(self):
        try:
            # Get battery information
            battery = psutil.sensors_battery()
            info_text = ""
            
            if battery:
                info_text += f"Battery Percentage: {battery.percent}%\n"
                info_text += f"Power Plugged: {'Yes' if battery.power_plugged else 'No'}\n"
                if battery.secsleft != psutil.POWER_TIME_UNLIMITED:
                    hours, remainder = divmod(battery.secsleft, 3600)
                    minutes, _ = divmod(remainder, 60)
                    info_text += f"Time Remaining: {hours:02d}:{minutes:02d}\n"
            
            # Try to get current thresholds
            try:
                with open('/sys/class/power_supply/BAT0/charge_start_threshold', 'r') as f:
                    start = f.read().strip()
                    info_text += f"Current Start Threshold: {start}%\n"
            except:
                info_text += "Current Start Threshold: N/A\n"
            
            try:
                with open('/sys/class/power_supply/BAT0/charge_stop_threshold', 'r') as f:
                    stop = f.read().strip()
                    info_text += f"Current Stop Threshold: {stop}%\n"
            except:
                info_text += "Current Stop Threshold: N/A\n"
            
            self.battery_info.setText(info_text)
            
        except Exception as e:
            self.battery_info.setText(f"Error reading battery info: {str(e)}")

class PowerControlWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # CPU Governor Control
        governor_group = QGroupBox("CPU Governor")
        governor_layout = QGridLayout()
        
        governor_layout.addWidget(QLabel("Current Governor:"), 0, 0)
        self.current_governor = QLabel("Loading...")
        governor_layout.addWidget(self.current_governor, 0, 1)
        
        governor_layout.addWidget(QLabel("Set Governor:"), 1, 0)
        self.governor_combo = QComboBox()
        self.load_available_governors()
        governor_layout.addWidget(self.governor_combo, 1, 1)
        
        apply_governor_btn = QPushButton("Apply")
        apply_governor_btn.clicked.connect(self.apply_cpu_governor)
        governor_layout.addWidget(apply_governor_btn, 2, 0, 1, 2)
        
        governor_group.setLayout(governor_layout)
        layout.addWidget(governor_group)
        
        # Brightness Control
        brightness_group = QGroupBox("Display Brightness")
        brightness_layout = QVBoxLayout()
        
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(1)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(50)
        self.brightness_slider.valueChanged.connect(self.change_brightness)
        
        brightness_layout.addWidget(QLabel("Brightness:"))
        brightness_layout.addWidget(self.brightness_slider)
        
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)
        
        self.setLayout(layout)
        self.update_current_governor()
    
    def load_available_governors(self):
        try:
            with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors', 'r') as f:
                governors = f.read().strip().split()
                self.governor_combo.addItems(governors)
        except:
            self.governor_combo.addItems(['performance', 'powersave', 'ondemand', 'conservative'])
    
    def update_current_governor(self):
        try:
            with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor', 'r') as f:
                current = f.read().strip()
                self.current_governor.setText(current)
        except:
            self.current_governor.setText("N/A")
    
    def apply_cpu_governor(self):
        try:
            governor = self.governor_combo.currentText()
            cmd = f"echo {governor} | pkexec tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"
            subprocess.run(cmd, shell=True, check=True)
            self.update_current_governor()
            QMessageBox.information(self, "Success", f"CPU governor set to: {governor}")
        except subprocess.CalledProcessError:
            QMessageBox.critical(self, "Error", "Failed to set CPU governor. Check permissions.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error: {str(e)}")
    
    def change_brightness(self, value):
        try:
            # Try different brightness control methods
            brightness_paths = [
                '/sys/class/backlight/intel_backlight/brightness',
                '/sys/class/backlight/acpi_video0/brightness',
                '/sys/class/backlight/amdgpu_bl0/brightness'
            ]
            
            for path in brightness_paths:
                if os.path.exists(path):
                    max_brightness_path = path.replace('brightness', 'max_brightness')
                    try:
                        with open(max_brightness_path, 'r') as f:
                            max_brightness = int(f.read().strip())
                        
                        new_brightness = int((value / 100) * max_brightness)
                        cmd = f"echo {new_brightness} | pkexec tee {path}"
                        subprocess.run(cmd, shell=True, check=True)
                        break
                    except:
                        continue
            else:
                # Fallback to xrandr
                cmd = f"xrandr --output eDP-1 --brightness {value/100}"
                subprocess.run(cmd, shell=True)
                
        except Exception as e:
            print(f"Error changing brightness: {e}")

class LenovoControlCenter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Lenovo Control Center")
        self.setGeometry(100, 100, 800, 600)
        
        # Create central widget and tab widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout()
        central_widget.setLayout(layout)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Add tabs
        self.tab_widget.addTab(SystemInfoWidget(), "System Info")
        self.tab_widget.addTab(BatteryControlWidget(), "Battery")
        self.tab_widget.addTab(PowerControlWidget(), "Power & Display")
        
        layout.addWidget(self.tab_widget)
        
        # Set dark theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
                background-color: #2b2b2b;
            }
            QTabBar::tab {
                background-color: #3c3c3c;
                color: #ffffff;
                padding: 8px 16px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #e74c3c;
                color: #ffffff;
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #555555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: #ffffff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #e74c3c;
                color: #ffffff;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
            QProgressBar {
                border: 1px solid #555555;
                border-radius: 5px;
                text-align: center;
                color: #ffffff;
            }
            QProgressBar::chunk {
                background-color: #e74c3c;
                border-radius: 5px;
            }
        """)

def main():
    app = QApplication(sys.argv)
    
    # Check for required dependencies
    try:
        import psutil
    except ImportError:
        print("Error: psutil is required. Install with: pip install psutil")
        sys.exit(1)
    
    window = LenovoControlCenter()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()