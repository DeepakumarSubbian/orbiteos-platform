#!/usr/bin/env python3
"""
OrbitEOS EV Charger Simulator
Simulates an EV charging station with OCPP 1.6J protocol
Protocol: OCPP 1.6J over WebSocket + MQTT for telemetry
"""

import os
import time
import random
import json
from datetime import datetime
import asyncio
import paho.mqtt.client as mqtt

# Configuration
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
DEVICE_ID = os.getenv('CHARGER_ID', 'EV-CHARGER-01')
MAX_POWER_KW = float(os.getenv('MAX_POWER_KW', 22))  # 22kW AC charger
CONNECTOR_TYPE = os.getenv('CONNECTOR_TYPE', 'Type2')

class EVChargerSimulator:
    def __init__(self):
        self.device_id = DEVICE_ID
        self.max_power_kw = MAX_POWER_KW
        self.connector_type = CONNECTOR_TYPE
        
        # Charger state
        self.status = "Available"  # Available, Preparing, Charging, SuspendedEV, SuspendedEVSE, Finishing, Reserved, Unavailable, Faulted
        self.current_power_kw = 0
        self.power_limit_kw = MAX_POWER_KW  # Can be throttled
        self.total_energy_kwh = 0
        self.session_energy_kwh = 0
        self.session_start_time = None
        
        # Vehicle state (when connected)
        self.vehicle_connected = False
        self.vehicle_soc_percent = 0
        self.vehicle_target_soc = 80
        self.vehicle_battery_capacity_kwh = 75  # Typical EV battery
        
        # Charging parameters
        self.voltage = 400  # 3-phase 400V
        self.current_limit_a = (MAX_POWER_KW * 1000) / (1.732 * 400)  # 3-phase
        self.current_a = 0
        
        # MQTT client
        self.mqtt_client = mqtt.Client(client_id=DEVICE_ID)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        
    def on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to control commands
        client.subscribe(f"orbiteos/devices/{self.device_id}/control/#")
        
    def on_mqtt_message(self, client, userdata, msg):
        """Handle control messages"""
        try:
            topic_parts = msg.topic.split('/')
            command = topic_parts[-1]
            
            if command == 'power_limit':
                limit = float(msg.payload.decode())
                self.set_power_limit(limit)
                print(f"Power limit set to: {limit} kW")
                
            elif command == 'start_charging':
                if self.vehicle_connected:
                    self.start_charging()
                    print("Charging started")
                    
            elif command == 'stop_charging':
                self.stop_charging()
                print("Charging stopped")
                
            elif command == 'simulate_connection':
                # For testing: simulate vehicle connection
                params = json.loads(msg.payload.decode())
                self.simulate_vehicle_connection(
                    soc=params.get('soc', 20),
                    capacity=params.get('capacity', 75)
                )
                
        except Exception as e:
            print(f"Error processing command: {e}")
    
    def simulate_vehicle_connection(self, soc=20, capacity=75):
        """Simulate a vehicle connecting"""
        self.vehicle_connected = True
        self.vehicle_soc_percent = soc
        self.vehicle_battery_capacity_kwh = capacity
        self.status = "Preparing"
        print(f"Vehicle connected: {capacity}kWh battery at {soc}% SoC")
        
        # Auto-start charging after 2 seconds
        time.sleep(2)
        self.start_charging()
    
    def simulate_vehicle_disconnection(self):
        """Simulate vehicle disconnecting"""
        self.vehicle_connected = False
        self.stop_charging()
        self.status = "Available"
        print("Vehicle disconnected")
    
    def set_power_limit(self, limit_kw):
        """Set power limit (smart charging)"""
        self.power_limit_kw = min(limit_kw, self.max_power_kw)
        self.power_limit_kw = max(0, self.power_limit_kw)
        
        # Adjust current charging power if needed
        if self.current_power_kw > self.power_limit_kw:
            self.current_power_kw = self.power_limit_kw
    
    def start_charging(self):
        """Start charging session"""
        if not self.vehicle_connected:
            return
            
        self.status = "Charging"
        self.session_start_time = datetime.now()
        self.session_energy_kwh = 0
        self.current_power_kw = self.power_limit_kw
    
    def stop_charging(self):
        """Stop charging session"""
        self.status = "Finishing" if self.vehicle_connected else "Available"
        self.current_power_kw = 0
        self.current_a = 0
    
    def calculate_charging(self, dt_seconds=5):
        """Calculate charging progress"""
        if self.status != "Charging":
            self.current_power_kw = 0
            self.current_a = 0
            return
        
        # Check if battery is full
        if self.vehicle_soc_percent >= self.vehicle_target_soc:
            print(f"Target SoC {self.vehicle_target_soc}% reached")
            self.stop_charging()
            return
        
        # Calculate power with some variation
        target_power = self.power_limit_kw
        
        # Taper charging near full (like real EVs)
        if self.vehicle_soc_percent > 80:
            taper_factor = (100 - self.vehicle_soc_percent) / 20
            target_power *= taper_factor
        
        # Add small random variation
        self.current_power_kw = target_power * (1 + random.gauss(0, 0.02))
        self.current_power_kw = max(0, min(self.power_limit_kw, self.current_power_kw))
        
        # Calculate current (3-phase: P = √3 × V × I × cos φ)
        power_factor = 0.99
        self.current_a = (self.current_power_kw * 1000) / (1.732 * self.voltage * power_factor)
        
        # Update energy and SoC
        dt_hours = dt_seconds / 3600
        energy_added_kwh = self.current_power_kw * dt_hours * 0.95  # 95% efficiency
        
        self.session_energy_kwh += energy_added_kwh
        self.total_energy_kwh += energy_added_kwh
        
        # Update vehicle SoC
        soc_increase = (energy_added_kwh / self.vehicle_battery_capacity_kwh) * 100
        self.vehicle_soc_percent += soc_increase
        self.vehicle_soc_percent = min(100, self.vehicle_soc_percent)
    
    def update_telemetry(self, dt_seconds=5):
        """Update charger telemetry"""
        # Calculate charging if active
        self.calculate_charging(dt_seconds)
        
        # Random chance of vehicle connection/disconnection for demo
        if not self.vehicle_connected and random.random() < 0.001:  # 0.1% chance per update
            self.simulate_vehicle_connection(
                soc=random.randint(10, 50),
                capacity=random.choice([50, 60, 75, 85, 100])
            )
        
        if self.vehicle_connected and self.status == "Finishing" and random.random() < 0.2:
            self.simulate_vehicle_disconnection()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'status': self.status,
            'power_kw': round(self.current_power_kw, 2),
            'power_limit_kw': round(self.power_limit_kw, 2),
            'current_a': round(self.current_a, 1),
            'voltage_v': self.voltage,
            'session_energy_kwh': round(self.session_energy_kwh, 2),
            'total_energy_kwh': round(self.total_energy_kwh, 2),
            'vehicle_connected': self.vehicle_connected,
            'vehicle_soc_percent': round(self.vehicle_soc_percent, 1) if self.vehicle_connected else None,
            'vehicle_target_soc': self.vehicle_target_soc if self.vehicle_connected else None,
            'connector_type': self.connector_type,
            'max_power_kw': self.max_power_kw,
            'session_duration_min': round((datetime.now() - self.session_start_time).total_seconds() / 60, 1) if self.session_start_time else 0
        }
    
    def publish_mqtt(self, telemetry):
        """Publish telemetry to MQTT"""
        topic_base = f"orbiteos/devices/{self.device_id}"
        
        # Publish individual metrics
        for key, value in telemetry.items():
            if key != 'timestamp' and value is not None:
                topic = f"{topic_base}/{key}"
                self.mqtt_client.publish(topic, str(value))
        
        # Publish aggregate JSON
        self.mqtt_client.publish(
            f"{topic_base}/telemetry",
            json.dumps(telemetry)
        )
        
        # Publish status changes
        if self.status == "Charging":
            self.mqtt_client.publish(
                f"{topic_base}/status",
                json.dumps({
                    'status': 'charging',
                    'power_kw': telemetry['power_kw'],
                    'soc': telemetry['vehicle_soc_percent']
                })
            )
    
    def simulation_loop(self):
        """Main simulation loop"""
        print(f"EV Charger Simulator started: {self.device_id}")
        print(f"Max Power: {self.max_power_kw} kW")
        print(f"Connector: {self.connector_type}")
        
        # Connect to MQTT
        try:
            self.mqtt_client.connect(MQTT_BROKER, 1883, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"Could not connect to MQTT: {e}")
        
        print("\n💡 Control Commands (MQTT):")
        print(f"   Set power limit: mosquitto_pub -t 'orbiteos/devices/{self.device_id}/control/power_limit' -m '11'")
        print(f"   Start charging:  mosquitto_pub -t 'orbiteos/devices/{self.device_id}/control/start_charging' -m ''")
        print(f"   Stop charging:   mosquitto_pub -t 'orbiteos/devices/{self.device_id}/control/stop_charging' -m ''")
        print(f"   Simulate car:    mosquitto_pub -t 'orbiteos/devices/{self.device_id}/control/simulate_connection' -m '{{\"soc\": 30, \"capacity\": 75}}'")
        print()
        
        while True:
            try:
                telemetry = self.update_telemetry(dt_seconds=5)
                self.publish_mqtt(telemetry)
                
                # Log with status indicators
                status_icons = {
                    'Available': '⚪',
                    'Preparing': '🟡',
                    'Charging': '🔌',
                    'SuspendedEV': '⏸️ ',
                    'SuspendedEVSE': '⏸️ ',
                    'Finishing': '✅',
                    'Faulted': '🔴'
                }
                icon = status_icons.get(self.status, '⚫')
                
                if self.vehicle_connected:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {icon} "
                          f"{self.status} | "
                          f"Power: {telemetry['power_kw']:.2f} kW | "
                          f"SoC: {telemetry['vehicle_soc_percent']:.1f}% | "
                          f"Session: {telemetry['session_energy_kwh']:.2f} kWh")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {icon} {self.status} (waiting for vehicle)")
                
                time.sleep(5)
                
            except Exception as e:
                print(f"Error in simulation loop: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(5)

if __name__ == "__main__":
    simulator = EVChargerSimulator()
    simulator.simulation_loop()
