# OrbitEOS Platform - Quick Start Guide

## 🚀 Get Running in 5 Minutes

### Prerequisites
- Docker Desktop installed and running
- 8GB RAM available
- 20GB disk space

### Step 1: Download

```bash
# Clone or extract the orbiteos-platform folder
cd orbiteos-platform
```

### Step 2: Start Everything

```bash
# Make script executable (first time only)
chmod +x start.sh

# Start the platform
./start.sh start
```

### Step 3: Access Services

Open these URLs in your browser:

| Service | URL | Login |
|---------|-----|-------|
| **Dashboard** | http://localhost:3000 | admin / orbiteos |
| **Workflows** | http://localhost:5678 | admin / orbiteos |
| **OpenEMS** | http://localhost:8080 | admin / admin |

### Step 4: Watch It Work

```bash
# See live device telemetry
./start.sh logs pv-simulator
./start.sh logs battery-simulator

# Or see everything
./start.sh logs
```

---

## 📊 What You'll See

### Grafana Dashboard (http://localhost:3000)
- Real-time power flows
- Battery state of charge
- Solar generation curve
- Grid connection status

### Device Simulators Running

1. **PV Inverter** - Generates solar power following sun curve
2. **Battery** - Charges/discharges based on setpoints
3. **EV Charger** - Ready for charging sessions
4. **Smart Meter** - Reports grid power consumption

### MQTT Topics (use MQTT Explorer)

Connect to `localhost:1883` and see:
```
orbiteos/devices/pv-inverter-01/power_kw
orbiteos/devices/battery-01/soc_percent
orbiteos/devices/smart-meter-01/grid_power
```

---

## 🎯 Try These Workflows

### 1. Control the Battery

Open n8n (http://localhost:5678) and create a workflow:
- **Trigger**: Schedule (every 5 minutes)
- **Action**: HTTP Request to MQTT
- **Topic**: `orbiteos/devices/battery-01/control/power_setpoint`
- **Value**: `10` (charge at 10kW) or `-10` (discharge)

### 2. Monitor Peak Load

Watch the smart meter. When grid power exceeds 50kW:
- Workflow triggers
- Email notification sent
- Battery starts discharging
- EV charging throttled

### 3. Solar Optimization

During sunny hours (10am-3pm):
- PV produces 30-45kW
- Excess power charges battery
- Grid import minimized
- Energy costs reduced

---

## 🛠️ Common Commands

```bash
# Check status
./start.sh status

# View logs
./start.sh logs [service-name]

# Restart everything
./start.sh restart

# Stop everything
./start.sh stop

# Clean up (removes all data)
./start.sh clean

# Fresh start
./start.sh reset
```

---

## 🐛 Troubleshooting

### Services won't start
```bash
# Check Docker is running
docker info

# Remove old containers
./start.sh clean
./start.sh start
```

### Can't access dashboards
```bash
# Check ports are not in use
lsof -i :3000
lsof -i :5678
lsof -i :8080

# Restart services
./start.sh restart
```

### Simulators not producing data
```bash
# Check MQTT broker
./start.sh logs mosquitto

# Restart specific simulator
docker-compose restart pv-simulator
```

---

## 📚 Next Steps

1. **Read the docs**: Open `README.md` for full documentation
2. **Explore workflows**: Import examples from `orbiteos-workflows/`
3. **Customize devices**: Edit `docker-compose.yml` environment variables
4. **Add real EMS**: Replace simulators with actual OpenEMS installation

---

## 💡 Understanding OrbitEOS

### Architecture Layers

```
┌──────────────────────────────────┐
│  OrbitEOS (You are here)         │  ← Orchestration & Intelligence
│  - Workflows                      │
│  - AI Agents                      │
│  - Decision Engine                │
└──────────────────┬───────────────┘
                   │
┌──────────────────┴───────────────┐
│  OpenEMS                          │  ← Asset Control
│  - Real-time control              │
│  - Safety limits                  │
│  - Hardware abstraction           │
└──────────────────┬───────────────┘
                   │
┌──────────────────┴───────────────┐
│  Physical Assets                  │  ← Energy Resources
│  [PV] [Battery] [EV] [Loads]     │
└──────────────────────────────────┘
```

### Key Concepts

**EMS** = Controls individual assets (low level)  
**OrbitEOS** = Orchestrates processes (high level)

**Example:**
- EMS: "Battery, charge at 10kW"
- OrbitEOS: "During cheap tariff hours, charge battery to 90%, then discharge during peak"

---

## 🆘 Get Help

- **Documentation**: Full README.md in this folder
- **GitHub Issues**: [Create an issue]
- **Email**: support@orbiteos.nl (when launched)

---

**Built with ❤️ in the Netherlands**

*OrbitEOS - Orchestrating the Energy Transition*
