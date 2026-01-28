-- OrbitEOS Platform - Multi-Tenant Database Schema

-- ============================================================================
-- TENANT MANAGEMENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_code VARCHAR(50) UNIQUE NOT NULL,  -- e.g., 'ecoways', 'orbiteos'
    tenant_name VARCHAR(255) NOT NULL,
    email_domain VARCHAR(255) NOT NULL,  -- e.g., '@ecoways.nl'
    
    -- Branding
    logo_url VARCHAR(500),
    primary_color VARCHAR(7),  -- Hex color #RRGGBB
    secondary_color VARCHAR(7),
    favicon_url VARCHAR(500),
    
    -- Configuration
    config JSONB DEFAULT '{}',
    features JSONB DEFAULT '{}',  -- Feature flags per tenant
    
    -- Subscription
    subscription_tier VARCHAR(50) DEFAULT 'trial',  -- trial, basic, professional, enterprise
    subscription_status VARCHAR(50) DEFAULT 'active',  -- active, suspended, cancelled
    subscription_starts_at TIMESTAMP,
    subscription_ends_at TIMESTAMP,
    
    -- Limits
    max_sites INTEGER DEFAULT 1,
    max_devices INTEGER DEFAULT 10,
    max_users INTEGER DEFAULT 5,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

-- Email domains for tenant identification
CREATE TABLE IF NOT EXISTS tenant_email_domains (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    email_domain VARCHAR(255) NOT NULL,  -- @ecoways.nl, @orbiteos.nl
    is_primary BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(email_domain)
);

CREATE INDEX IF NOT EXISTS idx_tenant_email_domains_domain 
    ON tenant_email_domains(email_domain);

-- ============================================================================
-- USER MANAGEMENT (Multi-tenant)
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Authentication
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    auth_provider VARCHAR(50) DEFAULT 'local',  -- local, google, microsoft
    auth_provider_id VARCHAR(255),
    
    -- Profile
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    phone VARCHAR(50),
    language VARCHAR(10) DEFAULT 'en',
    timezone VARCHAR(50) DEFAULT 'Europe/Amsterdam',
    
    -- Role & Permissions
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',  -- admin, operator, viewer
    permissions JSONB DEFAULT '[]',
    
    -- Status
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    last_login TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    
    UNIQUE(tenant_id, email)
);

CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================================================
-- SITES (Multi-tenant)
-- ============================================================================

CREATE TABLE IF NOT EXISTS sites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Site information
    site_code VARCHAR(50) NOT NULL,
    site_name VARCHAR(255) NOT NULL,
    site_type VARCHAR(100),  -- residential, commercial, industrial, charging_station
    
    -- Location
    address TEXT,
    city VARCHAR(100),
    postal_code VARCHAR(20),
    country VARCHAR(2) DEFAULT 'NL',
    latitude DECIMAL(9,6),
    longitude DECIMAL(9,6),
    
    -- Grid connection
    grid_connection_kw DECIMAL(10,2),
    grid_operator VARCHAR(100),
    grid_connection_id VARCHAR(100),
    
    -- Configuration
    config JSONB DEFAULT '{}',
    
    -- Status
    status VARCHAR(50) DEFAULT 'active',  -- active, inactive, maintenance
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    
    UNIQUE(tenant_id, site_code)
);

CREATE INDEX IF NOT EXISTS idx_sites_tenant ON sites(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sites_status ON sites(status);

-- ============================================================================
-- DEVICES (Multi-tenant)
-- ============================================================================

CREATE TABLE IF NOT EXISTS devices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    site_id UUID REFERENCES sites(id) ON DELETE CASCADE,
    
    -- Device identification
    device_id VARCHAR(255) NOT NULL,  -- External device ID
    device_type VARCHAR(100) NOT NULL,  -- pv_inverter, battery, ev_charger, smart_meter, hvac
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    serial_number VARCHAR(100),
    
    -- Device info
    name VARCHAR(255),
    location VARCHAR(255),  -- Physical location within site
    
    -- Technical specs
    rated_power_kw DECIMAL(10,2),
    capacity_kwh DECIMAL(10,2),  -- For batteries
    config JSONB DEFAULT '{}',
    
    -- Communication
    protocol VARCHAR(50),  -- modbus, ocpp, mqtt, rest
    connection_string TEXT,
    
    -- Status
    status VARCHAR(50) DEFAULT 'online',  -- online, offline, fault, maintenance
    last_seen TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,
    
    UNIQUE(tenant_id, site_id, device_id)
);

CREATE INDEX IF NOT EXISTS idx_devices_tenant ON devices(tenant_id);
CREATE INDEX IF NOT EXISTS idx_devices_site ON devices(site_id);
CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(device_type);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);

-- ============================================================================
-- WORKFLOWS (Multi-tenant)
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    site_id UUID REFERENCES sites(id) ON DELETE SET NULL,
    
    -- Workflow info
    name VARCHAR(255) NOT NULL,
    description TEXT,
    workflow_type VARCHAR(100),  -- peak_shaving, tariff_optimization, incident_response
    
    -- Definition
    definition JSONB NOT NULL,
    trigger_config JSONB DEFAULT '{}',
    
    -- Status
    status VARCHAR(50) DEFAULT 'active',  -- active, paused, archived
    
    -- Execution stats
    total_executions INTEGER DEFAULT 0,
    successful_executions INTEGER DEFAULT 0,
    failed_executions INTEGER DEFAULT 0,
    last_execution TIMESTAMP,
    
    -- Metadata
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workflows_tenant ON workflows(tenant_id);
CREATE INDEX IF NOT EXISTS idx_workflows_site ON workflows(site_id);
CREATE INDEX IF NOT EXISTS idx_workflows_status ON workflows(status);

-- ============================================================================
-- WORKFLOW EXECUTIONS (Multi-tenant)
-- ============================================================================

CREATE TABLE IF NOT EXISTS workflow_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    workflow_id UUID REFERENCES workflows(id) ON DELETE CASCADE,
    
    -- Execution details
    trigger_type VARCHAR(100),
    trigger_data JSONB,
    
    -- Status
    status VARCHAR(50),  -- running, success, failed, timeout
    result JSONB,
    error_message TEXT,
    
    -- Timing
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_ms INTEGER,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_workflow_executions_tenant ON workflow_executions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow ON workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_status ON workflow_executions(status);

-- ============================================================================
-- DECISIONS (Multi-tenant AI decisions)
-- ============================================================================

CREATE TABLE IF NOT EXISTS decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    site_id UUID REFERENCES sites(id) ON DELETE CASCADE,
    
    -- Decision details
    decision_type VARCHAR(100) NOT NULL,  -- optimize_battery, throttle_ev, curtail_pv
    agent_name VARCHAR(100),
    
    -- Context
    context JSONB,
    decision JSONB NOT NULL,
    confidence DECIMAL(5,2),  -- 0-100%
    rationale TEXT,
    
    -- Execution
    executed BOOLEAN DEFAULT FALSE,
    execution_result JSONB,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_decisions_tenant ON decisions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_decisions_site ON decisions(site_id);
CREATE INDEX IF NOT EXISTS idx_decisions_type ON decisions(decision_type);

-- ============================================================================
-- INCIDENTS (Multi-tenant)
-- ============================================================================

CREATE TABLE IF NOT EXISTS incidents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    site_id UUID REFERENCES sites(id) ON DELETE CASCADE,
    device_id UUID REFERENCES devices(id) ON DELETE SET NULL,
    
    -- Incident details
    title VARCHAR(255) NOT NULL,
    description TEXT,
    incident_type VARCHAR(100),  -- device_fault, grid_congestion, optimization_failure
    severity VARCHAR(50),  -- low, medium, high, critical
    
    -- Status
    status VARCHAR(50) DEFAULT 'open',  -- open, investigating, resolved, closed
    
    -- Assignment
    assigned_to UUID REFERENCES users(id),
    resolution TEXT,
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    closed_at TIMESTAMP,
    
    -- Metadata
    reported_by UUID REFERENCES users(id),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_incidents_tenant ON incidents(tenant_id);
CREATE INDEX IF NOT EXISTS idx_incidents_site ON incidents(site_id);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);

-- ============================================================================
-- AUDIT LOG (Multi-tenant)
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    
    -- Action details
    action_type VARCHAR(100) NOT NULL,  -- create, update, delete, execute
    resource_type VARCHAR(100),  -- device, workflow, user, site
    resource_id UUID,
    
    -- Actor
    actor_id UUID REFERENCES users(id),
    actor_email VARCHAR(255),
    
    -- Details
    details JSONB,
    
    -- Request info
    ip_address INET,
    user_agent TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource_type, resource_id);

-- ============================================================================
-- INSERT DEFAULT TENANTS
-- ============================================================================

-- Ecoways tenant
INSERT INTO tenants (
    tenant_code, 
    tenant_name, 
    email_domain,
    logo_url,
    primary_color,
    secondary_color,
    subscription_tier,
    subscription_status,
    max_sites,
    max_devices,
    max_users
) VALUES (
    'ecoways',
    'Ecoways',
    '@ecoways.nl',
    '/assets/logos/ecoways-logo.svg',
    '#00A86B',  -- Ecoways green
    '#0066CC',
    'enterprise',
    'active',
    100,
    1000,
    50
) ON CONFLICT (tenant_code) DO NOTHING;

-- OrbitEOS tenant (demo/default)
INSERT INTO tenants (
    tenant_code,
    tenant_name,
    email_domain,
    logo_url,
    primary_color,
    secondary_color,
    subscription_tier,
    subscription_status,
    max_sites,
    max_devices,
    max_users
) VALUES (
    'orbiteos',
    'OrbitEOS',
    '@orbiteos.nl',
    '/assets/logos/orbiteos-logo.svg',
    '#4A90E2',  -- OrbitEOS blue
    '#F39C12',  -- OrbitEOS orange
    'enterprise',
    'active',
    100,
    1000,
    50
) ON CONFLICT (tenant_code) DO NOTHING;

-- Insert email domains
INSERT INTO tenant_email_domains (tenant_id, email_domain, is_primary)
SELECT id, '@ecoways.nl', true FROM tenants WHERE tenant_code = 'ecoways'
ON CONFLICT (email_domain) DO NOTHING;

INSERT INTO tenant_email_domains (tenant_id, email_domain, is_primary)
SELECT id, '@ecoways.com', false FROM tenants WHERE tenant_code = 'ecoways'
ON CONFLICT (email_domain) DO NOTHING;

INSERT INTO tenant_email_domains (tenant_id, email_domain, is_primary)
SELECT id, '@orbiteos.nl', true FROM tenants WHERE tenant_code = 'orbiteos'
ON CONFLICT (email_domain) DO NOTHING;

INSERT INTO tenant_email_domains (tenant_id, email_domain, is_primary)
SELECT id, '@orbiteos.io', false FROM tenants WHERE tenant_code = 'orbiteos'
ON CONFLICT (email_domain) DO NOTHING;

-- ============================================================================
-- INSERT DEFAULT ADMIN USERS
-- ============================================================================

-- Ecoways admin (password: ecoways123 - CHANGE IN PRODUCTION!)
INSERT INTO users (tenant_id, email, password_hash, first_name, last_name, role, is_active, email_verified)
SELECT 
    id,
    'admin@ecoways.nl',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5lkW.6BI6XVG2',  -- bcrypt hash
    'Admin',
    'Ecoways',
    'admin',
    true,
    true
FROM tenants WHERE tenant_code = 'ecoways'
ON CONFLICT (tenant_id, email) DO NOTHING;

-- OrbitEOS admin (password: orbiteos123 - CHANGE IN PRODUCTION!)
INSERT INTO users (tenant_id, email, password_hash, first_name, last_name, role, is_active, email_verified)
SELECT 
    id,
    'admin@orbiteos.nl',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5lkW.6BI6XVG2',  -- bcrypt hash
    'Admin',
    'OrbitEOS',
    'admin',
    true,
    true
FROM tenants WHERE tenant_code = 'orbiteos'
ON CONFLICT (tenant_id, email) DO NOTHING;

-- ============================================================================
-- SAMPLE DEMO DATA
-- ============================================================================

-- Ecoways demo site
INSERT INTO sites (tenant_id, site_code, site_name, site_type, city, country, grid_connection_kw)
SELECT 
    id,
    'SITE-001',
    'Ecoways HQ - Utrecht',
    'commercial',
    'Utrecht',
    'NL',
    100.0
FROM tenants WHERE tenant_code = 'ecoways'
ON CONFLICT (tenant_id, site_code) DO NOTHING;

-- Ecoways demo devices
INSERT INTO devices (tenant_id, site_id, device_id, device_type, name, rated_power_kw, protocol, status)
SELECT 
    t.id,
    s.id,
    'pv-inverter-01',
    'pv_inverter',
    'Rooftop Solar Array',
    50.0,
    'modbus',
    'online'
FROM tenants t
CROSS JOIN sites s
WHERE t.tenant_code = 'ecoways' AND s.site_code = 'SITE-001'
ON CONFLICT (tenant_id, site_id, device_id) DO NOTHING;

INSERT INTO devices (tenant_id, site_id, device_id, device_type, name, rated_power_kw, capacity_kwh, protocol, status)
SELECT 
    t.id,
    s.id,
    'battery-01',
    'battery',
    'Main Battery Storage',
    50.0,
    100.0,
    'modbus',
    'online'
FROM tenants t
CROSS JOIN sites s
WHERE t.tenant_code = 'ecoways' AND s.site_code = 'SITE-001'
ON CONFLICT (tenant_id, site_id, device_id) DO NOTHING;

COMMIT;
