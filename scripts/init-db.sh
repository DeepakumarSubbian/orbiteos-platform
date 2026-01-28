#!/bin/bash
set -e

# Create multiple databases
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    -- Create OrbitEOS database
    CREATE DATABASE orbiteos;

    -- Create OpenEMS database
    CREATE DATABASE openems;

    -- Connect to orbiteos database and create schema
    \c orbiteos

    -- Tenants table
    CREATE TABLE IF NOT EXISTS tenants (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_code VARCHAR(50) UNIQUE NOT NULL,
        tenant_name VARCHAR(255) NOT NULL,
        logo_url TEXT,
        primary_color VARCHAR(7) DEFAULT '#00A86B',
        secondary_color VARCHAR(7) DEFAULT '#0066CC',
        config JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Tenant email domains
    CREATE TABLE IF NOT EXISTS tenant_email_domains (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID REFERENCES tenants(id),
        email_domain VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Sites table
    CREATE TABLE IF NOT EXISTS sites (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID REFERENCES tenants(id),
        site_code VARCHAR(50) NOT NULL,
        site_name VARCHAR(255) NOT NULL,
        site_type VARCHAR(50) DEFAULT 'residential',
        address TEXT,
        city VARCHAR(100),
        country VARCHAR(2),
        latitude DECIMAL(10, 8),
        longitude DECIMAL(11, 8),
        timezone VARCHAR(50) DEFAULT 'Europe/Amsterdam',
        grid_connection_kw DECIMAL(10, 2),
        status VARCHAR(20) DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Devices table
    CREATE TABLE IF NOT EXISTS devices (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id UUID REFERENCES tenants(id),
        site_id UUID REFERENCES sites(id),
        device_id VARCHAR(100) NOT NULL,
        device_type VARCHAR(50) NOT NULL,
        name VARCHAR(255),
        manufacturer VARCHAR(100),
        model VARCHAR(100),
        rated_power_kw DECIMAL(10, 2),
        capacity_kwh DECIMAL(10, 2),
        modbus_address INTEGER,
        status VARCHAR(20) DEFAULT 'online',
        config JSONB DEFAULT '{}',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- Insert demo tenant
    INSERT INTO tenants (tenant_code, tenant_name, primary_color, secondary_color)
    VALUES ('demo', 'Demo Tenant', '#00A86B', '#0066CC')
    ON CONFLICT (tenant_code) DO NOTHING;

    -- Insert demo site
    INSERT INTO sites (tenant_id, site_code, site_name, site_type, city, country, grid_connection_kw)
    SELECT id, 'DEMO001', 'Demo Home', 'residential', 'Amsterdam', 'NL', 25.0
    FROM tenants WHERE tenant_code = 'demo'
    ON CONFLICT DO NOTHING;

    -- Insert demo devices
    INSERT INTO devices (tenant_id, site_id, device_id, device_type, name, rated_power_kw, capacity_kwh)
    SELECT t.id, s.id, 'PV001', 'solar', 'Rooftop Solar', 6.0, NULL
    FROM tenants t JOIN sites s ON s.tenant_id = t.id
    WHERE t.tenant_code = 'demo' AND s.site_code = 'DEMO001'
    ON CONFLICT DO NOTHING;

    INSERT INTO devices (tenant_id, site_id, device_id, device_type, name, rated_power_kw, capacity_kwh)
    SELECT t.id, s.id, 'BAT001', 'battery', 'Tesla Powerwall', 5.0, 13.5
    FROM tenants t JOIN sites s ON s.tenant_id = t.id
    WHERE t.tenant_code = 'demo' AND s.site_code = 'DEMO001'
    ON CONFLICT DO NOTHING;

    INSERT INTO devices (tenant_id, site_id, device_id, device_type, name, rated_power_kw, capacity_kwh)
    SELECT t.id, s.id, 'GRID001', 'meter', 'Grid Meter', 25.0, NULL
    FROM tenants t JOIN sites s ON s.tenant_id = t.id
    WHERE t.tenant_code = 'demo' AND s.site_code = 'DEMO001'
    ON CONFLICT DO NOTHING;

    INSERT INTO devices (tenant_id, site_id, device_id, device_type, name, rated_power_kw, capacity_kwh)
    SELECT t.id, s.id, 'EV001', 'ev_charger', 'EV Charger', 11.0, NULL
    FROM tenants t JOIN sites s ON s.tenant_id = t.id
    WHERE t.tenant_code = 'demo' AND s.site_code = 'DEMO001'
    ON CONFLICT DO NOTHING;

    -- Create indexes
    CREATE INDEX IF NOT EXISTS idx_sites_tenant ON sites(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_devices_tenant ON devices(tenant_id);
    CREATE INDEX IF NOT EXISTS idx_devices_site ON devices(site_id);

EOSQL

echo "Database initialization completed successfully!"
