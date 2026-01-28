#!/bin/bash

# OrbitEOS Platform - Startup Script
# Orbit Energy Operating System

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logo
echo -e "${BLUE}"
cat << "EOF"
   ___       _     _ _   _____ ___  ____  
  / _ \ _ __| |__ (_) |_| ____/ _ \/ ___| 
 | | | | '__| '_ \| | __|  _|| | | \___ \ 
 | |_| | |  | |_) | | |_| |__| |_| |___) |
  \___/|_|  |_.__/|_|\__|_____\___/|____/ 
                                           
  Orbit Energy Operating System
  
EOF
echo -e "${NC}"

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Docker is running${NC}"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${YELLOW}⚠️  docker-compose not found, trying 'docker compose'${NC}"
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Function to show usage
usage() {
    cat << EOF
Usage: $0 [command]

Commands:
    start       Start all OrbitEOS services
    stop        Stop all services
    restart     Restart all services
    status      Show status of all services
    logs        Show logs from all services
    clean       Stop and remove all containers, networks, volumes
    reset       Clean and start fresh
    shell       Open bash shell in orchestrator container
    
Examples:
    $0 start              # Start the platform
    $0 logs pv-simulator  # Show logs for PV simulator
    $0 status             # Check service status
    
EOF
    exit 1
}

# Start services
start_services() {
    echo -e "${BLUE}🚀 Starting OrbitEOS Platform...${NC}"
    
    # Create directories if they don't exist
    mkdir -p mosquitto/data mosquitto/log
    mkdir -p orbiteos-core/workflows orbiteos-core/logs
    mkdir -p grafana/provisioning
    
    # Pull latest images
    echo -e "${YELLOW}📦 Pulling latest images...${NC}"
    $DOCKER_COMPOSE pull
    
    # Start services
    echo -e "${YELLOW}⚙️  Starting services...${NC}"
    $DOCKER_COMPOSE up -d
    
    # Wait for services to be healthy
    echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
    sleep 10
    
    # Show service status
    $DOCKER_COMPOSE ps
    
    echo ""
    echo -e "${GREEN}✅ OrbitEOS Platform started successfully!${NC}"
    echo ""
    echo -e "${BLUE}📊 Access Points:${NC}"
    echo -e "  OrbitEOS Dashboard:  ${GREEN}http://localhost:3000${NC}  (admin/orbiteos)"
    echo -e "  Workflow Engine:     ${GREEN}http://localhost:5678${NC}  (admin/orbiteos)"
    echo -e "  OpenEMS Edge:        ${GREEN}http://localhost:8080${NC}  (admin/admin)"
    echo -e "  OpenEMS Backend:     ${GREEN}http://localhost:8081${NC}"
    echo -e "  InfluxDB:            ${GREEN}http://localhost:8086${NC}  (orbiteos/orbiteos123)"
    echo ""
    echo -e "${BLUE}📡 MQTT Broker:${NC}"
    echo -e "  Host: localhost"
    echo -e "  Port: 1883"
    echo -e "  Websocket: 9001"
    echo ""
    echo -e "${BLUE}🔌 Device Simulators:${NC}"
    echo -e "  PV Inverter (Modbus):    localhost:5020"
    echo -e "  Battery (Modbus):        localhost:5021"
    echo -e "  EV Charger (OCPP):       Started"
    echo -e "  Smart Meter (MQTT):      Started"
    echo ""
    echo -e "${YELLOW}💡 Tip: Run './start.sh logs' to see live logs${NC}"
}

# Stop services
stop_services() {
    echo -e "${YELLOW}🛑 Stopping OrbitEOS Platform...${NC}"
    $DOCKER_COMPOSE down
    echo -e "${GREEN}✅ All services stopped${NC}"
}

# Restart services
restart_services() {
    echo -e "${YELLOW}🔄 Restarting OrbitEOS Platform...${NC}"
    $DOCKER_COMPOSE restart
    echo -e "${GREEN}✅ All services restarted${NC}"
}

# Show status
show_status() {
    echo -e "${BLUE}📊 OrbitEOS Platform Status:${NC}"
    echo ""
    $DOCKER_COMPOSE ps
    echo ""
    
    # Check if services are accessible
    echo -e "${BLUE}🔍 Service Health Checks:${NC}"
    
    check_service() {
        local name=$1
        local url=$2
        if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|302\|401"; then
            echo -e "  ${GREEN}✓${NC} $name"
        else
            echo -e "  ${RED}✗${NC} $name"
        fi
    }
    
    check_service "Grafana Dashboard" "http://localhost:3000"
    check_service "n8n Workflows" "http://localhost:5678"
    check_service "OpenEMS Edge" "http://localhost:8080"
    check_service "InfluxDB" "http://localhost:8086/health"
}

# Show logs
show_logs() {
    if [ -z "$1" ]; then
        $DOCKER_COMPOSE logs -f --tail=100
    else
        $DOCKER_COMPOSE logs -f --tail=100 "$1"
    fi
}

# Clean everything
clean_all() {
    echo -e "${RED}⚠️  This will remove all containers, networks, and volumes!${NC}"
    read -p "Are you sure? (yes/no): " -r
    if [[ $REPLY =~ ^[Yy]es$ ]]; then
        echo -e "${YELLOW}🧹 Cleaning up...${NC}"
        $DOCKER_COMPOSE down -v --remove-orphans
        echo -e "${GREEN}✅ Cleanup complete${NC}"
    else
        echo -e "${YELLOW}Cancelled${NC}"
    fi
}

# Reset (clean and start)
reset_platform() {
    clean_all
    if [[ $? -eq 0 ]]; then
        start_services
    fi
}

# Open shell in orchestrator
open_shell() {
    echo -e "${BLUE}🐚 Opening shell in OrbitEOS Orchestrator...${NC}"
    docker exec -it orbiteos-orchestrator /bin/bash
}

# Parse command
case "${1:-}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    clean)
        clean_all
        ;;
    reset)
        reset_platform
        ;;
    shell)
        open_shell
        ;;
    *)
        usage
        ;;
esac
