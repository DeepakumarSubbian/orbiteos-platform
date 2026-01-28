#!/usr/bin/env python3
"""
OrbitEOS Modbus TCP Server
Unified Modbus server for all device simulators with MQTT telemetry publishing.

Modbus Unit IDs:
- Unit 1: Solar/PV Inverter
- Unit 2: Battery ESS
- Unit 3: Grid Meter
- Unit 4: EV Charger
"""

import os
import asyncio
import logging
import json
import time
from datetime import datetime
from typing import Dict, Any

import pytz
from pymodbus.server import StartAsyncTcpServer
from pymodbus.device import ModbusDeviceIdentification
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusSlaveContext,
    ModbusServerContext
)
import paho.mqtt.client as mqtt

from solar_simulator import SolarSimulator
from battery_simulator import BatterySimulator
from grid_simulator import GridSimulator
from ev_simulator import EVChargerSimulator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("orbiteos-simulators")

# Environment configuration
LATITUDE = float(os.getenv("LATITUDE", "52.3676"))
LONGITUDE = float(os.getenv("LONGITUDE", "4.9041"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Amsterdam")
SOLAR_PEAK_POWER_KW = float(os.getenv("SOLAR_PEAK_POWER_KW", "6.0"))
BATTERY_CAPACITY_KWH = float(os.getenv("BATTERY_CAPACITY_KWH", "13.5"))
EV_CHARGER_POWER_KW = float(os.getenv("EV_CHARGER_POWER_KW", "11"))
MQTT_BROKER = os.getenv("MQTT_BROKER", "mqtt://mqtt:1883")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))

# Parse MQTT broker URL
mqtt_host = MQTT_BROKER.replace("mqtt://", "").split(":")[0]
mqtt_port = int(MQTT_BROKER.replace("mqtt://", "").split(":")[1]) if ":" in MQTT_BROKER.replace("mqtt://", "") else 1883


class ModbusSimulatorServer:
    """
    Modbus TCP Server that integrates all device simulators.
    Provides OpenEMS-compatible register mappings.
    """

    # Register mappings (OpenEMS SunSpec-style)
    # Solar registers (Unit 1) - Holding Registers 40000+
    SOLAR_POWER_REG = 0          # Active power (W) - INT32
    SOLAR_ENERGY_REG = 2         # Total energy (Wh) - UINT32
    SOLAR_VOLTAGE_REG = 4        # DC voltage (V * 10)
    SOLAR_CURRENT_REG = 5        # DC current (A * 10)
    SOLAR_STATUS_REG = 6         # Status (0=off, 1=on, 2=fault)

    # Battery registers (Unit 2) - Holding Registers 40000+
    BATTERY_SOC_REG = 0          # State of charge (%)
    BATTERY_POWER_REG = 1        # Active power (W) - positive=discharge
    BATTERY_VOLTAGE_REG = 3      # Voltage (V * 10)
    BATTERY_CURRENT_REG = 4      # Current (A * 10)
    BATTERY_TEMP_REG = 5         # Temperature (C * 10)
    BATTERY_STATUS_REG = 6       # Status
    BATTERY_CAPACITY_REG = 7     # Usable capacity (Wh)
    BATTERY_CHARGE_LIMIT_REG = 9 # Max charge power (W)
    BATTERY_DISCHARGE_LIMIT_REG = 11  # Max discharge power (W)

    # Grid meter registers (Unit 3) - Holding Registers 40000+
    GRID_POWER_REG = 0           # Active power (W) - positive=import
    GRID_REACTIVE_REG = 2        # Reactive power (VAr)
    GRID_VOLTAGE_L1_REG = 4      # L1 voltage (V * 10)
    GRID_VOLTAGE_L2_REG = 5      # L2 voltage (V * 10)
    GRID_VOLTAGE_L3_REG = 6      # L3 voltage (V * 10)
    GRID_CURRENT_L1_REG = 7      # L1 current (A * 100)
    GRID_CURRENT_L2_REG = 8      # L2 current (A * 100)
    GRID_CURRENT_L3_REG = 9      # L3 current (A * 100)
    GRID_FREQUENCY_REG = 10      # Frequency (Hz * 100)
    GRID_IMPORT_ENERGY_REG = 11  # Import energy (Wh) - UINT32
    GRID_EXPORT_ENERGY_REG = 13  # Export energy (Wh) - UINT32

    # EV charger registers (Unit 4) - Holding Registers 40000+
    EV_POWER_REG = 0             # Charging power (W)
    EV_ENERGY_REG = 2            # Session energy (Wh)
    EV_SOC_REG = 4               # Vehicle SOC (%)
    EV_STATUS_REG = 5            # Status (0=available, 1=preparing, 2=charging, 3=finished)
    EV_MAX_POWER_REG = 6         # Max power (W)
    EV_CURRENT_LIMIT_REG = 8     # Current limit (A * 10)

    def __init__(self):
        """Initialize all simulators and Modbus context."""
        self.tz = pytz.timezone(TIMEZONE)

        # Initialize simulators
        self.solar = SolarSimulator(
            latitude=LATITUDE,
            longitude=LONGITUDE,
            peak_power_kw=SOLAR_PEAK_POWER_KW,
            timezone=TIMEZONE
        )

        self.battery = BatterySimulator(
            capacity_kwh=BATTERY_CAPACITY_KWH,
            max_power_kw=5.0,
            initial_soc=50.0
        )

        self.grid = GridSimulator()

        self.ev = EVChargerSimulator(
            max_power_kw=EV_CHARGER_POWER_KW
        )

        # Energy accumulators
        self.solar_energy_wh = 0.0
        self.last_update = time.time()

        # Create Modbus data stores for each unit
        self.stores = self._create_stores()

        # MQTT client
        self.mqtt_client = mqtt.Client(client_id="orbiteos-simulators")
        self.mqtt_connected = False

        logger.info(f"Initialized simulators for location: {LATITUDE}, {LONGITUDE}")
        logger.info(f"Solar: {SOLAR_PEAK_POWER_KW} kW, Battery: {BATTERY_CAPACITY_KWH} kWh, EV: {EV_CHARGER_POWER_KW} kW")

    def _create_stores(self) -> Dict[int, ModbusSlaveContext]:
        """Create Modbus slave contexts for each unit."""
        stores = {}

        for unit_id in [1, 2, 3, 4]:
            # Create data blocks with 100 registers each
            # di = discrete inputs, co = coils, hr = holding registers, ir = input registers
            stores[unit_id] = ModbusSlaveContext(
                di=ModbusSequentialDataBlock(0, [0] * 100),
                co=ModbusSequentialDataBlock(0, [0] * 100),
                hr=ModbusSequentialDataBlock(0, [0] * 100),
                ir=ModbusSequentialDataBlock(0, [0] * 100)
            )

        return stores

    def _int32_to_registers(self, value: int) -> tuple:
        """Convert signed 32-bit integer to two 16-bit registers (big endian)."""
        if value < 0:
            value = value + 0x100000000
        return ((value >> 16) & 0xFFFF, value & 0xFFFF)

    def _uint32_to_registers(self, value: int) -> tuple:
        """Convert unsigned 32-bit integer to two 16-bit registers (big endian)."""
        value = int(value) & 0xFFFFFFFF
        return ((value >> 16) & 0xFFFF, value & 0xFFFF)

    def update_solar_registers(self):
        """Update solar/PV inverter registers."""
        now = datetime.now(self.tz)
        status = self.solar.get_current_status()
        power_w = int(status['power_w'])

        # Update energy accumulator
        current_time = time.time()
        dt_hours = (current_time - self.last_update) / 3600.0
        self.solar_energy_wh += power_w * dt_hours

        store = self.stores[1]
        hr = store.getValues(3, 0, 100)  # Get holding registers

        # Power (INT32)
        high, low = self._int32_to_registers(power_w)
        hr[self.SOLAR_POWER_REG] = high
        hr[self.SOLAR_POWER_REG + 1] = low

        # Energy (UINT32)
        high, low = self._uint32_to_registers(int(self.solar_energy_wh))
        hr[self.SOLAR_ENERGY_REG] = high
        hr[self.SOLAR_ENERGY_REG + 1] = low

        # Voltage (simulated DC bus voltage ~400V)
        hr[self.SOLAR_VOLTAGE_REG] = int(380 + (power_w / 1000) * 20) * 10

        # Current
        voltage = hr[self.SOLAR_VOLTAGE_REG] / 10
        hr[self.SOLAR_CURRENT_REG] = int((power_w / voltage) * 10) if voltage > 0 else 0

        # Status
        hr[self.SOLAR_STATUS_REG] = 1 if power_w > 0 else 0

        store.setValues(3, 0, hr)

        return {
            'power_w': power_w,
            'energy_wh': int(self.solar_energy_wh),
            'voltage_v': hr[self.SOLAR_VOLTAGE_REG] / 10,
            'current_a': hr[self.SOLAR_CURRENT_REG] / 10,
            'status': hr[self.SOLAR_STATUS_REG]
        }

    def update_battery_registers(self, solar_power_w: int, load_power_w: int):
        """Update battery ESS registers."""
        # Calculate net power (positive = need to discharge, negative = can charge)
        net_power = load_power_w - solar_power_w

        # Update battery simulation
        status = self.battery.update(net_power / 1000.0, 1.0)  # 1 second interval

        store = self.stores[2]
        hr = store.getValues(3, 0, 100)

        # SOC
        hr[self.BATTERY_SOC_REG] = int(status['soc'])

        # Power (INT32) - positive = discharge, negative = charge
        power_w = int(status['power_kw'] * 1000)
        high, low = self._int32_to_registers(power_w)
        hr[self.BATTERY_POWER_REG] = high
        hr[self.BATTERY_POWER_REG + 1] = low

        # Voltage (~50V battery pack)
        hr[self.BATTERY_VOLTAGE_REG] = int(status['voltage'] * 10)

        # Current
        hr[self.BATTERY_CURRENT_REG] = int(status['current'] * 10)

        # Temperature
        hr[self.BATTERY_TEMP_REG] = int(status['temperature'] * 10)

        # Status (0=standby, 1=charging, 2=discharging, 3=fault)
        if abs(power_w) < 50:
            hr[self.BATTERY_STATUS_REG] = 0  # Standby
        elif power_w < 0:
            hr[self.BATTERY_STATUS_REG] = 1  # Charging
        else:
            hr[self.BATTERY_STATUS_REG] = 2  # Discharging

        # Capacity
        capacity_wh = int(status['capacity_kwh'] * 1000)
        high, low = self._uint32_to_registers(capacity_wh)
        hr[self.BATTERY_CAPACITY_REG] = high
        hr[self.BATTERY_CAPACITY_REG + 1] = low

        # Charge/discharge limits
        high, low = self._int32_to_registers(int(status['max_charge_power_kw'] * 1000))
        hr[self.BATTERY_CHARGE_LIMIT_REG] = high
        hr[self.BATTERY_CHARGE_LIMIT_REG + 1] = low

        high, low = self._int32_to_registers(int(status['max_discharge_power_kw'] * 1000))
        hr[self.BATTERY_DISCHARGE_LIMIT_REG] = high
        hr[self.BATTERY_DISCHARGE_LIMIT_REG + 1] = low

        store.setValues(3, 0, hr)

        return {
            'soc': status['soc'],
            'power_w': power_w,
            'voltage_v': status['voltage'],
            'current_a': status['current'],
            'temperature_c': status['temperature'],
            'status': hr[self.BATTERY_STATUS_REG]
        }

    def update_grid_registers(self, net_power_w: int):
        """Update grid meter registers."""
        status = self.grid.update(net_power_w)

        store = self.stores[3]
        hr = store.getValues(3, 0, 100)

        # Power (INT32) - positive = import, negative = export
        high, low = self._int32_to_registers(int(status['power_w']))
        hr[self.GRID_POWER_REG] = high
        hr[self.GRID_POWER_REG + 1] = low

        # Reactive power
        high, low = self._int32_to_registers(int(status['reactive_power_var']))
        hr[self.GRID_REACTIVE_REG] = high
        hr[self.GRID_REACTIVE_REG + 1] = low

        # Voltages (3-phase)
        hr[self.GRID_VOLTAGE_L1_REG] = int(status['voltage_l1'] * 10)
        hr[self.GRID_VOLTAGE_L2_REG] = int(status['voltage_l2'] * 10)
        hr[self.GRID_VOLTAGE_L3_REG] = int(status['voltage_l3'] * 10)

        # Currents (3-phase)
        hr[self.GRID_CURRENT_L1_REG] = int(status['current_l1'] * 100)
        hr[self.GRID_CURRENT_L2_REG] = int(status['current_l2'] * 100)
        hr[self.GRID_CURRENT_L3_REG] = int(status['current_l3'] * 100)

        # Frequency
        hr[self.GRID_FREQUENCY_REG] = int(status['frequency'] * 100)

        # Energy counters
        high, low = self._uint32_to_registers(int(status['import_energy_wh']))
        hr[self.GRID_IMPORT_ENERGY_REG] = high
        hr[self.GRID_IMPORT_ENERGY_REG + 1] = low

        high, low = self._uint32_to_registers(int(status['export_energy_wh']))
        hr[self.GRID_EXPORT_ENERGY_REG] = high
        hr[self.GRID_EXPORT_ENERGY_REG + 1] = low

        store.setValues(3, 0, hr)

        return {
            'power_w': status['power_w'],
            'voltage_v': status['voltage_l1'],
            'frequency_hz': status['frequency'],
            'import_energy_wh': status['import_energy_wh'],
            'export_energy_wh': status['export_energy_wh']
        }

    def update_ev_registers(self):
        """Update EV charger registers."""
        status = self.ev.update()

        store = self.stores[4]
        hr = store.getValues(3, 0, 100)

        # Power (INT32)
        high, low = self._int32_to_registers(int(status['power_w']))
        hr[self.EV_POWER_REG] = high
        hr[self.EV_POWER_REG + 1] = low

        # Session energy
        high, low = self._uint32_to_registers(int(status['session_energy_wh']))
        hr[self.EV_ENERGY_REG] = high
        hr[self.EV_ENERGY_REG + 1] = low

        # Vehicle SOC
        hr[self.EV_SOC_REG] = int(status['vehicle_soc'])

        # Status
        hr[self.EV_STATUS_REG] = status['status_code']

        # Max power
        high, low = self._int32_to_registers(int(status['max_power_w']))
        hr[self.EV_MAX_POWER_REG] = high
        hr[self.EV_MAX_POWER_REG + 1] = low

        # Current limit
        hr[self.EV_CURRENT_LIMIT_REG] = int(status['current_limit_a'] * 10)

        store.setValues(3, 0, hr)

        return {
            'power_w': status['power_w'],
            'session_energy_wh': status['session_energy_wh'],
            'vehicle_soc': status['vehicle_soc'],
            'status': status['status'],
            'status_code': status['status_code']
        }

    def setup_mqtt(self):
        """Setup MQTT connection."""
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                self.mqtt_connected = True
                logger.info(f"Connected to MQTT broker at {mqtt_host}:{mqtt_port}")
            else:
                logger.error(f"Failed to connect to MQTT: {rc}")

        def on_disconnect(client, userdata, rc):
            self.mqtt_connected = False
            logger.warning("Disconnected from MQTT broker")

        self.mqtt_client.on_connect = on_connect
        self.mqtt_client.on_disconnect = on_disconnect

        try:
            self.mqtt_client.connect_async(mqtt_host, mqtt_port, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")

    def publish_telemetry(self, telemetry: Dict[str, Any]):
        """Publish telemetry to MQTT."""
        if not self.mqtt_connected:
            return

        timestamp = datetime.now(self.tz).isoformat()

        try:
            # Publish individual device topics
            for device, data in telemetry.items():
                topic = f"orbiteos/devices/{device}/telemetry"
                payload = json.dumps({
                    'timestamp': timestamp,
                    'device': device,
                    'data': data
                })
                self.mqtt_client.publish(topic, payload, qos=1)

            # Publish combined system status
            system_topic = "orbiteos/system/status"
            system_payload = json.dumps({
                'timestamp': timestamp,
                'solar_power_w': telemetry.get('solar', {}).get('power_w', 0),
                'battery_soc': telemetry.get('battery', {}).get('soc', 0),
                'battery_power_w': telemetry.get('battery', {}).get('power_w', 0),
                'grid_power_w': telemetry.get('grid', {}).get('power_w', 0),
                'ev_power_w': telemetry.get('ev', {}).get('power_w', 0),
                'home_consumption_w': self._calculate_consumption(telemetry)
            })
            self.mqtt_client.publish(system_topic, system_payload, qos=1)

        except Exception as e:
            logger.error(f"Failed to publish MQTT telemetry: {e}")

    def _calculate_consumption(self, telemetry: Dict[str, Any]) -> int:
        """Calculate home consumption from power flows."""
        solar = telemetry.get('solar', {}).get('power_w', 0)
        battery = telemetry.get('battery', {}).get('power_w', 0)  # positive = discharge
        grid = telemetry.get('grid', {}).get('power_w', 0)  # positive = import
        ev = telemetry.get('ev', {}).get('power_w', 0)

        # Consumption = Solar + Battery_discharge + Grid_import - EV
        consumption = solar + battery + grid - ev
        return max(0, int(consumption))

    async def update_loop(self):
        """Main update loop for all simulators."""
        logger.info("Starting simulator update loop")

        # Simulated base load (house consumption)
        base_load_w = 800

        while True:
            try:
                # Update solar
                solar_data = self.update_solar_registers()

                # Update EV (may add to load)
                ev_data = self.update_ev_registers()

                # Total load = base + EV
                total_load_w = base_load_w + ev_data['power_w']

                # Update battery (manages solar excess or deficit)
                battery_data = self.update_battery_registers(
                    solar_data['power_w'],
                    total_load_w
                )

                # Calculate grid power (what's left after battery)
                # Grid = Load - Solar - Battery_discharge
                net_grid_w = total_load_w - solar_data['power_w'] - battery_data['power_w']

                # Update grid meter
                grid_data = self.update_grid_registers(int(net_grid_w))

                # Publish telemetry
                telemetry = {
                    'solar': solar_data,
                    'battery': battery_data,
                    'grid': grid_data,
                    'ev': ev_data
                }
                self.publish_telemetry(telemetry)

                self.last_update = time.time()

                # Log summary every 10 seconds
                if int(time.time()) % 10 == 0:
                    logger.info(
                        f"Solar: {solar_data['power_w']}W | "
                        f"Battery: {battery_data['soc']}% ({battery_data['power_w']}W) | "
                        f"Grid: {grid_data['power_w']}W | "
                        f"EV: {ev_data['power_w']}W"
                    )

            except Exception as e:
                logger.error(f"Error in update loop: {e}")

            await asyncio.sleep(1.0)

    async def run(self):
        """Run the Modbus server."""
        # Setup MQTT
        self.setup_mqtt()

        # Create server context with all unit stores
        context = ModbusServerContext(slaves=self.stores, single=False)

        # Device identification
        identity = ModbusDeviceIdentification()
        identity.VendorName = 'OrbitEOS'
        identity.ProductCode = 'ORBITEOS-SIM'
        identity.VendorUrl = 'https://orbiteos.io'
        identity.ProductName = 'OrbitEOS Device Simulator'
        identity.ModelName = 'Multi-Device Simulator'
        identity.MajorMinorRevision = '1.0.0'

        # Start update loop
        update_task = asyncio.create_task(self.update_loop())

        logger.info(f"Starting Modbus TCP Server on port {MODBUS_PORT}")
        logger.info("Unit IDs: 1=Solar, 2=Battery, 3=Grid, 4=EV")

        try:
            await StartAsyncTcpServer(
                context=context,
                identity=identity,
                address=("0.0.0.0", MODBUS_PORT)
            )
        except Exception as e:
            logger.error(f"Modbus server error: {e}")
            update_task.cancel()
            raise


async def main():
    """Main entry point."""
    server = ModbusSimulatorServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
