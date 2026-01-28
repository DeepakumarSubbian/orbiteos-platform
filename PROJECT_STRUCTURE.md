# OrbitEOS Platform - Project Structure

## Repository Strategy

**Single Monorepo Approach** - All components in one repository for easier development and deployment.

```
orbiteos-platform/
├── README.md                          # Main project documentation
├── LICENSE                            # MIT License
├── .gitignore                         # Git ignore rules
├── docker-compose.yml                 # Main orchestration file
├── docker-compose.dev.yml             # Development overrides
├── .env.example                       # Environment template
│
├── docs/                              # Documentation
│   ├── getting-started.md
│   ├── architecture.md
│   ├── deployment.md
│   ├── api-reference.md
│   └── use-cases.md
│
├── orbiteos-simulators/               # Device simulators
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── solar_simulator.py
│   │   ├── battery_simulator.py
│   │   ├── ev_simulator.py
│   │   ├── heat_pump_simulator.py
│   │   ├── appliances_simulator.py
│   │   └── grid_simulator.py
│   └── tests/
│
├── orbiteos-weather/                  # Weather simulation
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   └── weather.py
│   └── tests/
│
├── orbiteos-pricing/                  # Energy pricing
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── simulation.py
│   │   ├── entsoe.py
│   │   └── nordpool.py
│   └── tests/
│
├── orbiteos-api/                      # Core API (FastAPI)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── models.py
│   │   ├── routes/
│   │   ├── services/
│   │   └── integrations/
│   └── tests/
│
├── orbiteos-llm/                      # LLM Agent
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── agent.py
│   │   ├── providers/
│   │   │   ├── base.py
│   │   │   ├── ollama.py
│   │   │   ├── claude.py
│   │   │   └── openai.py
│   │   └── prompts/
│   └── tests/
│
├── orbiteos-web/                      # Web Frontend (React)
│   ├── Dockerfile
│   ├── package.json
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── hooks/
│   │   └── utils/
│   └── tests/
│
├── homeassistant/                     # Home Assistant config
│   ├── configuration.yaml
│   ├── automations.yaml
│   ├── scripts.yaml
│   └── custom_components/
│       └── openems/                   # OpenEMS integration
│
├── openems-edge/                      # OpenEMS Edge config
│   └── config.json
│
├── openems-backend/                   # OpenEMS Backend config
│   └── config.properties
│
├── grafana/                           # Grafana dashboards
│   ├── provisioning/
│   │   ├── datasources/
│   │   └── dashboards/
│   └── dashboards/
│       ├── home-energy.json
│       └── commercial-energy.json
│
├── mosquitto/                         # MQTT broker config
│   └── config/
│       └── mosquitto.conf
│
├── scripts/                           # Utility scripts
│   ├── setup.sh
│   ├── init-db.sh
│   ├── pull-models.sh
│   └── backup.sh
│
└── infrastructure/                    # Future cloud deployment
    ├── terraform/
    └── kubernetes/
```

## Component Responsibilities

### orbiteos-simulators
- Simulate all energy devices
- Publish to OpenEMS Edge via Modbus TCP
- Publish telemetry to MQTT
- Realistic behavior patterns

### orbiteos-weather
- Weather simulation (cloud cover, temperature)
- Location-aware
- Publish to MQTT

### orbiteos-pricing
- Energy price fetching/simulation
- Multiple sources (simulation, ENTSO-E, etc.)
- Publish to MQTT

### orbiteos-api
- Central API layer
- Integration between HA, OpenEMS, LLM
- License management
- User management

### orbiteos-llm
- LLM provider abstraction
- Energy system knowledge
- Natural language interface
- Action execution

### orbiteos-web
- User interface
- Chat interface
- Dashboards
- Configuration

## Technology Stack

**Backend:**
- Python 3.11+
- FastAPI
- SQLAlchemy
- Pydantic
- asyncio

**Frontend:**
- React 18
- TypeScript
- TailwindCSS
- Recharts

**Databases:**
- PostgreSQL 15
- TimescaleDB (time-series)
- Redis 7 (cache)

**LLM:**
- Ollama (default)
- Anthropic Claude (optional)
- OpenAI GPT-4 (optional)

**Native Systems:**
- Home Assistant (official)
- OpenEMS Edge (official)
- OpenEMS Backend (official)

**Infrastructure:**
- Docker & Docker Compose
- MQTT (Eclipse Mosquitto)
- Grafana
- Nginx (reverse proxy)

## Getting Started

```bash
# Clone repository
git clone https://github.com/yourusername/orbiteos-platform
cd orbiteos-platform

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env

# Start platform
docker-compose up -d

# Pull LLM model
docker exec orbiteos-ollama ollama pull llama3.1:8b

# Access interfaces
# Home Assistant: http://localhost:8123
# OpenEMS Edge: http://localhost:8080
# OrbitEOS API: http://localhost:8000
# OrbitEOS Chat: http://localhost:9000
# Grafana: http://localhost:3000
```

## Development

```bash
# Development mode with hot reload
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

# Run tests
docker-compose run orbiteos-api pytest
docker-compose run orbiteos-llm pytest

# View logs
docker-compose logs -f orbiteos-simulators
```

## License

MIT License - See LICENSE file for details
