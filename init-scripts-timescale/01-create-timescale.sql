-- OrbitEOS Platform - TimescaleDB Initialization
-- Time-series database for energy data

-- Create TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- ============================================================================
-- TELEMETRY DATA (High-frequency measurements)
-- ============================================================================

CREATE TABLE IF NOT EXISTS device_telemetry (
    time TIMESTAMPTZ NOT NULL,
    tenant_id UUID NOT NULL,
    device_id VARCHAR(255) NOT NULL,
    metric_name VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION,
    unit VARCHAR(50),
    quality VARCHAR(20) DEFAULT 'good'
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('device_telemetry', 'time', if_not_exists => TRUE);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_device_telemetry_tenant
    ON device_telemetry (tenant_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_device_telemetry_device_id
    ON device_telemetry (tenant_id, device_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_device_telemetry_metric
    ON device_telemetry (tenant_id, metric_name, time DESC);

-- ============================================================================
-- ENERGY FLOWS (Power measurements at 5-second resolution)
-- ============================================================================

CREATE TABLE IF NOT EXISTS energy_flows (
    time TIMESTAMPTZ NOT NULL,
    tenant_id UUID NOT NULL,
    site_id VARCHAR(255) NOT NULL,
    pv_power_kw DOUBLE PRECISION,
    battery_power_kw DOUBLE PRECISION,
    ev_power_kw DOUBLE PRECISION,
    grid_power_kw DOUBLE PRECISION,
    load_power_kw DOUBLE PRECISION,
    soc_percent DOUBLE PRECISION
);

SELECT create_hypertable('energy_flows', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_energy_flows_tenant
    ON energy_flows (tenant_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_energy_flows_site
    ON energy_flows (tenant_id, site_id, time DESC);

-- ============================================================================
-- FORECASTS (AI/ML predictions)
-- ============================================================================

CREATE TABLE IF NOT EXISTS forecasts (
    time TIMESTAMPTZ NOT NULL,
    forecast_time TIMESTAMPTZ NOT NULL,
    forecast_type VARCHAR(100) NOT NULL,
    site_id VARCHAR(255),
    predicted_value DOUBLE PRECISION,
    confidence_lower DOUBLE PRECISION,
    confidence_upper DOUBLE PRECISION,
    model_version VARCHAR(50)
);

SELECT create_hypertable('forecasts', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_forecasts_type
    ON forecasts (forecast_type, forecast_time DESC);

-- ============================================================================
-- PRICE DATA (Dynamic tariffs)
-- ============================================================================

CREATE TABLE IF NOT EXISTS energy_prices (
    time TIMESTAMPTZ NOT NULL,
    price_type VARCHAR(50) NOT NULL,
    market VARCHAR(100),
    price_eur_kwh DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) DEFAULT 'EUR'
);

SELECT create_hypertable('energy_prices', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_energy_prices_market
    ON energy_prices (market, time DESC);

-- ============================================================================
-- OPTIMIZATION RESULTS (Decision outcomes)
-- ============================================================================

CREATE TABLE IF NOT EXISTS optimization_results (
    time TIMESTAMPTZ NOT NULL,
    optimization_id UUID NOT NULL,
    site_id VARCHAR(255),
    objective VARCHAR(100),
    result JSONB,
    execution_time_ms INTEGER,
    cost_savings_eur DOUBLE PRECISION
);

SELECT create_hypertable('optimization_results', 'time', if_not_exists => TRUE);

-- ============================================================================
-- GRID EVENTS (Congestion, outages, etc.)
-- ============================================================================

CREATE TABLE IF NOT EXISTS grid_events (
    time TIMESTAMPTZ NOT NULL,
    event_id UUID NOT NULL,
    site_id VARCHAR(255),
    event_type VARCHAR(100),
    severity VARCHAR(20),
    description TEXT,
    resolved_at TIMESTAMPTZ
);

SELECT create_hypertable('grid_events', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_grid_events_type
    ON grid_events (event_type, time DESC);

-- ============================================================================
-- SAMPLE DATA FOR TESTING
-- ============================================================================

-- Insert sample telemetry with demo tenant UUID
INSERT INTO device_telemetry (time, tenant_id, device_id, metric_name, value, unit) VALUES
    (NOW() - INTERVAL '1 hour', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'PV001', 'solar_power', 3200, 'W'),
    (NOW() - INTERVAL '1 hour', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'BAT001', 'battery_soc', 72, '%'),
    (NOW() - INTERVAL '1 hour', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'BAT001', 'battery_power', 1800, 'W'),
    (NOW() - INTERVAL '1 hour', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'GRID001', 'grid_power', -800, 'W'),
    (NOW() - INTERVAL '1 hour', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'HOME', 'consumption_power', 2400, 'W'),
    (NOW() - INTERVAL '30 minutes', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'PV001', 'solar_power', 3500, 'W'),
    (NOW() - INTERVAL '30 minutes', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'BAT001', 'battery_soc', 75, '%'),
    (NOW() - INTERVAL '30 minutes', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'BAT001', 'battery_power', 1500, 'W'),
    (NOW() - INTERVAL '30 minutes', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'GRID001', 'grid_power', -1000, 'W'),
    (NOW() - INTERVAL '30 minutes', 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'HOME', 'consumption_power', 2500, 'W'),
    (NOW(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'PV001', 'solar_power', 3000, 'W'),
    (NOW(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'BAT001', 'battery_soc', 78, '%'),
    (NOW(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'BAT001', 'battery_power', 1200, 'W'),
    (NOW(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'GRID001', 'grid_power', -600, 'W'),
    (NOW(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'HOME', 'consumption_power', 2200, 'W');

-- Insert sample energy flow
INSERT INTO energy_flows (time, tenant_id, site_id, pv_power_kw, battery_power_kw, grid_power_kw, soc_percent) VALUES
    (NOW(), 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11'::UUID, 'DEMO001', 3.0, 1.2, -0.6, 78.0);

-- Insert sample price data
INSERT INTO energy_prices (time, price_type, market, price_eur_kwh) VALUES
    (NOW(), 'day_ahead', 'EPEX_NL', 0.25),
    (NOW(), 'feed_in', 'NL', 0.08);
