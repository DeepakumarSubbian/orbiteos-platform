# OpenEMS Compatibility Guide for OrbitEOS Simulators

## OpenEMS Device Support Overview

Based on OpenEMS documentation and source code, OpenEMS Edge supports these device categories:

### 1. **Energy Storage System (ESS) / Battery**
- **Protocol:** Modbus TCP/RTU
- **OpenEMS Component:** `Battery.Fenecon.Home`, `Ess.Generic.ManagedSymmetric`
- **Key Channels:**
  - `Soc` - State of Charge (%)
  - `Capacity` - Capacity (Wh)
  - `ActivePower` - Current power (W, + = charging)
  - `MaxApparentPower` - Max power (W)
  - `GridMode` - On-grid/Off-grid
  - `AllowedChargePower` - Max charge power
  - `AllowedDischargePower` - Max discharge power

### 2. **PV Inverter / Solar**
- **Protocol:** Modbus TCP/RTU, SunSpec
- **OpenEMS Component:** `PvInverter.SolarEdge`, `PvInverter.Kostal`, `PvInverter.Fronius`
- **Key Channels:**
  - `ActivePower` - Current production (W)
  - `MaxActivePower` - Peak power (W)
  - `Voltage` - DC voltage (V)
  - `Current` - DC current (A)
  - `Energy` - Total energy (Wh)

### 3. **Grid Meter**
- **Protocol:** Modbus TCP/RTU
- **OpenEMS Component:** `Meter.Janitza.UMG96RM`, `Meter.Socomec.Threephase`
- **Key Channels:**
  - `ActivePower` - Grid power (W, + = import, - = export)
  - `ActivePowerL1/L2/L3` - Per-phase power
  - `Voltage` - Grid voltage (V)
  - `Frequency` - Grid frequency (Hz)
  - `ActiveProductionEnergy` - Export energy (Wh)
  - `ActiveConsumptionEnergy` - Import energy (Wh)

### 4. **EV Charging Station (EVCS)**
- **Protocol:** OCPP 1.6 / 2.0.1
- **OpenEMS Component:** `Evcs.Keba.KeContact`, `Evcs.Ocpp`
- **Key Channels:**
  - `ChargePower` - Current charge power (W)
  - `MaximumPower` - Max available power (W)
  - `Status` - Charging status
  - `EnergySession` - Session energy (Wh)
  - `Phases` - Number of phases

### 5. **Controllable Loads (Heat Pump, HVAC)**
- **Protocol:** Modbus TCP/RTU
- **OpenEMS Component:** `Controller.Io.HeatingElement`, `Controller.Io.Relay`
- **Key Channels:**
  - `ActivePower` - Current power (W)
  - `Enabled` - On/Off state
  - `SetPoint` - Temperature setpoint
  - `Temperature` - Current temperature

### 6. **Additional Devices Supported:**
- Weather Station (Modbus)
- Industrial Machines (Modbus)
- Smart Meters (Modbus, M-Bus)
- Generators (Modbus)
- UPS Systems (Modbus)

---

## Recommended Simulator Approach for OrbitEOS

### **Option 1: Modbus TCP Simulators (RECOMMENDED)**
- ✅ Most flexible
- ✅ Works with all OpenEMS components
- ✅ Easy to test
- ✅ Industry standard
- ✅ No device-specific protocol implementation needed

### **Option 2: MQTT Bridge**
- ✅ Lightweight
- ✅ Easy to implement
- ⚠️ Requires OpenEMS MQTT component configuration
- ⚠️ Less standardized

### **Option 3: REST API**
- ✅ Simple HTTP calls
- ⚠️ OpenEMS REST API is more for monitoring/control than device simulation
- ❌ Not ideal for real-time device simulation

---

## OrbitEOS Simulator Architecture

```
OrbitEOS Simulators
├── Modbus TCP Server (Port 502 or custom)
│   ├── Solar PV (Holding Registers 0-99)
│   ├── Battery (Holding Registers 100-199)
│   ├── Grid Meter (Holding Registers 200-299)
│   ├── EV Charger (Holding Registers 300-399)
│   ├── Heat Pump (Holding Registers 400-499)
│   └── Base Load (Holding Registers 500-599)
│
├── MQTT Publisher (Backup/Telemetry)
│   ├── Publishes all device states
│   ├── Topics: orbiteos/solar/power
│   └── Used by OrbitEOS API and LLM
│
└── OpenEMS Edge Connection
    └── Reads Modbus registers
    └── Controls devices via Modbus writes
```

---

## Implementation: Modbus TCP Device Simulators

Each simulator will:
1. **Run Modbus TCP server** on unique ports or unit IDs
2. **Expose standard registers** (compatible with OpenEMS)
3. **Update values realistically** (solar follows sun, battery charges/discharges)
4. **Publish to MQTT** (for OrbitEOS monitoring)
5. **Accept commands** from OpenEMS (battery charge power, EV charge rate)

---

## Modbus Register Map for OrbitEOS Simulators

### Solar PV Inverter (Unit ID 1)
```
Holding Registers (Read/Write):
  0: Max Power Limit (W)
  1: Enable/Disable

Input Registers (Read-only):
  0: Active Power (W) - Current production
  1: DC Voltage (0.1V)
  2: DC Current (0.1A)
  3: AC Voltage (0.1V)
  4: AC Current (0.1A)
  5: Total Energy (kWh)
  6: Daily Energy (Wh)
  7: Inverter Temperature (0.1°C)
  8: Status (0=OK, 1=Warning, 2=Fault)
```

### Battery ESS (Unit ID 2)
```
Holding Registers (Read/Write):
  0: Power Setpoint (W, signed, +=charge)
  1: Max Charge Power (W)
  2: Max Discharge Power (W)
  3: Min SOC (%)
  4: Max SOC (%)
  5: Enable/Disable

Input Registers (Read-only):
  0: State of Charge (%)
  1: State of Health (%)
  2: Voltage (0.1V)
  3: Current (0.1A, signed)
  4: Power (W, signed, +=charging)
  5: Capacity (Wh)
  6: Energy (Wh)
  7: Temperature (0.1°C)
  8: Status
  9: Cycles
```

### Grid Meter (Unit ID 3)
```
Input Registers (Read-only):
  0: Active Power (W, signed, +=import)
  1: Active Power L1 (W)
  2: Active Power L2 (W)
  3: Active Power L3 (W)
  4: Voltage L1 (0.1V)
  5: Voltage L2 (0.1V)
  6: Voltage L3 (0.1V)
  7: Current L1 (0.1A)
  8: Current L2 (0.1A)
  9: Current L3 (0.1A)
  10: Frequency (0.01Hz)
  11: Import Energy (kWh)
  12: Export Energy (kWh)
  13: Power Factor (0.001)
```

### EV Charger (Unit ID 4)
```
Holding Registers (Read/Write):
  0: Charge Current Limit (0.1A)
  1: Enable/Disable
  2: Phases (1 or 3)

Input Registers (Read-only):
  0: Charge Power (W)
  1: Charge Current (0.1A)
  2: Voltage (0.1V)
  3: Session Energy (Wh)
  4: Total Energy (kWh)
  5: Status (0=Available, 1=Charging, 2=Fault)
  6: EV Connected (0/1)
  7: EV Battery SOC (%)
  8: Max Available Current (0.1A)
```

### Heat Pump (Unit ID 5)
```
Holding Registers (Read/Write):
  0: Power Setpoint (W)
  1: Enable/Disable
  2: Mode (0=Off, 1=Heat, 2=Cool)
  3: Temperature Setpoint (0.1°C)

Input Registers (Read-only):
  0: Active Power (W)
  1: Indoor Temperature (0.1°C)
  2: Outdoor Temperature (0.1°C)
  3: COP (0.1)
  4: Status
  5: Compressor Speed (%)
```

### Base Load / Consumption (Unit ID 6)
```
Input Registers (Read-only):
  0: Active Power (W)
  1: Refrigerator (W)
  2: Freezer (W)
  3: Lighting (W)
  4: Electronics (W)
  5: Other (W)
```

---

## OpenEMS Edge Configuration Example

```json
{
  "components": {
    "meter0": {
      "alias": "Grid Meter",
      "factoryId": "Simulator.GridMeter.Acting",
      "properties": {
        "modbus.id": "modbus0",
        "modbusUnitId": 3
      }
    },
    "ess0": {
      "alias": "Battery Storage",
      "factoryId": "Simulator.EssSymmetric.Reacting",
      "properties": {
        "modbus.id": "modbus0",
        "modbusUnitId": 2,
        "capacity": 13500,
        "maxApparentPower": 5000
      }
    },
    "pvInverter0": {
      "alias": "Solar PV",
      "factoryId": "Simulator.PvInverter",
      "properties": {
        "modbus.id": "modbus0",
        "modbusUnitId": 1,
        "maxActivePower": 6000
      }
    },
    "evcs0": {
      "alias": "EV Charger",
      "factoryId": "Evcs.Simulator",
      "properties": {
        "modbus.id": "modbus0",
        "modbusUnitId": 4,
        "maxPower": 11000
      }
    },
    "modbus0": {
      "alias": "Modbus Bridge",
      "factoryId": "Bridge.Modbus.Tcp",
      "properties": {
        "ip": "orbiteos-simulators",
        "port": 502
      }
    }
  }
}
```

---

## Python Modbus Implementation

We'll use **pymodbus** library:

```python
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.datastore import ModbusSequentialDataBlock

# Create data blocks for each device
solar_datablock = ModbusSequentialDataBlock(0, [0]*100)
battery_datablock = ModbusSequentialDataBlock(0, [0]*100)
grid_datablock = ModbusSequentialDataBlock(0, [0]*100)
ev_datablock = ModbusSequentialDataBlock(0, [0]*100)
heatpump_datablock = ModbusSequentialDataBlock(0, [0]*100)

# Create slave contexts (one per device)
solar_context = ModbusSlaveContext(
    di=solar_datablock,  # Discrete Inputs
    co=solar_datablock,  # Coils
    hr=solar_datablock,  # Holding Registers
    ir=solar_datablock   # Input Registers
)

# Map unit IDs to contexts
slaves = {
    1: solar_context,      # Solar PV
    2: battery_context,    # Battery
    3: grid_context,       # Grid Meter
    4: ev_context,         # EV Charger
    5: heatpump_context,   # Heat Pump
    6: baseload_context    # Base Load
}

# Start Modbus TCP server
context = ModbusServerContext(slaves=slaves, single=False)
StartTcpServer(context=context, address=("0.0.0.0", 502))
```

---

## Summary

**✅ OpenEMS Compatibility:**
1. Use Modbus TCP protocol (industry standard)
2. Implement standard register maps
3. Each device = unique Modbus Unit ID
4. OpenEMS reads/writes via Modbus Bridge component

**✅ OrbitEOS Architecture:**
1. Single Modbus TCP server with multiple unit IDs
2. Each simulator updates its registers in real-time
3. MQTT publishes for monitoring
4. OpenEMS connects and controls devices

**✅ Benefits:**
- Works with any OpenEMS version
- No OpenEMS modifications needed
- Easy to test and debug
- Industry-standard protocol
- Realistic device behavior

---

## Next: Implement All Simulators with Modbus Support

I'll now create complete implementations for:
1. ✅ Solar PV (with Modbus)
2. ⏳ Battery (with Modbus)
3. ⏳ Grid Meter (with Modbus)
4. ⏳ EV Charger (with Modbus)
5. ⏳ Heat Pump (with Modbus)
6. ⏳ Base Load (with Modbus)
7. ⏳ Main Orchestrator (Modbus Server + MQTT Publisher)

All compatible with OpenEMS Edge! 🚀
