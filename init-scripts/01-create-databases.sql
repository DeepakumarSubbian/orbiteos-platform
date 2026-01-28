-- OrbitEOS Platform Database Initialization

-- Create databases
CREATE DATABASE IF NOT EXISTS orbiteos;
CREATE DATABASE IF NOT EXISTS openems;

-- Create users
CREATE USER IF NOT EXISTS orbiteos WITH PASSWORD 'orbiteos';
CREATE USER IF NOT EXISTS openems WITH PASSWORD 'openems';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE orbiteos TO orbiteos;
GRANT ALL PRIVILEGES ON DATABASE openems TO openems;

-- Connect to orbiteos database
\c orbiteos;

-- OrbitEOS Core Tables
CREATE TABLE IF NOT EXISTS workflows (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    definition JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workflow_executions (
    id SERIAL PRIMARY KEY,
    workflow_id INTEGER REFERENCES workflows(id),
    trigger_type VARCHAR(100),
    trigger_data JSONB,
    status VARCHAR(50),
    result JSONB,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS devices (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) UNIQUE NOT NULL,
    device_type VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    location VARCHAR(255),
    config JSONB,
    status VARCHAR(50) DEFAULT 'online',
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS telemetry (
    id SERIAL PRIMARY KEY,
    device_id VARCHAR(255) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    metric_value NUMERIC,
    unit VARCHAR(50),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_device_metric_time (device_id, metric_name, timestamp)
);

CREATE TABLE IF NOT EXISTS decisions (
    id SERIAL PRIMARY KEY,
    decision_type VARCHAR(100) NOT NULL,
    agent_name VARCHAR(100),
    context JSONB,
    decision JSONB NOT NULL,
    confidence NUMERIC,
    rationale TEXT,
    executed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    severity VARCHAR(50),
    status VARCHAR(50) DEFAULT 'open',
    device_id VARCHAR(255),
    assigned_to VARCHAR(255),
    resolution TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    action_type VARCHAR(100) NOT NULL,
    actor VARCHAR(255),
    target_type VARCHAR(100),
    target_id VARCHAR(255),
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_workflow_executions_status ON workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_workflow_executions_workflow_id ON workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_devices_type ON devices(device_type);
CREATE INDEX IF NOT EXISTS idx_devices_status ON devices(status);
CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status);
CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(created_at);

-- Insert sample data
INSERT INTO devices (device_id, device_type, name, location, status) VALUES
    ('pv-inverter-01', 'pv_inverter', 'Main PV Array', 'Roof Section A', 'online'),
    ('battery-01', 'battery', 'Main Battery Storage', 'Equipment Room', 'online'),
    ('EV-CHARGER-01', 'ev_charger', 'Parking Lot Charger 1', 'Parking Area', 'online'),
    ('smart-meter-01', 'smart_meter', 'Grid Connection Meter', 'Main Switchboard', 'online')
ON CONFLICT (device_id) DO NOTHING;

-- Sample workflow
INSERT INTO workflows (name, description, definition) VALUES
    (
        'Peak Load Management',
        'Automatically reduce EV charging during peak load conditions',
        '{"trigger": "load_threshold", "threshold_kw": 80, "actions": ["throttle_ev_charging", "notify_operator"]}'::jsonb
    )
ON CONFLICT DO NOTHING;

COMMIT;
