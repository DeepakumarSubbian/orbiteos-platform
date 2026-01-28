#!/usr/bin/env python3
"""
OrbitEOS PV Simulator
Simulates a solar PV inverter with realistic generation patterns
Protocols: Modbus TCP, MQTT
"""

import os
import time
import math
import random
from datetime import datetime
from pymodbus.server.sync import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
from pymodbus.payload import BinaryPayloadBuilder
import paho.mqtt.client as mqtt
import threading

# Configuration
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MODBUS_HOST = os.getenv('MODBUS_HOST', '0.0.0.0')
MODBUS_PORT = int(os.getenv('MODBUS_PORT', 5020))
DEVICE_ID = os.getenv('DEVICE_ID', 'pv-inverter-01')
PEAK_POWER_KW = float(os.getenv('PEAK_POWER_KW', 50))  # 50kW peak
LOCATION_LAT = float(os.getenv('LOCATION_LAT', 52.0907))  # Utrecht, NL
LOCATION_LON = float(os.getenv('LOCATION_LON', 5.1214))

class PVSimulator:
    def __init__(self):
        self.peak_power_kw = PEAK_POWER_KW
        self.current_power_kw = 0
        self.daily_energy_kwh = 0
        self.total_energy_kwh = 0
        self.status = "online"
        self.efficiency = 0.95
        self.temperature_c = 25
        
        # MQTT setup
        self.mqtt_client = mqtt.Client(client_id=DEVICE_ID)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        
        # Modbus data store
        self.setup_modbus_datastore()
        
    def on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        
    def setup_modbus_datastore(self):
        """Initialize Modbus holding registers"""
        # Register map:
        # 0-1: Current Power (W) - 32-bit
        # 2-3: Total Energy (kWh) - 32-bit
        # 4-5: Daily Energy (kWh) - 32-bit
        # 6: Status (0=offline, 1=online, 2=fault)
        # 7: DC Voltage (V * 10)
        # 8: DC Current (A * 10)
        # 9: AC Voltage (V)
        # 10: AC Current (A * 10)
        # 11: Temperature (C * 10)
        
        store = ModbusSlaveContext(
            hr=ModbusSequentialDataBlock(0, [0]*100)
        )
        self.context = ModbusServerContext(slaves=store, single=True)
        
    def calculate_solar_power(self):
        """Calculate realistic solar power based on time of day"""
        now = datetime.now()
        hour = now.hour + now.minute / 60
        
        # Sun curve (gaussian approximation)
        # Peak at solar noon (around 13:00 in Netherlands)
        solar_noon = 13.0
        width = 4.0  # Hours of good sunlight
        
        # Calculate sun elevation factor
        time_from_noon = hour - solar_noon
        sun_factor = math.exp(-(time_from_noon ** 2) / (2 * width ** 2))
        
        # Add weather variability (clouds)
        cloud_factor = 0.7 + 0.3 * random.random()
        
        # Calculate power
        base_power = self.peak_power_kw * sun_factor * cloud_factor * self.efficiency
        
        # Add small random variations
        noise = random.gauss(0, 0.02) * base_power
        power = max(0, base_power + noise)
        
        # Night time (no production)
        if hour < 6 or hour > 21:
            power = 0
            
        return power
    
    def calculate_dc_metrics(self, power_kw):
        """Calculate DC voltage and current from power"""
        # Typical string voltage: 600-800V
        dc_voltage = 700 + random.gauss(0, 10)
        dc_current = (power_kw * 1000) / dc_voltage if dc_voltage > 0 else 0
        return dc_voltage, dc_current
    
    def calculate_ac_metrics(self, power_kw):
        """Calculate AC voltage and current"""
        # Grid voltage: 400V 3-phase
        ac_voltage = 400
        ac_current = (power_kw * 1000) / (math.sqrt(3) * ac_voltage) if ac_voltage > 0 else 0
        return ac_voltage, ac_current
    
    def update_telemetry(self):
        """Update all telemetry values"""
        # Calculate current power
        self.current_power_kw = self.calculate_solar_power()
        
        # Update daily energy (reset at midnight)
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:
            self.daily_energy_kwh = 0
            
        # Update energy counters (every 5 seconds = 1/720 of an hour)
        energy_increment = self.current_power_kw / 720
        self.daily_energy_kwh += energy_increment
        self.total_energy_kwh += energy_increment
        
        # Calculate electrical parameters
        dc_voltage, dc_current = self.calculate_dc_metrics(self.current_power_kw)
        ac_voltage, ac_current = self.calculate_ac_metrics(self.current_power_kw)
        
        # Temperature varies with production
        self.temperature_c = 25 + (self.current_power_kw / self.peak_power_kw) * 30 + random.gauss(0, 2)
        
        return {
            'power_kw': round(self.current_power_kw, 2),
            'daily_energy_kwh': round(self.daily_energy_kwh, 2),
            'total_energy_kwh': round(self.total_energy_kwh, 2),
            'dc_voltage': round(dc_voltage, 1),
            'dc_current': round(dc_current, 1),
            'ac_voltage': round(ac_voltage, 1),
            'ac_current': round(ac_current, 1),
            'temperature_c': round(self.temperature_c, 1),
            'status': self.status
        }
    
    def update_modbus_registers(self, telemetry):
        """Update Modbus holding registers with current values"""
        store = self.context[0].store['h']
        
        # Power (W) as 32-bit integer
        power_w = int(telemetry['power_kw'] * 1000)
        store.setValues(0, [power_w >> 16, power_w & 0xFFFF])
        
        # Total Energy (kWh) as 32-bit integer
        total_kwh = int(telemetry['total_energy_kwh'] * 10)  # 0.1 kWh resolution
        store.setValues(2, [total_kwh >> 16, total_kwh & 0xFFFF])
        
        # Daily Energy (kWh) as 32-bit integer
        daily_kwh = int(telemetry['daily_energy_kwh'] * 10)
        store.setValues(4, [daily_kwh >> 16, daily_kwh & 0xFFFF])
        
        # Status
        status_map = {'offline': 0, 'online': 1, 'fault': 2}
        store.setValues(6, [status_map.get(telemetry['status'], 0)])
        
        # DC Voltage (V * 10)
        store.setValues(7, [int(telemetry['dc_voltage'] * 10)])
        
        # DC Current (A * 10)
        store.setValues(8, [int(telemetry['dc_current'] * 10)])
        
        # AC Voltage (V)
        store.setValues(9, [int(telemetry['ac_voltage'])])
        
        # AC Current (A * 10)
        store.setValues(10, [int(telemetry['ac_current'] * 10)])
        
        # Temperature (C * 10)
        store.setValues(11, [int(telemetry['temperature_c'] * 10)])
    
    def publish_mqtt(self, telemetry):
        """Publish telemetry to MQTT"""
        topic_base = f"orbiteos/devices/{DEVICE_ID}"
        
        # Publish individual values
        for key, value in telemetry.items():
            topic = f"{topic_base}/{key}"
            self.mqtt_client.publish(topic, str(value))
        
        # Publish aggregate JSON
        import json
        self.mqtt_client.publish(
            f"{topic_base}/telemetry",
            json.dumps(telemetry)
        )
    
    def simulation_loop(self):
        """Main simulation loop"""
        print(f"PV Simulator started: {DEVICE_ID}")
        print(f"Peak Power: {self.peak_power_kw} kW")
        print(f"Location: {LOCATION_LAT}, {LOCATION_LON}")
        
        # Connect to MQTT
        try:
            self.mqtt_client.connect(MQTT_BROKER, 1883, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"Could not connect to MQTT: {e}")
        
        while True:
            try:
                # Update telemetry
                telemetry = self.update_telemetry()
                
                # Update Modbus registers
                self.update_modbus_registers(telemetry)
                
                # Publish to MQTT
                self.publish_mqtt(telemetry)
                
                # Log current state
                print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                      f"Power: {telemetry['power_kw']:.2f} kW | "
                      f"Daily: {telemetry['daily_energy_kwh']:.2f} kWh | "
                      f"Temp: {telemetry['temperature_c']:.1f}°C")
                
                time.sleep(5)  # Update every 5 seconds
                
            except Exception as e:
                print(f"Error in simulation loop: {e}")
                time.sleep(5)
    
    def start_modbus_server(self):
        """Start Modbus TCP server"""
        identity = ModbusDeviceIdentification()
        identity.VendorName = 'OrbitEOS'
        identity.ProductCode = 'PV-SIM'
        identity.VendorUrl = 'https://orbiteos.io'
        identity.ProductName = 'PV Inverter Simulator'
        identity.ModelName = f'Generic {int(self.peak_power_kw)}kW'
        identity.MajorMinorRevision = '1.0'
        
        print(f"Starting Modbus server on {MODBUS_HOST}:{MODBUS_PORT}")
        StartTcpServer(
            context=self.context,
            identity=identity,
            address=(MODBUS_HOST, MODBUS_PORT)
        )

if __name__ == "__main__":
    simulator = PVSimulator()
    
    # Start Modbus server in separate thread
    modbus_thread = threading.Thread(target=simulator.start_modbus_server, daemon=True)
    modbus_thread.start()
    
    # Run simulation loop in main thread
    time.sleep(2)  # Wait for Modbus server to start
    simulator.simulation_loop()
