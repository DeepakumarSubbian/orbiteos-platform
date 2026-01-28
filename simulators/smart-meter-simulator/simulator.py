#!/usr/bin/env python3
"""
OrbitEOS Smart Meter Simulator
Simulates a smart meter monitoring grid connection
Protocol: MQTT
"""

import os
import time
import random
import json
from datetime import datetime
import paho.mqtt.client as mqtt

# Configuration
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
DEVICE_ID = os.getenv('DEVICE_ID', 'smart-meter-01')
UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL', 5))  # seconds
MAX_GRID_CONNECTION_KW = float(os.getenv('MAX_GRID_CONNECTION_KW', 100))

class SmartMeterSimulator:
    def __init__(self):
        self.device_id = DEVICE_ID
        self.max_connection_kw = MAX_GRID_CONNECTION_KW
        
        # Meter state
        self.grid_power_kw = 0
        self.grid_voltage = 400  # 3-phase voltage
        self.grid_frequency_hz = 50.0
        self.total_import_kwh = 0
        self.total_export_kwh = 0
        self.power_factor = 0.98
        
        # Phase measurements (3-phase)
        self.phase_voltages = [230, 230, 230]  # L1, L2, L3
        self.phase_currents = [0, 0, 0]
        
        # Tariff tracking
        self.current_tariff_eur_kwh = 0.25
        self.peak_demand_kw = 0
        
        # MQTT client
        self.mqtt_client = mqtt.Client(client_id=DEVICE_ID)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        
        # Subscribe to device power topics to calculate grid power
        self.pv_power = 0
        self.battery_power = 0
        self.ev_power = 0
        self.base_load = 15  # kW baseline building load
        
    def on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to other devices to calculate grid balance
        client.subscribe("orbiteos/devices/+/power_kw")
        client.subscribe("orbiteos/devices/+/tariff/#")
        
    def on_mqtt_message(self, client, userdata, msg):
        """Process messages from other devices"""
        try:
            topic_parts = msg.topic.split('/')
            device_id = topic_parts[2]
            
            if 'power_kw' in msg.topic:
                power = float(msg.payload.decode())
                
                if 'pv' in device_id.lower():
                    self.pv_power = power
                elif 'battery' in device_id.lower():
                    self.battery_power = power
                elif 'charger' in device_id.lower() or 'ev' in device_id.lower():
                    self.ev_power = power
                    
        except Exception as e:
            pass  # Ignore malformed messages
    
    def calculate_grid_power(self):
        """
        Calculate grid power based on energy balance:
        Grid = Load + EV + Battery Charging - PV - Battery Discharging
        
        Positive = importing from grid
        Negative = exporting to grid
        """
        # Variable load throughout the day
        hour = datetime.now().hour
        load_factor = 1.0
        
        # Higher load during day, lower at night
        if 6 <= hour < 9:
            load_factor = 1.3  # Morning peak
        elif 9 <= hour < 17:
            load_factor = 1.1  # Daytime
        elif 17 <= hour < 22:
            load_factor = 1.5  # Evening peak
        else:
            load_factor = 0.6  # Night
            
        current_load = self.base_load * load_factor + random.gauss(0, 1)
        
        # Energy balance
        # Positive battery power = charging (consumes from grid)
        # Negative battery power = discharging (supplies to load)
        grid_power = (
            current_load +  # Building load
            self.ev_power +  # EV charging load
            max(0, self.battery_power) -  # Battery charging (if positive)
            self.pv_power -  # PV generation
            abs(min(0, self.battery_power))  # Battery discharging (if negative)
        )
        
        # Add small noise
        grid_power += random.gauss(0, 0.5)
        
        return grid_power
    
    def calculate_phase_distribution(self, total_power_kw):
        """Distribute total power across 3 phases"""
        # Ideally balanced, but with some asymmetry
        base = total_power_kw / 3
        
        # Add asymmetry (±10%)
        phase_powers = [
            base * (1 + random.gauss(0, 0.05)),
            base * (1 + random.gauss(0, 0.05)),
            base * (1 + random.gauss(0, 0.05))
        ]
        
        # Calculate currents (P = √3 × V × I × cos φ for 3-phase)
        # For simplicity: I = P / (V × cos φ) per phase
        for i in range(3):
            self.phase_currents[i] = abs(phase_powers[i] * 1000) / (self.phase_voltages[i] * self.power_factor)
        
        return phase_powers
    
    def update_energy_counters(self, grid_power_kw, dt_hours):
        """Update import/export energy counters"""
        energy_kwh = abs(grid_power_kw * dt_hours)
        
        if grid_power_kw > 0:
            self.total_import_kwh += energy_kwh
        else:
            self.total_export_kwh += energy_kwh
        
        # Track peak demand
        if abs(grid_power_kw) > self.peak_demand_kw:
            self.peak_demand_kw = abs(grid_power_kw)
    
    def get_tariff(self):
        """Get current electricity tariff (simple time-of-use)"""
        hour = datetime.now().hour
        
        # Simple time-of-use tariff
        if 7 <= hour < 9 or 17 <= hour < 21:
            return 0.35  # Peak hours
        elif 9 <= hour < 17:
            return 0.25  # Normal hours
        else:
            return 0.15  # Off-peak hours
    
    def update_telemetry(self, dt_seconds=5):
        """Update all meter readings"""
        dt_hours = dt_seconds / 3600
        
        # Calculate grid power
        self.grid_power_kw = self.calculate_grid_power()
        
        # Distribute across phases
        phase_powers = self.calculate_phase_distribution(self.grid_power_kw)
        
        # Update energy counters
        self.update_energy_counters(self.grid_power_kw, dt_hours)
        
        # Update tariff
        self.current_tariff_eur_kwh = self.get_tariff()
        
        # Add small voltage/frequency variations
        self.grid_voltage = 400 + random.gauss(0, 2)
        self.grid_frequency_hz = 50.0 + random.gauss(0, 0.02)
        
        for i in range(3):
            self.phase_voltages[i] = 230 + random.gauss(0, 2)
        
        # Check for grid issues
        status = "normal"
        if abs(self.grid_power_kw) > self.max_connection_kw * 0.9:
            status = "congestion_warning"
        if abs(self.grid_power_kw) > self.max_connection_kw:
            status = "congestion_critical"
        if self.grid_frequency_hz < 49.8 or self.grid_frequency_hz > 50.2:
            status = "frequency_deviation"
        
        return {
            'timestamp': datetime.now().isoformat(),
            'grid_power_kw': round(self.grid_power_kw, 2),
            'grid_import_kw': round(max(0, self.grid_power_kw), 2),
            'grid_export_kw': round(abs(min(0, self.grid_power_kw)), 2),
            'total_import_kwh': round(self.total_import_kwh, 2),
            'total_export_kwh': round(self.total_export_kwh, 2),
            'peak_demand_kw': round(self.peak_demand_kw, 2),
            'grid_voltage': round(self.grid_voltage, 1),
            'grid_frequency_hz': round(self.grid_frequency_hz, 3),
            'phase_voltages': [round(v, 1) for v in self.phase_voltages],
            'phase_currents': [round(i, 1) for i in self.phase_currents],
            'power_factor': round(self.power_factor, 2),
            'current_tariff_eur_kwh': round(self.current_tariff_eur_kwh, 3),
            'connection_utilization_pct': round(abs(self.grid_power_kw) / self.max_connection_kw * 100, 1),
            'status': status
        }
    
    def publish_mqtt(self, telemetry):
        """Publish telemetry to MQTT"""
        topic_base = f"orbiteos/devices/{self.device_id}"
        
        # Publish individual metrics
        for key, value in telemetry.items():
            if key != 'timestamp' and not isinstance(value, list):
                topic = f"{topic_base}/{key}"
                self.mqtt_client.publish(topic, str(value))
        
        # Publish aggregate JSON
        self.mqtt_client.publish(
            f"{topic_base}/telemetry",
            json.dumps(telemetry)
        )
        
        # Publish alerts if needed
        if telemetry['status'] != 'normal':
            alert = {
                'device_id': self.device_id,
                'alert_type': telemetry['status'],
                'severity': 'high' if 'critical' in telemetry['status'] else 'medium',
                'message': f"Grid power: {telemetry['grid_power_kw']} kW",
                'timestamp': telemetry['timestamp']
            }
            self.mqtt_client.publish(
                f"orbiteos/alerts/{self.device_id}",
                json.dumps(alert)
            )
    
    def simulation_loop(self):
        """Main simulation loop"""
        print(f"Smart Meter Simulator started: {self.device_id}")
        print(f"Max Grid Connection: {self.max_connection_kw} kW")
        print(f"Update Interval: {UPDATE_INTERVAL} seconds")
        
        # Connect to MQTT
        try:
            self.mqtt_client.connect(MQTT_BROKER, 1883, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"Could not connect to MQTT: {e}")
        
        # Wait a bit for subscriptions
        time.sleep(2)
        
        while True:
            try:
                telemetry = self.update_telemetry(dt_seconds=UPDATE_INTERVAL)
                self.publish_mqtt(telemetry)
                
                # Log with indicators
                direction = "⬆️" if telemetry['grid_power_kw'] > 0 else "⬇️" if telemetry['grid_power_kw'] < 0 else "⏸️ "
                status_icon = "⚠️" if telemetry['status'] != 'normal' else "✓"
                
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {status_icon} {direction} "
                      f"Grid: {telemetry['grid_power_kw']:+.2f} kW | "
                      f"Tariff: €{telemetry['current_tariff_eur_kwh']:.3f}/kWh | "
                      f"Util: {telemetry['connection_utilization_pct']:.1f}%")
                
                time.sleep(UPDATE_INTERVAL)
                
            except Exception as e:
                print(f"Error in simulation loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(UPDATE_INTERVAL)

if __name__ == "__main__":
    simulator = SmartMeterSimulator()
    simulator.simulation_loop()
