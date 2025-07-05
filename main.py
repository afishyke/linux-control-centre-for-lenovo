#!/usr/bin/env python3

import sys
import os
import glob
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QVBoxLayout, 
                             QHBoxLayout, QWidget, QLabel, QProgressBar, QPushButton,
                             QSlider, QComboBox, QTextEdit, QGroupBox, QGridLayout,
                             QMessageBox, QSpinBox, QCheckBox)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon
import subprocess
import json
import psutil
import platform
import shutil

class GPUController:
    def __init__(self):
        self.gpu_info = {}
        self.detect_gpu()

    def detect_gpu(self):
        """Detect GPU and its properties"""
        if shutil.which('nvidia-smi'):
            self.gpu_info['vendor'] = 'NVIDIA'
            self.update_nvidia_info()
        elif os.path.exists('/sys/class/drm/card0/device/vendor') and \
             os.path.exists('/sys/class/drm/card0/device/power_dpm_force_performance_level'):
            self.gpu_info['vendor'] = 'AMD'
            self.update_amd_info()
        else:
            self.gpu_info['vendor'] = 'Intel' # or other
            self.update_intel_info()

    def update_nvidia_info(self):
        try:
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=name,temperature.gpu,utilization.gpu,memory.total,memory.used', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, check=True
            )
            values = result.stdout.strip().split(', ')
            self.gpu_info['name'] = values[0]
            self.gpu_info['temperature'] = int(values[1])
            self.gpu_info['usage'] = int(values[2])
            self.gpu_info['memory_total'] = int(values[3])
            self.gpu_info['memory_used'] = int(values[4])
        except (subprocess.CalledProcessError, FileNotFoundError, IndexError) as e:
            print(f"Could not get NVIDIA info: {e}")

    def update_amd_info(self):
        try:
            # Temperature
            with open('/sys/class/drm/card0/device/hwmon/hwmon*/temp1_input', 'r') as f:
                self.gpu_info['temperature'] = int(f.read().strip()) / 1000
            # Usage
            with open('/sys/class/drm/card0/device/gpu_busy_percent', 'r') as f:
                self.gpu_info['usage'] = int(f.read().strip())
            # Power DPM performance level
            with open('/sys/class/drm/card0/device/power_dpm_force_performance_level', 'r') as f:
                self.gpu_info['performance_level'] = f.read().strip()
        except (FileNotFoundError, IndexError) as e:
            print(f"Could not get AMD info: {e}")

    def update_intel_info(self):
        # Intel GPU info is harder to get, placeholder
        self.gpu_info['name'] = "Intel Integrated Graphics"
        self.gpu_info['temperature'] = "N/A"
        self.gpu_info['usage'] = "N/A"

    def get_gpu_info(self):
        if self.gpu_info.get('vendor') == 'NVIDIA':
            self.update_nvidia_info()
        elif self.gpu_info.get('vendor') == 'AMD':
            self.update_amd_info()
        return self.gpu_info

    def set_amd_performance_level(self, level):
        if self.gpu_info.get('vendor') != 'AMD':
            return False, "Not an AMD GPU"
        
        valid_levels = ['auto', 'low', 'high', 'manual']
        if level not in valid_levels:
            return False, f"Invalid performance level. Valid levels are: {valid_levels}"

        try:
            cmd = f"echo {level} | pkexec tee /sys/class/drm/card0/device/power_dpm_force_performance_level"
            subprocess.run(cmd, shell=True, check=True)
            return True, f"AMD performance level set to {level}"
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            return False, f"Failed to set AMD performance level: {e}"

class FanController:
    def __init__(self):
        self.fan_info = {}
        self.controllable_fans = {}
        self.pwm_paths = {}
        self.detect_fans()
        self.detect_controllable_fans()
    
    def detect_fans(self):
        """Detect all available fans using multiple methods"""
        fans = {}
        
        # Method 1: psutil sensors
        try:
            psutil_fans = psutil.sensors_fans()
            for name, fan_list in psutil_fans.items():
                for i, fan in enumerate(fan_list):
                    if fan.current > 0:
                        fans[f"{name}_{i}"] = {
                            'name': f"{name} Fan {i+1}",
                            'rpm': fan.current,
                            'source': 'psutil',
                            'path': None
                        }
        except Exception as e:
            print(f"psutil fan detection failed: {e}")
        
        # Method 2: /sys/class/hwmon
        try:
            hwmon_paths = glob.glob('/sys/class/hwmon/hwmon*')
            for hwmon_path in hwmon_paths:
                try:
                    # Check for fan inputs
                    fan_inputs = glob.glob(f"{hwmon_path}/fan*_input")
                    for fan_input in fan_inputs:
                        fan_num = re.search(r'fan(\d+)_input', fan_input).group(1)
                        try:
                            with open(fan_input, 'r') as f:
                                rpm = int(f.read().strip())
                            if rpm > 0:
                                # Get fan name if available
                                name_file = f"{hwmon_path}/name"
                                device_name = "Unknown"
                                if os.path.exists(name_file):
                                    with open(name_file, 'r') as f:
                                        device_name = f.read().strip()
                                
                                fan_key = f"{device_name}_fan{fan_num}"
                                fans[fan_key] = {
                                    'name': f"{device_name} Fan {fan_num}",
                                    'rpm': rpm,
                                    'source': 'hwmon',
                                    'path': fan_input
                                }
                        except (ValueError, IOError):
                            continue
                except Exception:
                    continue
        except Exception as e:
            print(f"hwmon fan detection failed: {e}")
        
        # Method 3: lm-sensors via subprocess
        try:
            result = subprocess.run(['sensors', '-A'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                current_device = None
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and not line.startswith(' ') and ':' not in line:
                        current_device = line
                    elif 'fan' in line.lower() and 'rpm' in line.lower():
                        try:
                            parts = line.split(':')
                            if len(parts) >= 2:
                                fan_name = parts[0].strip()
                                rpm_part = parts[1].strip()
                                rpm_match = re.search(r'(\d+)\s*RPM', rpm_part)
                                if rpm_match:
                                    rpm = int(rpm_match.group(1))
                                    if rpm > 0:
                                        fan_key = f"{current_device}_{fan_name}"
                                        fans[fan_key] = {
                                            'name': f"{current_device} {fan_name}",
                                            'rpm': rpm,
                                            'source': 'lm-sensors',
                                            'path': None
                                        }
                        except Exception:
                            continue
        except Exception as e:
            print(f"lm-sensors fan detection failed: {e}")
        
        self.fan_info = fans
        return fans
    
    def detect_controllable_fans(self):
        """Detect which fans can be controlled"""
        controllable = {}
        
        # Look for PWM controls in /sys/class/hwmon
        try:
            hwmon_paths = glob.glob('/sys/class/hwmon/hwmon*')
            for hwmon_path in hwmon_paths:
                try:
                    pwm_files = glob.glob(f"{hwmon_path}/pwm*")
                    for pwm_file in pwm_files:
                        if pwm_file.endswith('_enable') or pwm_file.endswith('_mode'):
                            continue
                        
                        pwm_num = re.search(r'pwm(\d+)$', pwm_file).group(1)
                        pwm_enable_file = f"{hwmon_path}/pwm{pwm_num}_enable"
                        
                        # Check if PWM is writable and enabled
                        if os.access(pwm_file, os.W_OK) or True:  # We'll use pkexec for writes
                            try:
                                with open(pwm_file, 'r') as f:
                                    current_pwm = int(f.read().strip())
                                
                                # Get device name
                                name_file = f"{hwmon_path}/name"
                                device_name = "Unknown"
                                if os.path.exists(name_file):
                                    with open(name_file, 'r') as f:
                                        device_name = f.read().strip()
                                
                                fan_key = f"{device_name}_pwm{pwm_num}"
                                controllable[fan_key] = {
                                    'name': f"{device_name} PWM {pwm_num}",
                                    'pwm_path': pwm_file,
                                    'pwm_enable_path': pwm_enable_file,
                                    'current_pwm': current_pwm,
                                    'max_pwm': 255
                                }
                                
                                # Store PWM paths for easy access
                                self.pwm_paths[fan_key] = pwm_file
                                
                            except (ValueError, IOError):
                                continue
                except Exception:
                    continue
        except Exception as e:
            print(f"PWM detection failed: {e}")
        
        self.controllable_fans = controllable
        return controllable
    
    def get_current_fan_speeds(self):
        """Get current fan speeds for all detected fans"""
        current_speeds = {}
        
        for fan_key, fan_info in self.fan_info.items():
            try:
                if fan_info['source'] == 'hwmon' and fan_info['path']:
                    with open(fan_info['path'], 'r') as f:
                        rpm = int(f.read().strip())
                        current_speeds[fan_key] = rpm
                else:
                    current_speeds[fan_key] = fan_info['rpm']
            except Exception:
                current_speeds[fan_key] = 0
        
        return current_speeds
    
    def set_fan_speed(self, fan_key, speed_percent):
        """Set fan speed (0-100%) with safety checks"""
        if fan_key not in self.controllable_fans:
            return False, "Fan not controllable"
        
        # Safety checks
        if not (0 <= speed_percent <= 100):
            return False, "Speed must be between 0-100%"
        
        # Warn for very low speeds
        if speed_percent < 10:
            print(f"Warning: Setting fan speed very low ({speed_percent}%) - monitor temperatures")
        
        try:
            fan_info = self.controllable_fans[fan_key]
            pwm_value = int((speed_percent / 100) * fan_info['max_pwm'])
            
            # Verify PWM path exists
            if not os.path.exists(fan_info['pwm_path']):
                return False, f"PWM control file not found: {fan_info['pwm_path']}"
            
            # Use pkexec to write PWM value
            cmd = f"echo {pwm_value} | pkexec tee {fan_info['pwm_path']}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                # Update cached value
                self.controllable_fans[fan_key]['current_pwm'] = pwm_value
                return True, f"Fan speed set to {speed_percent}%"
            else:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                return False, f"Failed to set fan speed: {error_msg}"
                
        except subprocess.TimeoutExpired:
            return False, "Timeout: Fan speed change took too long"
        except Exception as e:
            return False, f"Error setting fan speed: {str(e)}"    
    
    def is_safe_to_control_fans(self):
        """Check if it's safe to control fans based on temperatures"""
        try:
            temps = psutil.sensors_temperatures()
            max_temp = 0
            
            for sensor_name, sensor_list in temps.items():
                for sensor in sensor_list:
                    if sensor.current and sensor.current > max_temp:
                        max_temp = sensor.current
            
            # Consider unsafe if any temperature is above 85°C
            if max_temp > 85:
                return False, f"High temperature detected: {max_temp}°C - Fan control disabled for safety"
            
            return True, "Safe to control fans"
            
        except Exception as e:
            return False, f"Cannot determine system temperature: {str(e)}"
    
    def set_fan_mode(self, fan_key, mode):
        """Set fan mode (automatic=1, manual=0)"""
        if fan_key not in self.controllable_fans:
            return False, "Fan not controllable"
        
        try:
            fan_info = self.controllable_fans[fan_key]
            enable_path = fan_info['pwm_enable_path']
            
            if not os.path.exists(enable_path):
                return False, "Fan mode control not available"
            
            mode_value = 1 if mode == 'automatic' else 0
            cmd = f"echo {mode_value} | pkexec tee {enable_path}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                return True, f"Fan mode set to {mode}"
            else:
                return False, f"Failed to set fan mode: {result.stderr}"
        except Exception as e:
            return False, f"Error setting fan mode: {str(e)}"

class GPUControlWidget(QWidget):
    def __init__(self, gpu_controller):
        super().__init__()
        self.gpu_controller = gpu_controller
        self.init_ui()
        self.update_gpu_info()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # GPU Info Card
        info_card = QGroupBox("🎮 GPU Information")
        info_layout = QGridLayout()
        info_layout.setSpacing(16)

        self.gpu_name_label = QLabel("N/A")
        self.gpu_temp_label = QLabel("N/A")
        self.gpu_usage_label = QLabel("N/A")
        self.gpu_memory_label = QLabel("N/A")

        info_layout.addWidget(QLabel("GPU Name:"), 0, 0)
        info_layout.addWidget(self.gpu_name_label, 0, 1)
        info_layout.addWidget(QLabel("Temperature:"), 1, 0)
        info_layout.addWidget(self.gpu_temp_label, 1, 1)
        info_layout.addWidget(QLabel("Usage:"), 2, 0)
        info_layout.addWidget(self.gpu_usage_label, 2, 1)
        info_layout.addWidget(QLabel("Memory:"), 3, 0)
        info_layout.addWidget(self.gpu_memory_label, 3, 1)

        info_card.setLayout(info_layout)
        main_layout.addWidget(info_card)

        # GPU Control Card
        control_card = QGroupBox("🔧 GPU Controls")
        control_layout = QVBoxLayout()
        control_layout.setSpacing(16)

        if self.gpu_controller.gpu_info.get('vendor') == 'AMD':
            self.amd_power_level_combo = QComboBox()
            self.amd_power_level_combo.addItems(['auto', 'low', 'high'])
            apply_btn = QPushButton("Apply Performance Level")
            apply_btn.clicked.connect(self.apply_amd_performance_level)
            control_layout.addWidget(QLabel("AMD PowerPlay Level:"))
            control_layout.addWidget(self.amd_power_level_combo)
            control_layout.addWidget(apply_btn)
        else:
            control_layout.addWidget(QLabel("No controls available for this GPU."))

        control_card.setLayout(control_layout)
        main_layout.addWidget(control_card)

        main_layout.addStretch()
        self.setLayout(main_layout)

    def update_gpu_info(self):
        gpu_info = self.gpu_controller.get_gpu_info()
        self.gpu_name_label.setText(gpu_info.get('name', 'N/A'))
        self.gpu_temp_label.setText(f"{gpu_info.get('temperature', 'N/A')} °C")
        self.gpu_usage_label.setText(f"{gpu_info.get('usage', 'N/A')} %")
        if gpu_info.get('vendor') == 'NVIDIA':
            self.gpu_memory_label.setText(f"{gpu_info.get('memory_used', 'N/A')} / {gpu_info.get('memory_total', 'N/A')} MiB")
        else:
            self.gpu_memory_label.setText("N/A")

    def apply_amd_performance_level(self):
        level = self.amd_power_level_combo.currentText()
        success, message = self.gpu_controller.set_amd_performance_level(level)
        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)

class SystemInfoThread(QThread):
    data_updated = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.fan_controller = FanController()
        self.gpu_controller = GPUController()
    
    def run(self):
        while True:
            try:
                system_info = {
                    'cpu_percent': psutil.cpu_percent(interval=1),
                    'memory': psutil.virtual_memory(),
                    'disk': psutil.disk_usage('/'),
                    'battery': psutil.sensors_battery(),
                    'temperatures': psutil.sensors_temperatures(),
                    'fans': self.fan_controller.get_current_fan_speeds(),
                    'fan_info': self.fan_controller.fan_info,
                    'controllable_fans': self.fan_controller.controllable_fans,
                    'gpu_info': self.gpu_controller.get_gpu_info()
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
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # System Overview Cards
        overview_group = QGroupBox("📊 System Overview")
        overview_layout = QGridLayout()
        overview_layout.setSpacing(16)
        
        # CPU Card
        cpu_card = self.create_metric_card("🖥️ CPU", "processor")
        self.cpu_usage = cpu_card['progress']
        self.cpu_value_label = cpu_card['value']
        overview_layout.addWidget(cpu_card['widget'], 0, 0)
        
        # Memory Card
        memory_card = self.create_metric_card("🧠 Memory", "memory")
        self.memory_usage = memory_card['progress']
        self.memory_value_label = memory_card['value']
        overview_layout.addWidget(memory_card['widget'], 0, 1)
        
        # Disk Card
        disk_card = self.create_metric_card("💾 Storage", "disk")
        self.disk_usage = disk_card['progress']
        self.disk_value_label = disk_card['value']
        overview_layout.addWidget(disk_card['widget'], 1, 0)
        
        # Battery Card
        battery_card = self.create_metric_card("🔋 Battery", "battery")
        self.battery_usage = battery_card['progress']
        self.battery_value_label = battery_card['value']
        overview_layout.addWidget(battery_card['widget'], 1, 1)

        # GPU Card
        gpu_card = self.create_metric_card("🎮 GPU", "gpu")
        self.gpu_usage = gpu_card['progress']
        self.gpu_value_label = gpu_card['value']
        overview_layout.addWidget(gpu_card['widget'], 2, 0, 1, 2)
        
        overview_group.setLayout(overview_layout)
        main_layout.addWidget(overview_group)
        
        # Temperature and Fan Info Row
        info_layout = QHBoxLayout()
        info_layout.setSpacing(16)
        
        # Temperature Info
        temp_group = QGroupBox("🌡️ Temperatures")
        temp_layout = QVBoxLayout()
        temp_layout.setContentsMargins(12, 15, 12, 12)
        temp_layout.setSpacing(8)
        
        self.temp_text = QTextEdit()
        self.temp_text.setMaximumHeight(110)
        self.temp_text.setMinimumHeight(110)
        self.temp_text.setReadOnly(True)
        self.temp_text.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d2d;
                border: 2px solid #404040;
                border-radius: 8px;
                color: #ffffff;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                padding: 8px;
                line-height: 1.4;
            }
        """)
        temp_layout.addWidget(self.temp_text)
        
        temp_group.setLayout(temp_layout)
        info_layout.addWidget(temp_group)
        
        # Fan Info
        fan_group = QGroupBox("🌀 Fan Information")
        fan_layout = QVBoxLayout()
        fan_layout.setContentsMargins(12, 15, 12, 12)
        fan_layout.setSpacing(8)
        
        self.fan_text = QTextEdit()
        self.fan_text.setMaximumHeight(110)
        self.fan_text.setMinimumHeight(110)
        self.fan_text.setReadOnly(True)
        self.fan_text.setStyleSheet("""
            QTextEdit {
                background-color: #2d2d2d;
                border: 2px solid #404040;
                border-radius: 8px;
                color: #ffffff;
                font-family: 'Segoe UI', sans-serif;
                font-size: 13px;
                padding: 8px;
                line-height: 1.4;
            }
        """)
        fan_layout.addWidget(self.fan_text)
        
        fan_group.setLayout(fan_layout)
        info_layout.addWidget(fan_group)
        
        info_widget = QWidget()
        info_widget.setLayout(info_layout)
        main_layout.addWidget(info_widget)
        
        self.setLayout(main_layout)
    
    def create_metric_card(self, title, metric_type):
        """Create a modern metric card widget"""
        card = QWidget()
        card.setFixedHeight(140)
        card.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 2px solid #404040;
                border-radius: 12px;
            }
            QWidget:hover {
                border-color: #0078d4;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #ffffff;
            padding: 2px 0px;
        """)
        layout.addWidget(title_label)
        
        # Progress Bar
        progress = QProgressBar()
        progress.setMaximum(100)
        progress.setFixedHeight(24)
        progress.setStyleSheet("""
            QProgressBar {
                border: 2px solid #404040;
                border-radius: 6px;
                text-align: center;
                color: #ffffff;
                font-weight: 600;
                font-size: 12px;
                background-color: #1a1a1a;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0078d4, stop: 1 #40a9ff);
                border-radius: 4px;
            }
        """)
        layout.addWidget(progress)
        
        # Value Label
        value_label = QLabel("Loading...")
        value_label.setStyleSheet("""
            font-size: 12px;
            color: #cccccc;
            font-weight: 500;
            padding: 2px 0px;
        """)
        layout.addWidget(value_label)
        
        card.setLayout(layout)
        
        return {
            'widget': card,
            'progress': progress,
            'value': value_label
        }
    
    def init_monitoring(self):
        self.monitor_thread = SystemInfoThread()
        self.monitor_thread.data_updated.connect(self.update_system_info)
        self.monitor_thread.start()
        
        # Store reference to fan controller for other components
        self.fan_controller = self.monitor_thread.fan_controller
    
    def update_system_info(self, data):
        # Update CPU
        cpu_percent = int(data['cpu_percent'])
        self.cpu_usage.setValue(cpu_percent)
        self.cpu_value_label.setText(f"{cpu_percent}% Usage")
        
        # Update Memory
        memory = data['memory']
        memory_percent = (memory.used / memory.total) * 100
        memory_gb_used = memory.used / (1024**3)
        memory_gb_total = memory.total / (1024**3)
        self.memory_usage.setValue(int(memory_percent))
        self.memory_value_label.setText(f"{memory_gb_used:.1f}GB / {memory_gb_total:.1f}GB")
        
        # Update Disk
        disk = data['disk']
        disk_percent = (disk.used / disk.total) * 100
        disk_gb_used = disk.used / (1024**3)
        disk_gb_total = disk.total / (1024**3)
        self.disk_usage.setValue(int(disk_percent))
        self.disk_value_label.setText(f"{disk_gb_used:.1f}GB / {disk_gb_total:.1f}GB")
        
        # Update Battery
        battery = data['battery']
        if battery:
            battery_percent = int(battery.percent)
            status = "⚡ Charging" if battery.power_plugged else "🔋 Discharging"
            self.battery_usage.setValue(battery_percent)
            self.battery_value_label.setText(f"{battery_percent}% ({status})")
        else:
            self.battery_usage.setValue(0)
            self.battery_value_label.setText("Not Available")

        # Update GPU
        gpu_info = data.get('gpu_info', {})
        if gpu_info and gpu_info.get('usage') is not None and gpu_info.get('usage') != 'N/A':
            gpu_usage = int(gpu_info['usage'])
            self.gpu_usage.setValue(gpu_usage)
            self.gpu_value_label.setText(f"{gpu_usage}% Usage")
        else:
            self.gpu_usage.setValue(0)
            self.gpu_value_label.setText("N/A")
        
        # Update Temperatures
        temps = data['temperatures']
        temp_text = ""
        if temps:
            temp_text += "<div style='font-size: 14px; color: #ffffff; margin-bottom: 8px;'><b>🌡️ System Temperatures</b></div>"
            for name, entries in temps.items():
                for entry in entries:
                    temp = entry.current
                    # Color code temperatures
                    if temp > 80:
                        color = "#ff4757"  # Red for hot
                    elif temp > 70:
                        color = "#ffa502"  # Orange for warm
                    elif temp > 60:
                        color = "#fffa65"  # Yellow for moderate
                    else:
                        color = "#7bed9f"  # Green for cool
                    
                    temp_text += f"<div style='margin: 4px 0; color: #cccccc;'>• {name}: <span style='color: {color}; font-weight: 600;'>{temp}°C</span></div>"
        else:
            temp_text = "<div style='color: #cccccc; text-align: center; margin-top: 20px;'>🔍 No temperature sensors detected</div>"
        
        self.temp_text.setHtml(temp_text)
        
        # Update Fan Information
        fans = data.get('fans', {})
        fan_info = data.get('fan_info', {})
        controllable_fans = data.get('controllable_fans', {})
        
        fan_text = ""
        if fans:
            fan_text += "<div style='font-size: 14px; color: #ffffff; margin-bottom: 8px;'><b>🌀 Detected Fans</b></div>"
            for fan_key, rpm in fans.items():
                fan_name = fan_info.get(fan_key, {}).get('name', fan_key)
                fan_text += f"<div style='margin: 4px 0; color: #cccccc;'>• {fan_name}: <span style='color: #0078d4; font-weight: 600;'>{rpm} RPM</span></div>"
            
            if controllable_fans:
                fan_text += "<div style='font-size: 14px; color: #ffffff; margin: 12px 0 8px 0;'><b>⚙️ Controllable Fans</b></div>"
                for fan_key, info in controllable_fans.items():
                    fan_name = info.get('name', fan_key)
                    current_pwm = info.get('current_pwm', 0)
                    pwm_percent = round((current_pwm / 255) * 100)
                    color = "#7bed9f" if pwm_percent > 60 else "#ffa502" if pwm_percent > 30 else "#ff4757"
                    fan_text += f"<div style='margin: 4px 0; color: #cccccc;'>• {fan_name}: <span style='color: {color}; font-weight: 600;'>{pwm_percent}% PWM</span></div>"
        else:
            fan_text = "<div style='color: #cccccc; text-align: center; margin-top: 15px;'>🔍 No fans detected or sensors not available</div>"
            fan_text += "<div style='color: #999999; font-style: italic; text-align: center; margin-top: 8px; font-size: 12px;'>This is normal on some laptops where fan control is managed by proprietary firmware.</div>"
        
        self.fan_text.setHtml(fan_text)

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
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Top row with CPU and Brightness controls
        top_row = QHBoxLayout()
        top_row.setSpacing(16)
        
        # CPU Governor Control Card
        governor_card = QWidget()
        governor_card.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 2px solid #404040;
                border-radius: 16px;
                padding: 20px;
            }
            QWidget:hover {
                border-color: #0078d4;
            }
        """)
        
        governor_layout = QVBoxLayout()
        governor_layout.setSpacing(16)
        governor_layout.setContentsMargins(20, 20, 20, 20)
        
        # CPU Governor Header
        cpu_header = QHBoxLayout()
        cpu_icon = QLabel("⚡")
        cpu_icon.setStyleSheet("font-size: 24px;")
        cpu_header.addWidget(cpu_icon)
        
        cpu_title = QLabel("CPU Governor")
        cpu_title.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
            margin-left: 8px;
        """)
        cpu_header.addWidget(cpu_title)
        cpu_header.addStretch()
        governor_layout.addLayout(cpu_header)
        
        # Current governor display
        current_layout = QHBoxLayout()
        current_layout.addWidget(QLabel("Current:"))
        self.current_governor = QLabel("Loading...")
        self.current_governor.setStyleSheet("""
            font-weight: 600;
            color: #0078d4;
        """)
        current_layout.addWidget(self.current_governor)
        current_layout.addStretch()
        governor_layout.addLayout(current_layout)
        
        # Governor selection
        selection_layout = QVBoxLayout()
        selection_layout.setSpacing(8)
        
        set_label = QLabel("Set Governor:")
        set_label.setStyleSheet("font-weight: 500; color: #cccccc;")
        selection_layout.addWidget(set_label)
        
        self.governor_combo = QComboBox()
        self.load_available_governors()
        selection_layout.addWidget(self.governor_combo)
        
        apply_governor_btn = QPushButton("🚀 Apply Governor")
        apply_governor_btn.clicked.connect(self.apply_cpu_governor)
        selection_layout.addWidget(apply_governor_btn)
        
        governor_layout.addLayout(selection_layout)
        governor_card.setLayout(governor_layout)
        top_row.addWidget(governor_card)
        
        # Brightness Control Card
        brightness_card = QWidget()
        brightness_card.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 2px solid #404040;
                border-radius: 16px;
                padding: 20px;
            }
            QWidget:hover {
                border-color: #0078d4;
            }
        """)
        
        brightness_layout = QVBoxLayout()
        brightness_layout.setSpacing(16)
        brightness_layout.setContentsMargins(20, 20, 20, 20)
        
        # Brightness Header
        brightness_header = QHBoxLayout()
        brightness_icon = QLabel("🔆")
        brightness_icon.setStyleSheet("font-size: 24px;")
        brightness_header.addWidget(brightness_icon)
        
        brightness_title = QLabel("Display Brightness")
        brightness_title.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
            margin-left: 8px;
        """)
        brightness_header.addWidget(brightness_title)
        brightness_header.addStretch()
        brightness_layout.addLayout(brightness_header)
        
        # Brightness slider with value display
        slider_layout = QVBoxLayout()
        slider_layout.setSpacing(8)
        
        brightness_label = QLabel("Brightness Level:")
        brightness_label.setStyleSheet("font-weight: 500; color: #cccccc;")
        slider_layout.addWidget(brightness_label)
        
        slider_container = QHBoxLayout()
        
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(1)
        self.brightness_slider.setMaximum(100)
        self.brightness_slider.setValue(50)
        self.brightness_slider.valueChanged.connect(self.change_brightness)
        self.brightness_slider.valueChanged.connect(self.update_brightness_label)
        slider_container.addWidget(self.brightness_slider)
        
        self.brightness_value_label = QLabel("50%")
        self.brightness_value_label.setStyleSheet("""
            font-size: 14px;
            font-weight: 600;
            color: #0078d4;
            min-width: 40px;
        """)
        slider_container.addWidget(self.brightness_value_label)
        
        slider_layout.addLayout(slider_container)
        brightness_layout.addLayout(slider_layout)
        
        brightness_card.setLayout(brightness_layout)
        top_row.addWidget(brightness_card)
        
        main_layout.addLayout(top_row)
        
        # Fan Control Section (expandable)
        self.fan_control_group = QGroupBox("🌀 Fan Control")
        self.fan_control_layout = QVBoxLayout()
        self.fan_control_layout.setSpacing(16)
        self.fan_control_layout.setContentsMargins(16, 20, 16, 16)
        self.fan_control_group.setLayout(self.fan_control_layout)
        
        # Initially hidden, will be shown if controllable fans are detected
        self.fan_control_group.setVisible(False)
        self.fan_controllers = {}
        
        main_layout.addWidget(self.fan_control_group)
        
        # Add stretch to push everything to top
        main_layout.addStretch()
        
        self.setLayout(main_layout)
        self.update_current_governor()
        
        # Set up fan monitoring
        self.setup_fan_monitoring()
    
    def update_brightness_label(self, value):
        """Update brightness value label"""
        self.brightness_value_label.setText(f"{value}%")
    
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
    
    def setup_fan_monitoring(self):
        """Set up fan monitoring and control interface"""
        try:
            # Create a timer to periodically check for fan updates
            self.fan_timer = QTimer()
            self.fan_timer.timeout.connect(self.update_fan_controls)
            self.fan_timer.start(3000)  # Update every 3 seconds
            
            # Initial fan control setup
            self.update_fan_controls()
        except Exception as e:
            print(f"Error setting up fan monitoring: {e}")
    
    def update_fan_controls(self):
        """Update fan control interface based on detected fans"""
        try:
            # Get the main window to access the system info widget
            main_window = self.parent().parent()
            if hasattr(main_window, 'tab_widget'):
                system_info_widget = main_window.tab_widget.widget(0)
                if hasattr(system_info_widget, 'fan_controller'):
                    fan_controller = system_info_widget.fan_controller
                    
                    # Re-detect fans periodically
                    fan_controller.detect_fans()
                    fan_controller.detect_controllable_fans()
                    
                    # Update controllable fans
                    controllable_fans = fan_controller.controllable_fans
                    
                    if controllable_fans and not self.fan_control_group.isVisible():
                        self.create_fan_control_interface(controllable_fans, fan_controller)
                        self.fan_control_group.setVisible(True)
                    elif controllable_fans:
                        self.update_fan_status(controllable_fans)
                    elif not controllable_fans and self.fan_control_group.isVisible():
                        # Hide fan controls if no controllable fans are detected
                        self.fan_control_group.setVisible(False)
        except Exception as e:
            print(f"Error updating fan controls: {e}")
            # Optionally show error in UI
            if hasattr(self, 'fan_control_group'):
                self.fan_control_group.setToolTip(f"Fan control error: {str(e)}")
    
    def create_fan_control_interface(self, controllable_fans, fan_controller):
        """Create the fan control interface"""
        # Clear existing layout
        for i in reversed(range(self.fan_control_layout.count())):
            child = self.fan_control_layout.itemAt(i).widget()
            if child:
                child.setParent(None)
        
        self.fan_controllers = {}
        
        # Add enhanced fan mode control
        mode_card = QWidget()
        mode_card.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 2px solid #404040;
                border-radius: 16px;
                padding: 20px;
                margin: 8px;
            }
            QWidget:hover {
                border-color: #0078d4;
            }
        """)
        
        mode_layout = QVBoxLayout()
        mode_layout.setSpacing(16)
        mode_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header_layout = QHBoxLayout()
        
        mode_icon = QLabel("⚙️")
        mode_icon.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(mode_icon)
        
        mode_title = QLabel("Fan Control Mode")
        mode_title.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
            margin-left: 8px;
        """)
        header_layout.addWidget(mode_title)
        header_layout.addStretch()
        
        mode_layout.addLayout(header_layout)
        
        # Mode selection section
        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(16)
        
        mode_label = QLabel("Control Mode:")
        mode_label.setStyleSheet("""
            font-size: 14px;
            color: #cccccc;
            font-weight: 500;
        """)
        selection_layout.addWidget(mode_label)
        
        self.fan_mode_combo = QComboBox()
        self.fan_mode_combo.addItems(["🤖 Automatic", "👤 Manual"])
        self.fan_mode_combo.setStyleSheet("""
            QComboBox {
                background-color: #1a1a1a;
                border: 2px solid #404040;
                border-radius: 8px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 500;
                min-width: 150px;
            }
            QComboBox:hover {
                border-color: #0078d4;
            }
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
                margin-right: 5px;
            }
        """)
        self.fan_mode_combo.currentTextChanged.connect(self.on_fan_mode_changed)
        selection_layout.addWidget(self.fan_mode_combo)
        
        selection_layout.addStretch()
        
        apply_mode_btn = QPushButton("🚀 Apply Mode")
        apply_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                padding: 10px 20px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
        """)
        apply_mode_btn.clicked.connect(self.apply_fan_mode)
        selection_layout.addWidget(apply_mode_btn)
        
        mode_layout.addLayout(selection_layout)
        
        # Mode description
        self.mode_description = QLabel("🤖 Automatic mode: System controls fan speeds based on temperature")
        self.mode_description.setStyleSheet("""
            font-size: 12px;
            color: #7bed9f;
            font-weight: 500;
            margin-top: 8px;
            padding: 8px 12px;
            background-color: #1a1a1a;
            border-radius: 6px;
        """)
        mode_layout.addWidget(self.mode_description)
        
        mode_card.setLayout(mode_layout)
        self.fan_control_layout.addWidget(mode_card)
        
        # Add individual fan controls
        for fan_key, fan_info in controllable_fans.items():
            fan_widget = self.create_fan_control_widget(fan_key, fan_info, fan_controller)
            self.fan_control_layout.addWidget(fan_widget)
            
        # Store reference to fan controller
        self.fan_controller = fan_controller
    
    def create_fan_control_widget(self, fan_key, fan_info, fan_controller):
        """Create a modern control widget for a single fan"""
        # Create main fan card
        fan_card = QWidget()
        fan_card.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                border: 2px solid #404040;
                border-radius: 16px;
                padding: 20px;
                margin: 8px;
            }
            QWidget:hover {
                border-color: #0078d4;
                background-color: #323232;
            }
        """)
        
        main_layout = QVBoxLayout()
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Fan header with icon and name
        header_layout = QHBoxLayout()
        
        # Fan icon and name
        fan_icon = QLabel("🌀")
        fan_icon.setStyleSheet("font-size: 24px;")
        header_layout.addWidget(fan_icon)
        
        fan_name_label = QLabel(fan_info['name'])
        fan_name_label.setStyleSheet("""
            font-size: 18px;
            font-weight: 600;
            color: #ffffff;
            margin-left: 8px;
        """)
        header_layout.addWidget(fan_name_label)
        
        header_layout.addStretch()
        
        # Status indicator
        current_pwm = fan_info.get('current_pwm', 0)
        pwm_percent = round((current_pwm / 255) * 100)
        
        status_color = "#00ff00" if pwm_percent > 60 else "#ffff00" if pwm_percent > 30 else "#ff6b6b"
        status_label = QLabel(f"●")
        status_label.setStyleSheet(f"""
            font-size: 20px;
            color: {status_color};
        """)
        header_layout.addWidget(status_label)
        
        main_layout.addLayout(header_layout)
        
        # Current speed display
        speed_info_layout = QHBoxLayout()
        
        current_label = QLabel("Current Speed:")
        current_label.setStyleSheet("""
            font-size: 14px;
            color: #cccccc;
            font-weight: 500;
        """)
        speed_info_layout.addWidget(current_label)
        
        speed_info_layout.addStretch()
        
        pwm_label = QLabel(f"{pwm_percent}%")
        pwm_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 600;
            color: {status_color};
        """)
        speed_info_layout.addWidget(pwm_label)
        
        main_layout.addLayout(speed_info_layout)
        
        # Speed control section
        control_group = QWidget()
        control_group.setStyleSheet("""
            QWidget {
                background-color: #1a1a1a;
                border: 1px solid #404040;
                border-radius: 12px;
                padding: 16px;
            }
        """)
        
        control_layout = QVBoxLayout()
        control_layout.setSpacing(12)
        
        # Set speed label
        set_speed_label = QLabel("Set Speed:")
        set_speed_label.setStyleSheet("""
            font-size: 14px;
            color: #ffffff;
            font-weight: 600;
            margin-bottom: 8px;
        """)
        control_layout.addWidget(set_speed_label)
        
        # Slider container
        slider_container = QHBoxLayout()
        slider_container.setSpacing(12)
        
        # Speed control slider with enhanced styling
        speed_slider = QSlider(Qt.Orientation.Horizontal)
        speed_slider.setMinimum(0)
        speed_slider.setMaximum(100)
        speed_slider.setValue(pwm_percent)
        speed_slider.setEnabled(False)  # Disabled in automatic mode by default
        
        # Enhanced slider styling with safety colors
        speed_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 2px solid #404040;
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #ff4757, stop: 0.3 #ffa502, stop: 0.6 #fffa65, stop: 1 #7bed9f);
                height: 12px;
                border-radius: 6px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 3px solid #0078d4;
                width: 24px;
                height: 24px;
                margin: -8px 0;
                border-radius: 12px;
            }
            QSlider::handle:horizontal:hover {
                background: #e0e0e0;
                border-color: #40a9ff;
            }
            QSlider::handle:horizontal:disabled {
                background: #666666;
                border-color: #404040;
            }
        """)
        
        slider_container.addWidget(speed_slider)
        
        # Speed value display
        speed_value_label = QLabel(f"{pwm_percent}%")
        speed_value_label.setStyleSheet("""
            font-size: 16px;
            font-weight: 600;
            color: #0078d4;
            min-width: 50px;
        """)
        slider_container.addWidget(speed_value_label)
        
        control_layout.addLayout(slider_container)
        
        # Safety warning label
        safety_label = QLabel("")
        safety_label.setStyleSheet("""
            font-size: 13px;
            color: #ffa502;
            font-weight: 600;
            margin-top: 8px;
        """)
        control_layout.addWidget(safety_label)
        
        # Apply button
        apply_btn = QPushButton("🔧 Apply Settings")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                padding: 12px 20px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                margin-top: 8px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #404040;
                color: #808080;
            }
        """)
        apply_btn.clicked.connect(
            lambda: self.apply_fan_speed(fan_key, speed_slider.value())
        )
        control_layout.addWidget(apply_btn)
        
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)
        
        # Connect slider to update displays
        def update_speed_display(value):
            speed_value_label.setText(f"{value}%")
            
            # Update status color
            color = "#7bed9f" if value > 60 else "#fffa65" if value > 30 else "#ff4757"
            speed_value_label.setStyleSheet(f"""
                font-size: 16px;
                font-weight: 600;
                color: {color};
                min-width: 50px;
            """)
            
            # Update safety warnings
            if value < 20:
                safety_label.setText("⚠️ Low speed - Monitor temperatures closely!")
                safety_label.setStyleSheet("font-size: 13px; color: #ff4757; font-weight: 600; margin-top: 8px;")
            elif value < 40:
                safety_label.setText("⚠️ Moderate speed - Watch temperatures")
                safety_label.setStyleSheet("font-size: 13px; color: #ffa502; font-weight: 600; margin-top: 8px;")
            else:
                safety_label.setText("✅ Safe operating range")
                safety_label.setStyleSheet("font-size: 13px; color: #7bed9f; font-weight: 600; margin-top: 8px;")
        
        speed_slider.valueChanged.connect(update_speed_display)
        
        fan_card.setLayout(main_layout)
        
        # Store references
        self.fan_controllers[fan_key] = {
            'group': fan_card,
            'pwm_label': pwm_label,
            'speed_slider': speed_slider,
            'speed_value_label': speed_value_label,
            'safety_label': safety_label,
            'apply_btn': apply_btn,
            'status_label': status_label
        }
        
        return fan_card
    
    def on_fan_mode_changed(self, mode):
        """Handle fan mode change"""
        is_manual = "Manual" in mode
        
        # Update mode description
        if hasattr(self, 'mode_description'):
            if is_manual:
                self.mode_description.setText("👤 Manual mode: You control fan speeds manually - Monitor temperatures!")
                self.mode_description.setStyleSheet("""
                    font-size: 12px;
                    color: #ffa502;
                    font-weight: 500;
                    margin-top: 8px;
                    padding: 8px 12px;
                    background-color: #1a1a1a;
                    border-radius: 6px;
                """)
            else:
                self.mode_description.setText("🤖 Automatic mode: System controls fan speeds based on temperature")
                self.mode_description.setStyleSheet("""
                    font-size: 12px;
                    color: #7bed9f;
                    font-weight: 500;
                    margin-top: 8px;
                    padding: 8px 12px;
                    background-color: #1a1a1a;
                    border-radius: 6px;
                """)
        
        # Enable/disable fan controls
        for fan_key, controls in self.fan_controllers.items():
            controls['speed_slider'].setEnabled(is_manual)
            controls['apply_btn'].setEnabled(is_manual)
    
    def apply_fan_mode(self):
        """Apply fan mode to all controllable fans with error handling"""
        if not hasattr(self, 'fan_controller'):
            QMessageBox.critical(self, "Error", "Fan controller not available")
            return
        
        mode = self.fan_mode_combo.currentText().lower()
        
        # Safety check for manual mode
        if mode == "manual":
            is_safe, safety_message = self.fan_controller.is_safe_to_control_fans()
            if not is_safe:
                QMessageBox.critical(self, "Safety Warning", 
                                   f"{safety_message}\n\nSwitching to manual mode is not recommended.")
                return
        
        success_count = 0
        error_messages = []
        
        for fan_key in self.fan_controllers.keys():
            success, message = self.fan_controller.set_fan_mode(fan_key, mode)
            if success:
                success_count += 1
            else:
                error_messages.append(f"{fan_key}: {message}")
        
        if success_count > 0:
            QMessageBox.information(self, "Success", 
                                  f"Fan mode set to {mode} for {success_count} fans")
        
        if error_messages:
            QMessageBox.warning(self, "Partial Success", 
                              "Some fans failed:\n" + "\n".join(error_messages[:5]))
    
    def apply_fan_speed(self, fan_key, speed_percent):
        """Apply fan speed to a specific fan with safety checks"""
        if not hasattr(self, 'fan_controller'):
            QMessageBox.critical(self, "Error", "Fan controller not available")
            return
        
        # Safety check
        is_safe, safety_message = self.fan_controller.is_safe_to_control_fans()
        if not is_safe:
            QMessageBox.critical(self, "Safety Warning", safety_message)
            return
        
        # Show confirmation for very low speeds
        if speed_percent < 20:
            reply = QMessageBox.question(self, "Low Speed Warning", 
                                       f"Setting fan speed to {speed_percent}% may cause overheating.\n\nMonitor temperatures closely. Continue?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        
        success, message = self.fan_controller.set_fan_speed(fan_key, speed_percent)
        
        if success:
            QMessageBox.information(self, "Success", message)
        else:
            QMessageBox.critical(self, "Error", message)
    
    def update_fan_status(self, controllable_fans):
        """Update fan status display"""
        for fan_key, fan_info in controllable_fans.items():
            if fan_key in self.fan_controllers:
                current_pwm = fan_info.get('current_pwm', 0)
                pwm_percent = round((current_pwm / 255) * 100)
                
                controls = self.fan_controllers[fan_key]
                controls['pwm_label'].setText(f"{pwm_percent}%")
                
                # Update slider if not being dragged
                if not controls['speed_slider'].isSliderDown():
                    controls['speed_slider'].setValue(pwm_percent)
    
    def change_brightness(self, value):
        try:
            # Try different brightness control methods
            brightness_paths = [
                '/sys/class/backlight/intel_backlight/brightness',
                '/sys/class/backlight/acpi_video0/brightness',
                '/sys/class/backlight/amdgpu_bl0/brightness',
                '/sys/class/backlight/nvidia_backlight/brightness'
            ]
            
            # First try hardware backlight control
            for path in brightness_paths:
                if os.path.exists(path):
                    max_brightness_path = path.replace('brightness', 'max_brightness')
                    try:
                        with open(max_brightness_path, 'r') as f:
                            max_brightness = int(f.read().strip())
                        
                        new_brightness = int((value / 100) * max_brightness)
                        cmd = f"echo {new_brightness} | pkexec tee {path}"
                        subprocess.run(cmd, shell=True, check=True)
                        return
                    except:
                        continue
            
            # Try to detect current display output
            try:
                result = subprocess.run(['xrandr', '--listmonitors'], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    # Parse output to find active monitor
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:  # Skip header
                        if '+*' in line:  # Active primary monitor
                            monitor_name = line.split()[-1]
                            break
                    else:
                        monitor_name = "HDMI-0"  # Default fallback
                else:
                    monitor_name = "HDMI-0"
            except:
                monitor_name = "HDMI-0"
            
            # Fallback to xrandr with detected monitor
            brightness_value = max(0.1, min(1.0, value/100))  # Clamp between 0.1 and 1.0
            cmd = f"xrandr --output {monitor_name} --brightness {brightness_value}"
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode != 0:
                # Try common display names as fallback
                common_names = ["HDMI-0", "HDMI-1", "HDMI-A-0", "eDP-1", "DP-1", "VGA-1"]
                for name in common_names:
                    cmd = f"xrandr --output {name} --brightness {brightness_value}"
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        break
                
        except Exception as e:
            print(f"Error changing brightness: {e}")

class LenovoControlCenter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
    
    def init_ui(self):
        self.setWindowTitle("Lenovo Control Center")
        self.setGeometry(100, 100, 1000, 700)
        self.setMinimumSize(900, 600)
        
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
        self.tab_widget.addTab(GPUControlWidget(self.monitor_thread.gpu_controller), "GPU")
        
        layout.addWidget(self.tab_widget)
        
        # Set modern dark theme
        self.setStyleSheet("""
            /* Main Window */
            QMainWindow {
                background-color: #1a1a1a;
                color: #ffffff;
                font-family: 'Segoe UI', 'San Francisco', 'Arial', sans-serif;
            }
            
            /* Tab Widget */
            QTabWidget::pane {
                border: 1px solid #333333;
                background-color: #1a1a1a;
                border-radius: 8px;
            }
            
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #cccccc;
                padding: 12px 24px;
                margin-right: 4px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                min-width: 120px;
            }
            
            QTabBar::tab:selected {
                background-color: #0078d4;
                color: #ffffff;
                border-bottom: 3px solid #106ebe;
            }
            
            QTabBar::tab:hover:!selected {
                background-color: #404040;
                color: #ffffff;
            }
            
            /* Group Boxes */
            QGroupBox {
                font-weight: 600;
                font-size: 16px;
                border: 2px solid #404040;
                border-radius: 12px;
                margin-top: 16px;
                padding-top: 16px;
                color: #ffffff;
                background-color: #242424;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 20px;
                padding: 0 8px 0 8px;
                color: #0078d4;
            }
            
            /* Buttons */
            QPushButton {
                background-color: #0078d4;
                color: #ffffff;
                border: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-weight: 600;
                font-size: 14px;
                min-height: 20px;
            }
            
            QPushButton:hover {
                background-color: #106ebe;
                transform: translateY(-1px);
            }
            
            QPushButton:pressed {
                background-color: #005a9e;
                transform: translateY(0px);
            }
            
            QPushButton:disabled {
                background-color: #666666;
                color: #999999;
            }
            
            /* Progress Bars */
            QProgressBar {
                border: 2px solid #404040;
                border-radius: 8px;
                text-align: center;
                color: #ffffff;
                font-weight: 600;
                background-color: #2d2d2d;
                height: 24px;
            }
            
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0078d4, stop: 1 #40a9ff);
                border-radius: 6px;
            }
            
            /* Labels */
            QLabel {
                color: #ffffff;
                font-size: 14px;
            }
            
            /* Text Edits */
            QTextEdit {
                background-color: #2d2d2d;
                border: 2px solid #404040;
                border-radius: 8px;
                color: #ffffff;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                padding: 8px;
            }
            
            /* Sliders */
            QSlider::groove:horizontal {
                border: 1px solid #404040;
                height: 8px;
                background: #2d2d2d;
                border-radius: 4px;
            }
            
            QSlider::handle:horizontal {
                background: #0078d4;
                border: 2px solid #ffffff;
                width: 20px;
                height: 20px;
                margin: -7px 0;
                border-radius: 10px;
            }
            
            QSlider::handle:horizontal:hover {
                background: #40a9ff;
            }
            
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                    stop: 0 #0078d4, stop: 1 #40a9ff);
                border-radius: 4px;
            }
            
            /* Combo Boxes */
            QComboBox {
                background-color: #2d2d2d;
                border: 2px solid #404040;
                border-radius: 8px;
                padding: 8px 12px;
                color: #ffffff;
                font-size: 14px;
                min-width: 120px;
            }
            
            QComboBox:hover {
                border-color: #0078d4;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #ffffff;
                margin-right: 5px;
            }
            
            QComboBox QAbstractItemView {
                background-color: #2d2d2d;
                border: 2px solid #404040;
                border-radius: 8px;
                color: #ffffff;
                selection-background-color: #0078d4;
            }
            
            /* Spin Boxes */
            QSpinBox {
                background-color: #2d2d2d;
                border: 2px solid #404040;
                border-radius: 8px;
                padding: 8px;
                color: #ffffff;
                font-size: 14px;
            }
            
            QSpinBox:hover {
                border-color: #0078d4;
            }
            
            /* Checkboxes */
            QCheckBox {
                color: #ffffff;
                font-size: 14px;
            }
            
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #404040;
                border-radius: 4px;
                background-color: #2d2d2d;
            }
            
            QCheckBox::indicator:checked {
                background-color: #0078d4;
                border-color: #0078d4;
            }
            
            QCheckBox::indicator:checked:hover {
                background-color: #40a9ff;
            }
            
            /* Scrollbars */
            QScrollBar:vertical {
                background-color: #2d2d2d;
                width: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #0078d4;
                border-radius: 6px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #40a9ff;
            }
            
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
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