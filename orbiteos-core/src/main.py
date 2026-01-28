#!/usr/bin/env python3
"""
OrbitEOS Platform - Main Application
Multi-tenant energy orchestration system
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import uvicorn
from typing import Optional
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'orbiteos')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'orbiteos')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'orbiteos')

DATABASE_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"

# Create database engine
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# TimescaleDB configuration
TIMESCALEDB_HOST = os.getenv('TIMESCALEDB_HOST', 'localhost')
TIMESCALEDB_PORT = os.getenv('TIMESCALEDB_PORT', '5432')
TIMESCALEDB_DB = os.getenv('TIMESCALEDB_DB', 'timeseries')

TIMESCALEDB_URL = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{TIMESCALEDB_HOST}:{TIMESCALEDB_PORT}/{TIMESCALEDB_DB}"
timescale_engine = create_engine(TIMESCALEDB_URL, pool_pre_ping=True)
TimescaleSession = sessionmaker(autocommit=False, autoflush=False, bind=timescale_engine)

# ============================================================================
# MULTI-TENANT MIDDLEWARE
# ============================================================================

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

def extract_email_domain(email: str) -> str:
    """Extract domain from email address"""
    if '@' not in email:
        return None
    return '@' + email.split('@')[1]

async def get_tenant_from_email(email: str, db: Session) -> Optional[dict]:
    """
    Resolve tenant from email domain
    Examples:
        admin@ecoways.nl -> Ecoways tenant
        user@orbiteos.io -> OrbitEOS tenant
    """
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
    Extract tenant information from request
    Priority:
    1. X-Tenant-ID header
    2. Authorization token (extracts email)
    3. Query parameter ?tenant=xxx
    4. Subdomain (tenant.orbiteos.nl)
    """
    
    # Method 1: Explicit tenant header
    tenant_id = request.headers.get('X-Tenant-ID')
    if tenant_id:
        query = text("SELECT id, tenant_code, tenant_name, logo_url, primary_color, secondary_color FROM tenants WHERE id = :tenant_id")
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
    
    # Method 2: From email in Authorization header (simplified - add JWT parsing in production)
    auth_header = request.headers.get('Authorization')
    if auth_header:
        # In production, decode JWT and extract email
        # For POC, we'll accept Basic auth or custom header
        email = request.headers.get('X-User-Email')
        if email:
            tenant = await get_tenant_from_email(email, db)
            if tenant:
                return tenant
    
    # Method 3: Query parameter
    tenant_code = request.query_params.get('tenant')
    if tenant_code:
        query = text("SELECT id, tenant_code, tenant_name, logo_url, primary_color, secondary_color FROM tenants WHERE tenant_code = :code")
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
            query = text("SELECT id, tenant_code, tenant_name, logo_url, primary_color, secondary_color FROM tenants WHERE tenant_code = :code")
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
    
    # Default: Return OrbitEOS tenant for POC
    query = text("SELECT id, tenant_code, tenant_name, logo_url, primary_color, secondary_color FROM tenants WHERE tenant_code = 'orbiteos'")
    result = db.execute(query).fetchone()
    if result:
        return {
            "id": str(result[0]),
            "code": result[1],
            "name": result[2],
            "logo_url": result[3],
            "primary_color": result[4],
            "secondary_color": result[5]
        }
    
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Could not determine tenant from request"
    )

# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler"""
    logger.info("🚀 Starting OrbitEOS Platform")
    logger.info(f"📊 Database: {DATABASE_URL.split('@')[1]}")
    logger.info(f"⏱️  TimescaleDB: {TIMESCALEDB_URL.split('@')[1]}")
    
    # Test database connections
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ PostgreSQL connection successful")
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
    
    try:
        with timescale_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ TimescaleDB connection successful")
    except Exception as e:
        logger.error(f"❌ TimescaleDB connection failed: {e}")
    
    yield
    
    logger.info("🛑 Shutting down OrbitEOS Platform")

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
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "OrbitEOS Platform",
        "version": "1.0.0",
        "description": "Orbit Energy Operating System - Multi-tenant Energy Orchestration"
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "disconnected", "error": str(e)}
        )

@app.get("/api/v1/tenant/info")
async def get_tenant_info(
    request: Request,
    tenant: dict = Depends(get_tenant_from_request)
):
    """
    Get tenant information and branding
    
    Usage:
        GET /api/v1/tenant/info
        Header: X-User-Email: admin@ecoways.nl
        
        Returns Ecoways branding configuration
    """
    return {
        "tenant_id": tenant["id"],
        "tenant_code": tenant["code"],
        "tenant_name": tenant["name"],
        "branding": {
            "logo_url": tenant["logo_url"],
            "primary_color": tenant["primary_color"],
            "secondary_color": tenant["secondary_color"]
        }
    }

@app.post("/api/v1/auth/resolve-tenant")
async def resolve_tenant_from_email(
    email: str,
    db: Session = Depends(get_db)
):
    """
    Resolve tenant from email address
    
    Example:
        POST /api/v1/auth/resolve-tenant
        Body: {"email": "admin@ecoways.nl"}
        
        Returns: Ecoways tenant info
    """
    tenant = await get_tenant_from_email(email, db)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No tenant found for email domain: {extract_email_domain(email)}"
        )
    return tenant

@app.get("/api/v1/sites")
async def list_sites(
    request: Request,
    tenant: dict = Depends(get_tenant_from_request),
    db: Session = Depends(get_db)
):
    """List all sites for tenant"""
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
    
    return {
        "tenant": tenant["name"],
        "count": len(telemetry),
        "telemetry": telemetry
    }

# ============================================================================
# RUN APPLICATION
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv('PORT', 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
