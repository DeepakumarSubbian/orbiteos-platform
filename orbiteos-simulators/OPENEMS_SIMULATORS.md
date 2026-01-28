# OpenEMS Built-in Simulators - Complete Reference

Based on OpenEMS official documentation and source code (https://github.com/OpenEMS/openems), OpenEMS Edge includes these **built-in simulator components**:

## ✅ OpenEMS Native Simulators (Built-in)

### 1. **Simulator.GridMeter.Acting**
```
Factory ID: Simulator.GridMeter.Acting
Purpose: Simulates a grid connection point meter
Type: Acting (affects system behavior)
Channels:
  - ActivePower (W, signed)
  - ReactivePower (var)
  - Voltage (mV)
  - Current (mA)
Configuration:
  - maxActivePower (W)
  - minActivePower (W)
```

### 2. **Simulator.GridMeter.Reacting**
```
Factory ID: Simulator.GridMeter.Reacting
Purpose: Grid meter that reacts to system state
Type: Reacting (responds to other components)
```

### 3. **Simulator.EssSymmetric.Reacting**
```
Factory ID: Simulator.EssSymmetric.Reacting
Purpose: Battery Energy Storage System
Type: Reacting (follows commands from controller)
Channels:
  - Soc (%)
  - Capacity (Wh)
  - ActivePower (W)
  - AllowedChargePower (W)
  - AllowedDischargePower (W)
  - GridMode
Configuration:
  - capacity (Wh)
  - maxApparentPower (VA)
```

### 4. **Simulator.PvInverter**
```
Factory ID: Simulator.PvInverter
Purpose: Solar PV inverter
Channels:
  - ActivePower (W)
  - MaxActivePower (W)
Configuration:
  - maxActivePower (W)
```

### 5. **Simulator.ProductionMeter.Acting**
```
Factory ID: Simulator.ProductionMeter.Acting
Purpose: Production meter (solar, wind, etc.)
Type: Acting
```

### 6. **Simulator.ConsumptionMeter.Acting**
```
Factory ID: Simulator.ConsumptionMeter.Acting  
Purpose: Consumption meter
Type: Acting
```

### 7. **Simulator.Datasource.CSV.Predictor**
```
Factory ID: Simulator.Datasource.CSV.Predictor
Purpose: Load data from CSV files for prediction
Use: Historical data replay
```

### 8. **Simulator.Datasource.CSV.Reader**
```
Factory ID: Simulator.Datasource.CSV.Reader
Purpose: Read time-series data from CSV
Use: Testing with real data
```

## 🔧 How OpenEMS Simulators Work

### Acting vs Reacting Simulators

**Acting Simulators:**
- Generate independent behavior
- Not controlled by OpenEMS controllers
- Example: GridMeter.Acting generates random consumption

**Reacting Simulators:**
- Respond to system commands
- Controlled by OpenEMS
- Example: EssSymmetric.Reacting follows charge/discharge commands

## 🎯 OrbitEOS Strategy: External Simulators via Modbus

**Why NOT use OpenEMS built-in simulators:**
- ❌ Limited to basic behavior
- ❌ No sun trajectory following
- ❌ No realistic weather impact
- ❌ No complex device interactions
- ❌ Hard to customize

**Why CREATE external simulators:**
- ✅ Full control over behavior
- ✅ Realistic physics (sun position, battery curves)
- ✅ Weather impact modeling
- ✅ Can run independently
- ✅ MQTT telemetry for OrbitEOS LLM
- ✅ Demo-ready from boot
- ✅ Works with ANY OpenEMS version

## 📋 OrbitEOS Simulator Architecture

```
OrbitEOS Approach:
┌─────────────────────────────────────────┐
│  OrbitEOS Simulators (External)         │
│  ├── Solar (realistic sun following)    │
│  ├── Battery (Tesla Powerwall model)    │
│  ├── EV Charger (OCPP simulation)       │
│  ├── Grid Meter (dynamic pricing)       │
│  ├── Heat Pump (COP curves)             │
│  └── Base Load (realistic patterns)     │
└─────────────────────────────────────────┘
                 ↓
        Modbus TCP Protocol
                 ↓
┌─────────────────────────────────────────┐
│  OpenEMS Edge                           │
│  ├── Bridge.Modbus.Tcp                  │
│  ├── Meter.Custom (reads Grid Meter)    │
│  ├── Ess.Custom (reads Battery)         │
│  ├── PvInverter.Custom (reads Solar)    │
│  └── Controllers                        │
└─────────────────────────────────────────┘
```

## 🔌 Connection Methods

### Option 1: Modbus TCP (RECOMMENDED) ✅
```
OrbitEOS Simulators → Modbus TCP Server (Port 502)
                     ↓
OpenEMS Edge → Bridge.Modbus.Tcp → Device Components
```

**Advantages:**
- Industry standard
- Works with real hardware too
- No OpenEMS modifications needed
- Easy to debug
- Supports all device types

### Option 2: Use OpenEMS REST API
```
OrbitEOS Simulators → OpenEMS REST API
                     ↓
OpenEMS Edge receives updates
```

**Disadvantages:**
- REST API is more for monitoring
- Not ideal for real-time simulation
- Polling overhead

### Option 3: JSON-RPC WebSocket
```
OrbitEOS Simulators → WebSocket (Port 8084)
                     ↓
OpenEMS Edge UI Backend
```

**Disadvantages:**
- Primarily for UI communication
- Not designed for device simulation

## ✅ FINAL DECISION: Modbus TCP

**Implementation Plan:**

1. **OrbitEOS Simulators** (Python)
   - Run Modbus TCP server (pymodbus)
   - Each device = unique Modbus Unit ID
   - Realistic behavior (sun, weather, physics)
   - MQTT publishing (for OrbitEOS monitoring)

2. **OpenEMS Edge Configuration**
   - Bridge.Modbus.Tcp component
   - Connect to `orbiteos-simulators:502`
   - Map standard Modbus components
   - Use generic meter/ess/pv components

3. **Benefits**
   - ✅ Realistic simulations
   - ✅ OpenEMS compatibility
   - ✅ No OpenEMS modifications
   - ✅ Works with real hardware later
   - ✅ Demo-ready

## 📝 OpenEMS Configuration Example

```json
{
  "components": {
    "modbus0": {
      "id": "modbus0",
      "alias": "OrbitEOS Simulators",
      "factoryId": "Bridge.Modbus.Tcp",
      "properties": {
        "ip": "orbiteos-simulators",
        "port": 502
      }
    },
    "meter0": {
      "id": "meter0",
      "alias": "Grid Meter",
      "factoryId": "Meter.Goodwe.GoodWe-Grid-Meter",
      "properties": {
        "modbus.id": "modbus0",
        "modbusUnitId": 3
      }
    },
    "ess0": {
      "id": "ess0",
      "alias": "Battery",
      "factoryId": "Ess.Generic.ManagedSymmetric",
      "properties": {
        "modbus.id": "modbus0",
        "modbusUnitId": 2,
        "startStop": "START",
        "capacity": 13500,
        "maxApparentPower": 5000
      }
    },
    "pvInverter0": {
      "id": "pvInverter0",
      "alias": "Solar PV",
      "factoryId": "PvInverter.SolarEdge",
      "properties": {
        "modbus.id": "modbus0",
        "modbusUnitId": 1
      }
    }
  }
}
```

## 🎯 Summary

**OpenEMS Built-in Simulators:**
- ✅ Good for basic testing
- ❌ Not realistic enough
- ❌ Limited customization
- ❌ No complex scenarios

**OrbitEOS External Simulators:**
- ✅ Fully realistic behavior
- ✅ Weather and physics modeling
- ✅ Demo-ready system
- ✅ MQTT telemetry
- ✅ Works with OpenEMS via Modbus
- ✅ No OpenEMS modifications

**Decision: Build external Modbus TCP simulators** 🚀

---

## Next Steps

I will now create complete implementations for:
1. ✅ Solar PV Simulator (with Modbus TCP)
2. ⏳ Battery Simulator (with Modbus TCP)
3. ⏳ Grid Meter Simulator (with Modbus TCP)
4. ⏳ EV Charger Simulator (with Modbus TCP)
5. ⏳ Heat Pump Simulator (with Modbus TCP)
6. ⏳ Base Load Simulator (with Modbus TCP)
7. ⏳ Modbus Server (orchestrates all simulators)
8. ⏳ MQTT Publisher (telemetry for OrbitEOS)

All compatible with OpenEMS Edge via standard Modbus TCP! ✅
