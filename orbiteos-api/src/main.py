#!/usr/bin/env python3
"""
OrbitEOS Platform API
Multi-tenant energy orchestration system REST API.
"""

import os
import logging
from contextlib import asynccontextmanager
from typing import Optional
import re

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'postgres')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'orbiteos')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'postgres')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'postgres')

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Create database engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# TimescaleDB configuration
TIMESCALEDB_HOST = os.getenv('TIMESCALEDB_HOST', 'timescaledb')
TIMESCALEDB_PORT = os.getenv('TIMESCALEDB_PORT', '5432')
TIMESCALEDB_DB = os.getenv('TIMESCALEDB_DB', 'telemetry')
TIMESCALEDB_USER = os.getenv('TIMESCALEDB_USER', 'postgres')
TIMESCALEDB_PASSWORD = os.getenv('TIMESCALEDB_PASSWORD', 'timescale')

TIMESCALEDB_URL = f"postgresql://{TIMESCALEDB_USER}:{TIMESCALEDB_PASSWORD}@{TIMESCALEDB_HOST}:{TIMESCALEDB_PORT}/{TIMESCALEDB_DB}"
timescale_engine = create_engine(TIMESCALEDB_URL, pool_pre_ping=True)
TimescaleSession = sessionmaker(autocommit=False, autoflush=False, bind=timescale_engine)


# Database dependencies
def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_timescale_db():
    """TimescaleDB dependency"""
    db = TimescaleSession()
    try:
        yield db
    finally:
        db.close()


def extract_email_domain(email: str) -> Optional[str]:
    """Extract domain from email address"""
    if '@' not in email:
        return None
    return '@' + email.split('@')[1]


async def get_tenant_from_email(email: str, db: Session) -> Optional[dict]:
    """Resolve tenant from email domain"""
    email_domain = extract_email_domain(email)
    if not email_domain:
        return None

    query = text("""
        SELECT t.id, t.tenant_code, t.tenant_name, t.logo_url,
               t.primary_color, t.secondary_color, t.config
        FROM tenants t
        JOIN tenant_email_domains ted ON t.id = ted.tenant_id
        WHERE ted.email_domain = :email_domain
        LIMIT 1
    """)

    result = db.execute(query, {"email_domain": email_domain}).fetchone()

    if result:
        return {
            "id": str(result[0]),
            "code": result[1],
            "name": result[2],
            "logo_url": result[3],
            "primary_color": result[4],
            "secondary_color": result[5],
            "config": result[6]
        }
    return None


async def get_tenant_from_request(request: Request, db: Session = Depends(get_db)) -> dict:
    """
    Extract tenant information from request.
    Priority: X-Tenant-ID header > Authorization > Query param > Subdomain > Default
    """
    # Method 1: Explicit tenant header
    tenant_id = request.headers.get('X-Tenant-ID')
    if tenant_id:
        query = text("""
            SELECT id, tenant_code, tenant_name, logo_url, primary_color, secondary_color
            FROM tenants WHERE id = :tenant_id
        """)
        result = db.execute(query, {"tenant_id": tenant_id}).fetchone()
        if result:
            return {
                "id": str(result[0]),
                "code": result[1],
                "name": result[2],
                "logo_url": result[3],
                "primary_color": result[4],
                "secondary_color": result[5]
            }

    # Method 2: From email header
    email = request.headers.get('X-User-Email')
    if email:
        tenant = await get_tenant_from_email(email, db)
        if tenant:
            return tenant

    # Method 3: Query parameter
    tenant_code = request.query_params.get('tenant')
    if tenant_code:
        query = text("""
            SELECT id, tenant_code, tenant_name, logo_url, primary_color, secondary_color
            FROM tenants WHERE tenant_code = :code
        """)
        result = db.execute(query, {"code": tenant_code}).fetchone()
        if result:
            return {
                "id": str(result[0]),
                "code": result[1],
                "name": result[2],
                "logo_url": result[3],
                "primary_color": result[4],
                "secondary_color": result[5]
            }

    # Method 4: Subdomain
    host = request.headers.get('Host', '')
    subdomain_match = re.match(r'^([^.]+)\.orbiteos\.(nl|io|com)', host)
    if subdomain_match:
        subdomain = subdomain_match.group(1)
        if subdomain not in ['www', 'api', 'app']:
            query = text("""
                SELECT id, tenant_code, tenant_name, logo_url, primary_color, secondary_color
                FROM tenants WHERE tenant_code = :code
            """)
            result = db.execute(query, {"code": subdomain}).fetchone()
            if result:
                return {
                    "id": str(result[0]),
                    "code": result[1],
                    "name": result[2],
                    "logo_url": result[3],
                    "primary_color": result[4],
                    "secondary_color": result[5]
                }

    # Default: Return demo tenant
    return {
        "id": "demo",
        "code": "demo",
        "name": "Demo Tenant",
        "logo_url": None,
        "primary_color": "#00A86B",
        "secondary_color": "#0066CC"
    }


# Application lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info("Starting OrbitEOS Platform API")

    # Test database connections
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("PostgreSQL connection successful")
    except Exception as e:
        logger.warning(f"PostgreSQL connection failed: {e}")

    try:
        with timescale_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("TimescaleDB connection successful")
    except Exception as e:
        logger.warning(f"TimescaleDB connection failed: {e}")

    yield

    logger.info("Shutting down OrbitEOS Platform API")


# Create FastAPI app
app = FastAPI(
    title="OrbitEOS Platform API",
    description="Orbit Energy Operating System - Multi-tenant Energy Orchestration",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "OrbitEOS Platform API",
        "version": "1.0.0",
        "description": "Orbit Energy Operating System"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "disconnected", "error": str(e)}
        )


@app.get("/api/v1/status")
async def get_system_status():
    """Get current system status for LLM agent"""
    # This endpoint provides simplified status for the LLM
    return {
        "solar": {
            "power_kw": 3.2,
            "daily_energy_kwh": 18.4,
            "status": "producing"
        },
        "battery": {
            "soc_percent": 72,
            "power_kw": 1.8,
            "status": "charging"
        },
        "grid": {
            "power_kw": -0.8,
            "status": "exporting"
        },
        "ev_charger": {
            "power_kw": 0,
            "vehicle_soc_percent": 0,
            "status": "available"
        },
        "home": {
            "consumption_kw": 2.4
        }
    }


@app.get("/api/v1/tenant/info")
async def get_tenant_info(
    request: Request,
    tenant: dict = Depends(get_tenant_from_request)
):
    """Get tenant information and branding"""
    return {
        "tenant_id": tenant["id"],
        "tenant_code": tenant["code"],
        "tenant_name": tenant["name"],
        "branding": {
            "logo_url": tenant.get("logo_url"),
            "primary_color": tenant.get("primary_color"),
            "secondary_color": tenant.get("secondary_color")
        }
    }


@app.get("/api/v1/sites")
async def list_sites(
    request: Request,
    tenant: dict = Depends(get_tenant_from_request),
    db: Session = Depends(get_db)
):
    """List all sites for tenant"""
    try:
        query = text("""
            SELECT id, site_code, site_name, site_type, city, country,
                   grid_connection_kw, status
            FROM sites
            WHERE tenant_id = :tenant_id
            ORDER BY site_name
        """)
        results = db.execute(query, {"tenant_id": tenant["id"]}).fetchall()

        sites = [
            {
                "id": str(row[0]),
                "site_code": row[1],
                "name": row[2],
                "type": row[3],
                "city": row[4],
                "country": row[5],
                "grid_connection_kw": float(row[6]) if row[6] else None,
                "status": row[7]
            }
            for row in results
        ]
    except Exception:
        # Return demo data if database not available
        sites = [{
            "id": "demo-site",
            "site_code": "DEMO001",
            "name": "Demo Home",
            "type": "residential",
            "city": "Amsterdam",
            "country": "NL",
            "grid_connection_kw": 25.0,
            "status": "active"
        }]

    return {
        "tenant": tenant["name"],
        "count": len(sites),
        "sites": sites
    }


@app.get("/api/v1/devices")
async def list_devices(
    request: Request,
    tenant: dict = Depends(get_tenant_from_request),
    site_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all devices for tenant"""
    try:
        if site_id:
            query = text("""
                SELECT id, device_id, device_type, name, rated_power_kw, status
                FROM devices
                WHERE tenant_id = :tenant_id AND site_id = :site_id
                ORDER BY device_type, name
            """)
            results = db.execute(query, {"tenant_id": tenant["id"], "site_id": site_id}).fetchall()
        else:
            query = text("""
                SELECT id, device_id, device_type, name, rated_power_kw, status
                FROM devices
                WHERE tenant_id = :tenant_id
                ORDER BY device_type, name
            """)
            results = db.execute(query, {"tenant_id": tenant["id"]}).fetchall()

        devices = [
            {
                "id": str(row[0]),
                "device_id": row[1],
                "type": row[2],
                "name": row[3],
                "rated_power_kw": float(row[4]) if row[4] else None,
                "status": row[5]
            }
            for row in results
        ]
    except Exception:
        # Return demo data
        devices = [
            {"id": "pv1", "device_id": "PV001", "type": "solar", "name": "Rooftop Solar", "rated_power_kw": 6.0, "status": "online"},
            {"id": "bat1", "device_id": "BAT001", "type": "battery", "name": "Powerwall", "rated_power_kw": 5.0, "status": "online"},
            {"id": "grid1", "device_id": "GRID001", "type": "meter", "name": "Grid Meter", "rated_power_kw": 25.0, "status": "online"},
            {"id": "ev1", "device_id": "EV001", "type": "ev_charger", "name": "EV Charger", "rated_power_kw": 11.0, "status": "online"},
        ]

    return {
        "tenant": tenant["name"],
        "count": len(devices),
        "devices": devices
    }


@app.get("/api/v1/telemetry/latest")
async def get_latest_telemetry(
    request: Request,
    tenant: dict = Depends(get_tenant_from_request),
    device_id: Optional[str] = None,
    timescale_db: Session = Depends(get_timescale_db)
):
    """Get latest telemetry for devices"""
    try:
        if device_id:
            query = text("""
                SELECT DISTINCT ON (metric_name)
                    time, device_id, metric_name, value, unit
                FROM device_telemetry
                WHERE tenant_id = :tenant_id AND device_id = :device_id
                ORDER BY metric_name, time DESC
            """)
            results = timescale_db.execute(query, {
                "tenant_id": tenant["id"],
                "device_id": device_id
            }).fetchall()
        else:
            query = text("""
                SELECT DISTINCT ON (device_id, metric_name)
                    time, device_id, metric_name, value, unit
                FROM device_telemetry
                WHERE tenant_id = :tenant_id
                ORDER BY device_id, metric_name, time DESC
                LIMIT 100
            """)
            results = timescale_db.execute(query, {"tenant_id": tenant["id"]}).fetchall()

        telemetry = [
            {
                "timestamp": row[0].isoformat(),
                "device_id": row[1],
                "metric": row[2],
                "value": float(row[3]) if row[3] else None,
                "unit": row[4]
            }
            for row in results
        ]
    except Exception:
        # Return demo data
        from datetime import datetime
        telemetry = [
            {"timestamp": datetime.now().isoformat(), "device_id": "PV001", "metric": "power", "value": 3200, "unit": "W"},
            {"timestamp": datetime.now().isoformat(), "device_id": "BAT001", "metric": "soc", "value": 72, "unit": "%"},
            {"timestamp": datetime.now().isoformat(), "device_id": "BAT001", "metric": "power", "value": 1800, "unit": "W"},
            {"timestamp": datetime.now().isoformat(), "device_id": "GRID001", "metric": "power", "value": -800, "unit": "W"},
        ]

    return {
        "tenant": tenant["name"],
        "count": len(telemetry),
        "telemetry": telemetry
    }


@app.get("/api/v1/energy/summary")
async def get_energy_summary():
    """Get energy summary for dashboard"""
    return {
        "today": {
            "solar_production_kwh": 18.4,
            "consumption_kwh": 14.2,
            "grid_import_kwh": 2.1,
            "grid_export_kwh": 6.3,
            "self_consumption_percent": 74
        },
        "current": {
            "solar_power_kw": 3.2,
            "battery_soc_percent": 72,
            "battery_power_kw": 1.8,
            "grid_power_kw": -0.8,
            "consumption_kw": 2.4
        },
        "prices": {
            "current_import_eur_kwh": 0.25,
            "current_export_eur_kwh": 0.08,
            "today_cost_eur": 0.53,
            "today_revenue_eur": 0.50
        }
    }


if __name__ == "__main__":
    port = int(os.getenv('PORT', 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
