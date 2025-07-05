#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import threading
import time
import psutil
import platform
import os

class SystemMonitor:
    def __init__(self):
        self.running = False
        self.callbacks = []
    
    def add_callback(self, callback):
        self.callbacks.append(callback)
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        self.running = False
    
    def _monitor_loop(self):
        while self.running:
            try:
                data = {
                    'cpu_percent': psutil.cpu_percent(interval=1),
                    'memory': psutil.virtual_memory(),
                    'disk': psutil.disk_usage('/'),
                    'battery': psutil.sensors_battery(),
                    'temperatures': psutil.sensors_temperatures(),
                }
                
                for callback in self.callbacks:
                    callback(data)
                    
            except Exception as e:
                print(f"Monitor error: {e}")
            
            time.sleep(2)

class LenovoControlCenter:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Lenovo Control Center")
        self.root.geometry("800x600")
        self.root.configure(bg='#2b2b2b')
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        
        self.monitor = SystemMonitor()
        self.monitor.add_callback(self.update_system_info)
        
        self.create_widgets()
        self.monitor.start()
    
    def configure_styles(self):
        # Configure dark theme
        self.style.configure('TNotebook', background='#2b2b2b')
        self.style.configure('TNotebook.Tab', background='#3c3c3c', foreground='white')
        self.style.map('TNotebook.Tab', background=[('selected', '#e74c3c')])
        self.style.configure('TFrame', background='#2b2b2b')
        self.style.configure('TLabel', background='#2b2b2b', foreground='white')
        self.style.configure('TButton', background='#e74c3c', foreground='white')
        self.style.map('TButton', background=[('active', '#c0392b')])
        self.style.configure('TProgressbar', background='#e74c3c')
        self.style.configure('TScale', background='#2b2b2b')
    
    def create_widgets(self):
        # Create notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # System Info Tab
        self.system_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.system_frame, text="System Info")
        self.create_system_tab()
        
        # Battery Tab
        self.battery_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.battery_frame, text="Battery")
        self.create_battery_tab()
        
        # Power Tab
        self.power_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.power_frame, text="Power & Display")
        self.create_power_tab()
    
    def create_system_tab(self):
        # System Overview
        overview_frame = ttk.LabelFrame(self.system_frame, text="System Overview", padding=10)
        overview_frame.pack(fill='x', padx=10, pady=5)
        
        # CPU
        ttk.Label(overview_frame, text="CPU Usage:").grid(row=0, column=0, sticky='w', padx=5)
        self.cpu_progress = ttk.Progressbar(overview_frame, length=300, mode='determinate')
        self.cpu_progress.grid(row=0, column=1, padx=5, pady=2)
        self.cpu_label = ttk.Label(overview_frame, text="0%")
        self.cpu_label.grid(row=0, column=2, padx=5)
        
        # Memory
        ttk.Label(overview_frame, text="Memory Usage:").grid(row=1, column=0, sticky='w', padx=5)
        self.memory_progress = ttk.Progressbar(overview_frame, length=300, mode='determinate')
        self.memory_progress.grid(row=1, column=1, padx=5, pady=2)
        self.memory_label = ttk.Label(overview_frame, text="0%")
        self.memory_label.grid(row=1, column=2, padx=5)
        
        # Disk
        ttk.Label(overview_frame, text="Disk Usage:").grid(row=2, column=0, sticky='w', padx=5)
        self.disk_progress = ttk.Progressbar(overview_frame, length=300, mode='determinate')
        self.disk_progress.grid(row=2, column=1, padx=5, pady=2)
        self.disk_label = ttk.Label(overview_frame, text="0%")
        self.disk_label.grid(row=2, column=2, padx=5)
        
        # Battery
        self.battery_info_label = ttk.Label(overview_frame, text="Battery: N/A")
        self.battery_info_label.grid(row=3, column=0, columnspan=3, sticky='w', padx=5, pady=5)
        
        # Temperature
        temp_frame = ttk.LabelFrame(self.system_frame, text="Temperatures", padding=10)
        temp_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.temp_text = scrolledtext.ScrolledText(temp_frame, height=8, bg='#3c3c3c', fg='white')
        self.temp_text.pack(fill='both', expand=True)
    
    def create_battery_tab(self):
        # Battery Thresholds
        threshold_frame = ttk.LabelFrame(self.battery_frame, text="Battery Charge Thresholds", padding=10)
        threshold_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(threshold_frame, text="Start Charging At:").grid(row=0, column=0, sticky='w', padx=5)
        self.start_threshold = tk.Spinbox(threshold_frame, from_=40, to=80, value=60, width=10)
        self.start_threshold.grid(row=0, column=1, padx=5)
        ttk.Label(threshold_frame, text="%").grid(row=0, column=2, sticky='w')
        
        ttk.Label(threshold_frame, text="Stop Charging At:").grid(row=1, column=0, sticky='w', padx=5)
        self.stop_threshold = tk.Spinbox(threshold_frame, from_=60, to=100, value=80, width=10)
        self.stop_threshold.grid(row=1, column=1, padx=5)
        ttk.Label(threshold_frame, text="%").grid(row=1, column=2, sticky='w')
        
        apply_btn = ttk.Button(threshold_frame, text="Apply Thresholds", command=self.apply_battery_thresholds)
        apply_btn.grid(row=2, column=0, columnspan=3, pady=10)
        
        # Battery Info
        info_frame = ttk.LabelFrame(self.battery_frame, text="Battery Information", padding=10)
        info_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.battery_info_text = scrolledtext.ScrolledText(info_frame, height=10, bg='#3c3c3c', fg='white')
        self.battery_info_text.pack(fill='both', expand=True)
        
        self.update_battery_info()
    
    def create_power_tab(self):
        # CPU Governor
        governor_frame = ttk.LabelFrame(self.power_frame, text="CPU Governor", padding=10)
        governor_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(governor_frame, text="Current Governor:").grid(row=0, column=0, sticky='w', padx=5)
        self.current_governor_label = ttk.Label(governor_frame, text="Loading...")
        self.current_governor_label.grid(row=0, column=1, padx=5)
        
        ttk.Label(governor_frame, text="Set Governor:").grid(row=1, column=0, sticky='w', padx=5)
        self.governor_var = tk.StringVar()
        self.governor_combo = ttk.Combobox(governor_frame, textvariable=self.governor_var, state='readonly')
        self.governor_combo.grid(row=1, column=1, padx=5)
        
        apply_governor_btn = ttk.Button(governor_frame, text="Apply", command=self.apply_cpu_governor)
        apply_governor_btn.grid(row=2, column=0, columnspan=2, pady=10)
        
        # Brightness
        brightness_frame = ttk.LabelFrame(self.power_frame, text="Display Brightness", padding=10)
        brightness_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(brightness_frame, text="Brightness:").pack(anchor='w')
        self.brightness_var = tk.IntVar(value=50)
        self.brightness_scale = ttk.Scale(brightness_frame, from_=1, to=100, variable=self.brightness_var, 
                                         command=self.change_brightness, orient='horizontal', length=400)
        self.brightness_scale.pack(fill='x', pady=5)
        
        self.load_governors()
        self.update_current_governor()
    
    def update_system_info(self, data):
        try:
            # Update CPU
            cpu_percent = data['cpu_percent']
            self.cpu_progress['value'] = cpu_percent
            self.cpu_label.config(text=f"{cpu_percent:.1f}%")
            
            # Update Memory
            memory = data['memory']
            memory_percent = (memory.used / memory.total) * 100
            self.memory_progress['value'] = memory_percent
            self.memory_label.config(text=f"{memory_percent:.1f}%")
            
            # Update Disk
            disk = data['disk']
            disk_percent = (disk.used / disk.total) * 100
            self.disk_progress['value'] = disk_percent
            self.disk_label.config(text=f"{disk_percent:.1f}%")
            
            # Update Battery
            battery = data['battery']
            if battery:
                status = "Charging" if battery.power_plugged else "Discharging"
                self.battery_info_label.config(text=f"Battery: {battery.percent}% ({status})")
            else:
                self.battery_info_label.config(text="Battery: N/A")
            
            # Update Temperatures
            temps = data['temperatures']
            temp_text = ""
            for name, entries in temps.items():
                for entry in entries:
                    temp_text += f"{name}: {entry.current}°C\n"
            
            self.temp_text.delete(1.0, tk.END)
            self.temp_text.insert(1.0, temp_text)
            
        except Exception as e:
            print(f"Error updating UI: {e}")
    
    def apply_battery_thresholds(self):
        try:
            start_val = int(self.start_threshold.get())
            stop_val = int(self.stop_threshold.get())
            
            if start_val >= stop_val:
                messagebox.showerror("Error", "Start threshold must be less than stop threshold!")
                return
            
            # Apply thresholds
            start_cmd = f"echo {start_val} | pkexec tee /sys/class/power_supply/BAT0/charge_start_threshold"
            stop_cmd = f"echo {stop_val} | pkexec tee /sys/class/power_supply/BAT0/charge_stop_threshold"
            
            subprocess.run(start_cmd, shell=True, check=True)
            subprocess.run(stop_cmd, shell=True, check=True)
            
            messagebox.showinfo("Success", f"Battery thresholds set: {start_val}% - {stop_val}%")
            self.update_battery_info()
            
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", "Failed to apply battery thresholds. Check permissions.")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {str(e)}")
    
    def update_battery_info(self):
        try:
            info_text = ""
            
            # Battery info
            battery = psutil.sensors_battery()
            if battery:
                info_text += f"Battery Percentage: {battery.percent}%\n"
                info_text += f"Power Plugged: {'Yes' if battery.power_plugged else 'No'}\n"
                if battery.secsleft != psutil.POWER_TIME_UNLIMITED:
                    hours, remainder = divmod(battery.secsleft, 3600)
                    minutes, _ = divmod(remainder, 60)
                    info_text += f"Time Remaining: {hours:02d}:{minutes:02d}\n"
            
            # Current thresholds
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
            
            self.battery_info_text.delete(1.0, tk.END)
            self.battery_info_text.insert(1.0, info_text)
            
        except Exception as e:
            self.battery_info_text.delete(1.0, tk.END)
            self.battery_info_text.insert(1.0, f"Error reading battery info: {str(e)}")
    
    def load_governors(self):
        try:
            with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors', 'r') as f:
                governors = f.read().strip().split()
                self.governor_combo['values'] = governors
        except:
            self.governor_combo['values'] = ['performance', 'powersave', 'ondemand', 'conservative']
    
    def update_current_governor(self):
        try:
            with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor', 'r') as f:
                current = f.read().strip()
                self.current_governor_label.config(text=current)
        except:
            self.current_governor_label.config(text="N/A")
    
    def apply_cpu_governor(self):
        try:
            governor = self.governor_var.get()
            if not governor:
                messagebox.showerror("Error", "Please select a governor!")
                return
                
            cmd = f"echo {governor} | pkexec tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor"
            subprocess.run(cmd, shell=True, check=True)
            self.update_current_governor()
            messagebox.showinfo("Success", f"CPU governor set to: {governor}")
        except subprocess.CalledProcessError:
            messagebox.showerror("Error", "Failed to set CPU governor. Check permissions.")
        except Exception as e:
            messagebox.showerror("Error", f"Unexpected error: {str(e)}")
    
    def change_brightness(self, value):
        try:
            brightness_value = int(float(value))
            
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
                        
                        new_brightness = int((brightness_value / 100) * max_brightness)
                        cmd = f"echo {new_brightness} | pkexec tee {path}"
                        subprocess.run(cmd, shell=True, check=True)
                        return
                    except:
                        continue
            
            # Fallback to xrandr - get actual display name
            try:
                result = subprocess.run(['xrandr', '--listmonitors'], capture_output=True, text=True)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:  # Skip header
                        if '+*' in line:  # Primary display
                            display_name = line.split()[-1]
                            cmd = f"xrandr --output {display_name} --brightness {brightness_value/100}"
                            subprocess.run(cmd, shell=True, check=True)
                            return
            except:
                pass
            
            # Last resort - try common display names
            common_displays = ['HDMI-0', 'HDMI-1', 'eDP-1', 'VGA-1', 'DP-1']
            for display in common_displays:
                try:
                    cmd = f"xrandr --output {display} --brightness {brightness_value/100}"
                    result = subprocess.run(cmd, shell=True, stderr=subprocess.PIPE)
                    if result.returncode == 0:
                        return
                except:
                    continue
            
        except Exception as e:
            print(f"Error changing brightness: {e}")
    
    def run(self):
        self.root.mainloop()
        self.monitor.stop()

def main():
    try:
        import psutil
    except ImportError:
        print("Error: psutil is required. Install with: pip install psutil")
        return
    
    app = LenovoControlCenter()
    app.run()

if __name__ == "__main__":
    main()