#!/usr/bin/env python3
"""
OrbitEOS Battery Simulator
Simulates a battery energy storage system with realistic charge/discharge behavior
Protocols: Modbus TCP, MQTT
"""

import os
import time
import random
import math
from datetime import datetime
from pymodbus.server.sync import StartTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import ModbusSequentialDataBlock, ModbusSlaveContext, ModbusServerContext
import paho.mqtt.client as mqtt
import threading

# Configuration
MQTT_BROKER = os.getenv('MQTT_BROKER', 'localhost')
MODBUS_HOST = os.getenv('MODBUS_HOST', '0.0.0.0')
MODBUS_PORT = int(os.getenv('MODBUS_PORT', 5021))
DEVICE_ID = os.getenv('DEVICE_ID', 'battery-01')
CAPACITY_KWH = float(os.getenv('CAPACITY_KWH', 100))  # 100kWh capacity
MAX_CHARGE_RATE_KW = float(os.getenv('MAX_CHARGE_RATE_KW', 50))  # 50kW charge
MAX_DISCHARGE_RATE_KW = float(os.getenv('MAX_DISCHARGE_RATE_KW', 50))  # 50kW discharge
INITIAL_SOC = float(os.getenv('INITIAL_SOC', 50))  # 50% initial charge

class BatterySimulator:
    def __init__(self):
        self.capacity_kwh = CAPACITY_KWH
        self.max_charge_rate_kw = MAX_CHARGE_RATE_KW
        self.max_discharge_rate_kw = MAX_DISCHARGE_RATE_KW
        
        # Battery state
        self.soc_percent = INITIAL_SOC  # State of Charge
        self.soh_percent = 100  # State of Health
        self.current_power_kw = 0  # Positive = charging, Negative = discharging
        self.voltage = 800  # DC voltage
        self.temperature_c = 25
        self.cycle_count = 0
        self.status = "idle"  # idle, charging, discharging, fault
        
        # Energy counters
        self.total_charged_kwh = 0
        self.total_discharged_kwh = 0
        
        # Control setpoint (can be set via Modbus)
        self.power_setpoint_kw = 0
        
        # MQTT setup
        self.mqtt_client = mqtt.Client(client_id=DEVICE_ID)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        
        # Modbus data store
        self.setup_modbus_datastore()
        
    def on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to control topic
        client.subscribe(f"orbiteos/devices/{DEVICE_ID}/control/#")
        client.message_callback_add(
            f"orbiteos/devices/{DEVICE_ID}/control/power_setpoint",
            self.on_power_setpoint
        )
        
    def on_power_setpoint(self, client, userdata, msg):
        """Handle power setpoint changes from MQTT"""
        try:
            setpoint = float(msg.payload.decode())
            self.power_setpoint_kw = max(
                -self.max_discharge_rate_kw,
                min(self.max_charge_rate_kw, setpoint)
            )
            print(f"Power setpoint changed to: {self.power_setpoint_kw} kW")
        except Exception as e:
            print(f"Error processing power setpoint: {e}")
    
    def setup_modbus_datastore(self):
        """Initialize Modbus holding registers"""
        # Register map:
        # 0-1: Current Power (W) - 32-bit signed (+ charge, - discharge)
        # 2: SOC (% * 10)
        # 3: SOH (% * 10)
        # 4-5: Total Charged Energy (kWh * 10) - 32-bit
        # 6-7: Total Discharged Energy (kWh * 10) - 32-bit
        # 8: Status (0=idle, 1=charging, 2=discharging, 3=fault)
        # 9: Voltage (V)
        # 10: Current (A * 10)
        # 11: Temperature (C * 10)
        # 12-13: Power Setpoint (W) - 32-bit signed (writable)
        # 14: Cycle Count
        
        store = ModbusSlaveContext(
            hr=ModbusSequentialDataBlock(0, [0]*100)
        )
        self.context = ModbusServerContext(slaves=store, single=True)
        
    def calculate_charge_discharge(self, power_setpoint_kw, dt_hours):
        """
        Calculate battery charge/discharge based on setpoint
        Returns actual power (may be limited by SOC)
        """
        # Check SOC limits
        if self.soc_percent >= 100 and power_setpoint_kw > 0:
            return 0  # Can't charge beyond 100%
        if self.soc_percent <= 5 and power_setpoint_kw < 0:
            return 0  # Don't discharge below 5% (protection)
        
        # Apply efficiency losses
        efficiency = 0.95 if power_setpoint_kw > 0 else 0.92
        
        # Calculate energy change
        energy_change_kwh = power_setpoint_kw * dt_hours * efficiency
        
        # Update SOC
        new_soc = self.soc_percent + (energy_change_kwh / self.capacity_kwh * 100)
        
        # Clamp SOC
        if new_soc > 100:
            # Reduce power to not exceed 100% SOC
            max_energy = (100 - self.soc_percent) / 100 * self.capacity_kwh
            actual_power = max_energy / dt_hours / efficiency if dt_hours > 0 else 0
            new_soc = 100
        elif new_soc < 5:
            # Reduce power to not go below 5% SOC
            max_energy = (self.soc_percent - 5) / 100 * self.capacity_kwh
            actual_power = -max_energy / dt_hours / efficiency if dt_hours > 0 else 0
            new_soc = 5
        else:
            actual_power = power_setpoint_kw
        
        self.soc_percent = new_soc
        
        # Update energy counters
        if actual_power > 0:
            self.total_charged_kwh += abs(actual_power * dt_hours)
        elif actual_power < 0:
            self.total_discharged_kwh += abs(actual_power * dt_hours)
        
        # Update cycle count (full discharge-charge = 1 cycle)
        cycle_increment = abs(actual_power * dt_hours) / (2 * self.capacity_kwh)
        self.cycle_count += cycle_increment
        
        # Degrade SOH based on cycles (0.01% per 100 cycles)
        self.soh_percent = 100 - (self.cycle_count / 100) * 0.01
        
        return actual_power
    
    def calculate_voltage_current(self, power_kw):
        """Calculate voltage and current from power and SOC"""
        # Voltage varies slightly with SOC (nominal 800V)
        # Higher at high SOC, lower at low SOC
        soc_factor = 0.9 + 0.2 * (self.soc_percent / 100)
        self.voltage = 800 * soc_factor + random.gauss(0, 5)
        
        # Calculate current from power
        current = (power_kw * 1000) / self.voltage if self.voltage > 0 else 0
        
        return self.voltage, current
    
    def calculate_temperature(self, power_kw):
        """Calculate battery temperature based on power throughput"""
        # Temperature increases with power throughput
        ambient_temp = 25
        thermal_factor = abs(power_kw) / max(self.max_charge_rate_kw, self.max_discharge_rate_kw)
        
        # Target temperature based on load
        target_temp = ambient_temp + thermal_factor * 15
        
        # Gradual temperature change (thermal inertia)
        temp_change_rate = 0.1
        temp_diff = target_temp - self.temperature_c
        self.temperature_c += temp_diff * temp_change_rate + random.gauss(0, 0.5)
        
        return self.temperature_c
    
    def update_status(self, power_kw):
        """Update battery status based on current operation"""
        if abs(power_kw) < 0.1:
            self.status = "idle"
        elif power_kw > 0:
            self.status = "charging"
        else:
            self.status = "discharging"
        
        # Random fault simulation (very rare)
        if random.random() < 0.0001 and self.status != "fault":
            self.status = "fault"
            print("⚠️  Battery fault detected!")
        
        return self.status
    
    def update_telemetry(self, dt_seconds=5):
        """Update all telemetry values"""
        dt_hours = dt_seconds / 3600
        
        # Read setpoint from Modbus if changed
        store = self.context[0].store['h']
        setpoint_high = store.getValues(12, 1)[0]
        setpoint_low = store.getValues(13, 1)[0]
        setpoint_w = (setpoint_high << 16) | setpoint_low
        # Convert from unsigned to signed
        if setpoint_w & 0x80000000:
            setpoint_w -= 0x100000000
        self.power_setpoint_kw = setpoint_w / 1000
        
        # Calculate charge/discharge
        self.current_power_kw = self.calculate_charge_discharge(
            self.power_setpoint_kw,
            dt_hours
        )
        
        # Calculate electrical parameters
        voltage, current = self.calculate_voltage_current(self.current_power_kw)
        temperature = self.calculate_temperature(self.current_power_kw)
        status = self.update_status(self.current_power_kw)
        
        return {
            'power_kw': round(self.current_power_kw, 2),
            'soc_percent': round(self.soc_percent, 1),
            'soh_percent': round(self.soh_percent, 1),
            'voltage': round(voltage, 1),
            'current': round(current, 1),
            'temperature_c': round(temperature, 1),
            'status': status,
            'total_charged_kwh': round(self.total_charged_kwh, 2),
            'total_discharged_kwh': round(self.total_discharged_kwh, 2),
            'cycle_count': round(self.cycle_count, 2),
            'capacity_kwh': self.capacity_kwh
        }
    
    def update_modbus_registers(self, telemetry):
        """Update Modbus holding registers"""
        store = self.context[0].store['h']
        
        # Current Power (W) as 32-bit signed integer
        power_w = int(telemetry['power_kw'] * 1000)
        if power_w < 0:
            power_w += 0x100000000  # Convert to unsigned representation
        store.setValues(0, [power_w >> 16, power_w & 0xFFFF])
        
        # SOC (% * 10)
        store.setValues(2, [int(telemetry['soc_percent'] * 10)])
        
        # SOH (% * 10)
        store.setValues(3, [int(telemetry['soh_percent'] * 10)])
        
        # Total Charged Energy (kWh * 10)
        charged = int(telemetry['total_charged_kwh'] * 10)
        store.setValues(4, [charged >> 16, charged & 0xFFFF])
        
        # Total Discharged Energy (kWh * 10)
        discharged = int(telemetry['total_discharged_kwh'] * 10)
        store.setValues(6, [discharged >> 16, discharged & 0xFFFF])
        
        # Status
        status_map = {'idle': 0, 'charging': 1, 'discharging': 2, 'fault': 3}
        store.setValues(8, [status_map.get(telemetry['status'], 0)])
        
        # Voltage (V)
        store.setValues(9, [int(telemetry['voltage'])])
        
        # Current (A * 10)
        store.setValues(10, [int(telemetry['current'] * 10)])
        
        # Temperature (C * 10)
        store.setValues(11, [int(telemetry['temperature_c'] * 10)])
        
        # Cycle Count
        store.setValues(14, [int(telemetry['cycle_count'])])
    
    def publish_mqtt(self, telemetry):
        """Publish telemetry to MQTT"""
        topic_base = f"orbiteos/devices/{DEVICE_ID}"
        
        for key, value in telemetry.items():
            topic = f"{topic_base}/{key}"
            self.mqtt_client.publish(topic, str(value))
        
        import json
        self.mqtt_client.publish(
            f"{topic_base}/telemetry",
            json.dumps(telemetry)
        )
    
    def simulation_loop(self):
        """Main simulation loop"""
        print(f"Battery Simulator started: {DEVICE_ID}")
        print(f"Capacity: {self.capacity_kwh} kWh")
        print(f"Max Charge Rate: {self.max_charge_rate_kw} kW")
        print(f"Max Discharge Rate: {self.max_discharge_rate_kw} kW")
        print(f"Initial SOC: {self.soc_percent}%")
        
        # Connect to MQTT
        try:
            self.mqtt_client.connect(MQTT_BROKER, 1883, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"Could not connect to MQTT: {e}")
        
        while True:
            try:
                telemetry = self.update_telemetry(dt_seconds=5)
                self.update_modbus_registers(telemetry)
                self.publish_mqtt(telemetry)
                
                # Log with emoji indicators
                direction = "⚡" if telemetry['power_kw'] > 0 else "🔋" if telemetry['power_kw'] < 0 else "⏸️ "
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {direction} "
                      f"Power: {telemetry['power_kw']:+.2f} kW | "
                      f"SOC: {telemetry['soc_percent']:.1f}% | "
                      f"Status: {telemetry['status']}")
                
                time.sleep(5)
                
            except Exception as e:
                print(f"Error in simulation loop: {e}")
                time.sleep(5)
    
    def start_modbus_server(self):
        """Start Modbus TCP server"""
        identity = ModbusDeviceIdentification()
        identity.VendorName = 'OrbitEOS'
        identity.ProductCode = 'BESS-SIM'
        identity.VendorUrl = 'https://orbiteos.io'
        identity.ProductName = 'Battery Storage Simulator'
        identity.ModelName = f'Generic {int(self.capacity_kwh)}kWh'
        identity.MajorMinorRevision = '1.0'
        
        print(f"Starting Modbus server on {MODBUS_HOST}:{MODBUS_PORT}")
        StartTcpServer(
            context=self.context,
            identity=identity,
            address=(MODBUS_HOST, MODBUS_PORT)
        )

if __name__ == "__main__":
    simulator = BatterySimulator()
    
    modbus_thread = threading.Thread(target=simulator.start_modbus_server, daemon=True)
    modbus_thread.start()
    
    time.sleep(2)
    simulator.simulation_loop()
