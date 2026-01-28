# OrbitEOS Multi-Tenant Architecture Guide

**Version:** 1.0  
**Date:** January 2026  
**Audience:** Developers, System Architects, DevOps

---

## 🎯 Overview

OrbitEOS Platform is now a **fully multi-tenant SaaS system** where:
- Each tenant (customer/organization) has **isolated data**
- **Email domain determines tenant** (e.g., `@ecoways.nl` → Ecoways tenant)
- **Custom branding** per tenant (logo, colors)
- **Separate subscription limits** per tenant
- **Complete data isolation** in both PostgreSQL and TimescaleDB

---

## 🏢 Tenant Examples

| Tenant | Email Domain | Logo | Primary Color | Use Case |
|--------|--------------|------|---------------|----------|
| **Ecoways** | `@ecoways.nl` | Ecoways logo | `#00A86B` (Green) | Dutch energy management company |
| **OrbitEOS** | `@orbiteos.nl`, `@orbiteos.io` | OrbitEOS logo | `#4A90E2` (Blue) | Default/demo tenant |

---

## 🔐 How Tenant Resolution Works

### Method 1: Email Domain (Primary)

```http
POST /api/v1/auth/resolve-tenant
Content-Type: application/json

{
  "email": "admin@ecoways.nl"
}
```

**Response:**
```json
{
  "id": "uuid-here",
  "code": "ecoways",
  "name": "Ecoways",
  "logo_url": "/assets/logos/ecoways-logo.svg",
  "primary_color": "#00A86B",
  "secondary_color": "#0066CC"
}
```

### Method 2: Custom Header

```http
GET /api/v1/sites
X-Tenant-ID: uuid-here
X-User-Email: admin@ecoways.nl
```

### Method 3: Query Parameter

```http
GET /api/v1/sites?tenant=ecoways
```

### Method 4: Subdomain

```
https://ecoways.orbiteos.nl/api/v1/sites
                  ↓
        Tenant: Ecoways
```

---

## 📊 Database Schema

### Multi-Tenant Tables (PostgreSQL)

All application tables include `tenant_id`:

```sql
-- Tenants table
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    tenant_code VARCHAR(50) UNIQUE,
    tenant_name VARCHAR(255),
    email_domain VARCHAR(255),
    logo_url VARCHAR(500),
    primary_color VARCHAR(7),
    secondary_color VARCHAR(7),
    subscription_tier VARCHAR(50),
    max_sites INTEGER,
    max_devices INTEGER,
    max_users INTEGER
);

-- Sites (per tenant)
CREATE TABLE sites (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    site_code VARCHAR(50),
    site_name VARCHAR(255),
    city VARCHAR(100),
    grid_connection_kw DECIMAL
);

-- Devices (per tenant & site)
CREATE TABLE devices (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    site_id UUID REFERENCES sites(id),
    device_id VARCHAR(255),
    device_type VARCHAR(100),
    name VARCHAR(255)
);
```

### Time-Series Data (TimescaleDB)

```sql
-- Telemetry (multi-tenant)
CREATE TABLE device_telemetry (
    time TIMESTAMPTZ NOT NULL,
    tenant_id UUID NOT NULL,
    device_id VARCHAR(255),
    metric_name VARCHAR(100),
    value DOUBLE PRECISION,
    PRIMARY KEY (time, tenant_id, device_id, metric_name)
);

-- Hypertable with tenant-aware compression
SELECT create_hypertable('device_telemetry', 'time');
ALTER TABLE device_telemetry SET (
    timescaledb.compress_segmentby = 'tenant_id, device_id'
);
```

---

## 🎨 Branding System

### Tenant Configuration

Each tenant has custom branding stored in database:

```sql
SELECT 
    tenant_code,
    logo_url,
    primary_color,
    secondary_color
FROM tenants;
```

| Tenant | Logo Path | Primary | Secondary |
|--------|-----------|---------|-----------|
| ecoways | `/assets/logos/ecoways-logo.svg` | `#00A86B` | `#0066CC` |
| orbiteos | `/assets/logos/orbiteos-logo.svg` | `#4A90E2` | `#F39C12` |

### Frontend Integration

```javascript
// Fetch tenant branding
const response = await fetch('/api/v1/tenant/info', {
    headers: {
        'X-User-Email': 'admin@ecoways.nl'
    }
});

const tenant = await response.json();

// Apply branding
document.documentElement.style.setProperty('--primary-color', tenant.branding.primary_color);
document.getElementById('logo').src = tenant.branding.logo_url;
document.title = `${tenant.tenant_name} - Energy Management`;
```

---

## 🔧 API Usage Examples

### 1. List Sites for Tenant

```bash
curl -X GET "http://localhost:8000/api/v1/sites" \
  -H "X-User-Email: admin@ecoways.nl"
```

**Response:**
```json
{
  "tenant": "Ecoways",
  "count": 1,
  "sites": [
    {
      "id": "uuid",
      "site_code": "SITE-001",
      "name": "Ecoways HQ - Utrecht",
      "type": "commercial",
      "city": "Utrecht",
      "status": "active"
    }
  ]
}
```

### 2. List Devices for Tenant

```bash
curl -X GET "http://localhost:8000/api/v1/devices?site_id=uuid" \
  -H "X-User-Email: admin@ecoways.nl"
```

**Response:**
```json
{
  "tenant": "Ecoways",
  "count": 2,
  "devices": [
    {
      "device_id": "pv-inverter-01",
      "type": "pv_inverter",
      "name": "Rooftop Solar Array",
      "rated_power_kw": 50.0,
      "status": "online"
    },
    {
      "device_id": "battery-01",
      "type": "battery",
      "name": "Main Battery Storage",
      "rated_power_kw": 50.0,
      "status": "online"
    }
  ]
}
```

### 3. Get Latest Telemetry

```bash
curl -X GET "http://localhost:8000/api/v1/telemetry/latest?device_id=pv-inverter-01" \
  -H "X-User-Email: admin@ecoways.nl"
```

**Response:**
```json
{
  "tenant": "Ecoways",
  "telemetry": [
    {
      "timestamp": "2026-01-19T14:30:00Z",
      "device_id": "pv-inverter-01",
      "metric": "power_kw",
      "value": 45.5,
      "unit": "kW"
    }
  ]
}
```

---

## 🚀 Adding a New Tenant

### Step 1: Insert Tenant Record

```sql
INSERT INTO tenants (
    tenant_code,
    tenant_name,
    email_domain,
    logo_url,
    primary_color,
    secondary_color,
    subscription_tier,
    max_sites,
    max_devices
) VALUES (
    'newcompany',
    'New Company BV',
    '@newcompany.nl',
    '/assets/logos/newcompany-logo.svg',
    '#FF6B35',  -- Orange
    '#004E89',  -- Blue
    'professional',
    10,
    100
);
```

### Step 2: Add Email Domains

```sql
INSERT INTO tenant_email_domains (tenant_id, email_domain, is_primary)
SELECT id, '@newcompany.nl', true FROM tenants WHERE tenant_code = 'newcompany';

INSERT INTO tenant_email_domains (tenant_id, email_domain, is_primary)
SELECT id, '@newcompany.com', false FROM tenants WHERE tenant_code = 'newcompany';
```

### Step 3: Create Admin User

```sql
INSERT INTO users (tenant_id, email, password_hash, role)
SELECT 
    id,
    'admin@newcompany.nl',
    '$2b$12$...',  -- Use bcrypt
    'admin'
FROM tenants WHERE tenant_code = 'newcompany';
```

### Step 4: Upload Logo

```bash
# Copy logo to assets directory
cp newcompany-logo.svg /assets/logos/

# Or use CDN URL
UPDATE tenants 
SET logo_url = 'https://cdn.newcompany.nl/logo.svg'
WHERE tenant_code = 'newcompany';
```

---

## 🔒 Data Isolation Guarantees

### Row-Level Security (RLS)

All queries are automatically filtered by `tenant_id`:

```python
# Backend automatically adds tenant_id filter
@app.get("/api/v1/sites")
async def list_sites(tenant: dict = Depends(get_tenant_from_request)):
    # Query automatically includes WHERE tenant_id = tenant["id"]
    query = "SELECT * FROM sites WHERE tenant_id = :tenant_id"
```

### Time-Series Isolation

TimescaleDB queries include `tenant_id` in WHERE clause:

```sql
SELECT * FROM device_telemetry
WHERE tenant_id = :tenant_id
  AND time > NOW() - INTERVAL '1 hour';
```

### Index Optimization

All indexes include `tenant_id` for performance:

```sql
CREATE INDEX idx_devices_tenant 
    ON devices(tenant_id, device_type, status);
```

---

## 📈 Subscription Tiers

| Tier | Max Sites | Max Devices | Max Users | Price/Month |
|------|-----------|-------------|-----------|-------------|
| **Trial** | 1 | 10 | 2 | Free |
| **Basic** | 5 | 50 | 5 | €199 |
| **Professional** | 20 | 200 | 20 | €499 |
| **Enterprise** | Unlimited | Unlimited | Unlimited | Custom |

### Enforcing Limits

```python
@app.post("/api/v1/sites")
async def create_site(tenant: dict, db: Session):
    # Check limit
    current_count = db.execute(text(
        "SELECT COUNT(*) FROM sites WHERE tenant_id = :tenant_id"
    ), {"tenant_id": tenant["id"]}).scalar()
    
    max_sites = db.execute(text(
        "SELECT max_sites FROM tenants WHERE id = :tenant_id"
    ), {"tenant_id": tenant["id"]}).scalar()
    
    if current_count >= max_sites:
        raise HTTPException(403, "Site limit reached")
```

---

## 🎨 Frontend Branding Example

### React Component

```jsx
import { useEffect, useState } from 'react';

function App() {
    const [tenant, setTenant] = useState(null);
    
    useEffect(() => {
        // Get tenant from email
        const email = localStorage.getItem('userEmail');
        
        fetch('/api/v1/auth/resolve-tenant', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        })
        .then(res => res.json())
        .then(data => {
            setTenant(data);
            
            // Apply branding
            document.documentElement.style.setProperty(
                '--primary-color', 
                data.primary_color
            );
            document.documentElement.style.setProperty(
                '--secondary-color', 
                data.secondary_color
            );
        });
    }, []);
    
    if (!tenant) return <div>Loading...</div>;
    
    return (
        <div className="app">
            <header>
                <img src={tenant.logo_url} alt={tenant.name} />
                <h1>{tenant.name} Energy Platform</h1>
            </header>
            {/* Rest of app */}
        </div>
    );
}
```

### CSS Variables

```css
:root {
    --primary-color: #4A90E2;  /* Dynamically set */
    --secondary-color: #F39C12;
}

.btn-primary {
    background-color: var(--primary-color);
}

.header {
    border-bottom: 2px solid var(--secondary-color);
}
```

---

## 🧪 Testing Multi-Tenancy

### Test 1: Ecoways User

```bash
# Login as Ecoways user
curl -X GET "http://localhost:8000/api/v1/sites" \
  -H "X-User-Email: admin@ecoways.nl"

# Should only see Ecoways sites
```

### Test 2: OrbitEOS User

```bash
# Login as OrbitEOS user
curl -X GET "http://localhost:8000/api/v1/sites" \
  -H "X-User-Email: admin@orbiteos.nl"

# Should only see OrbitEOS sites (different from Ecoways)
```

### Test 3: Data Isolation

```bash
# Ecoways creates device
curl -X POST "http://localhost:8000/api/v1/devices" \
  -H "X-User-Email: admin@ecoways.nl" \
  -d '{"device_id": "battery-ecoways", "name": "Ecoways Battery"}'

# OrbitEOS tries to access it (should fail or return empty)
curl -X GET "http://localhost:8000/api/v1/devices/battery-ecoways" \
  -H "X-User-Email: admin@orbiteos.nl"

# Returns 404 or empty - data is isolated!
```

---

## 🔐 Security Considerations

### 1. Always Filter by Tenant ID

```python
# ✅ CORRECT
query = "SELECT * FROM devices WHERE tenant_id = :tenant_id AND device_id = :device_id"

# ❌ WRONG - Missing tenant_id filter!
query = "SELECT * FROM devices WHERE device_id = :device_id"
```

### 2. Validate Tenant Access

```python
# Check user belongs to tenant
def validate_user_tenant(user_id: str, tenant_id: str):
    result = db.execute(text(
        "SELECT 1 FROM users WHERE id = :user_id AND tenant_id = :tenant_id"
    ), {"user_id": user_id, "tenant_id": tenant_id}).scalar()
    
    if not result:
        raise HTTPException(403, "Access denied")
```

### 3. Prevent Tenant Hopping

```python
# Never trust tenant_id from user input!
# Always resolve from authentication token
tenant = get_tenant_from_authenticated_user()
```

---

## 📊 Monitoring & Analytics

### Per-Tenant Metrics

```sql
-- Device count per tenant
SELECT 
    t.tenant_name,
    COUNT(d.id) as device_count
FROM tenants t
LEFT JOIN devices d ON t.id = d.tenant_id
GROUP BY t.tenant_name;

-- Data volume per tenant
SELECT 
    tenant_id,
    COUNT(*) as data_points,
    pg_size_pretty(pg_total_relation_size('device_telemetry')) as storage
FROM device_telemetry
GROUP BY tenant_id;
```

---

## 🚀 Deployment Checklist

- [ ] Create tenant record in database
- [ ] Add email domains
- [ ] Upload tenant logo to CDN
- [ ] Create admin user
- [ ] Configure subscription tier & limits
- [ ] Test tenant resolution
- [ ] Test data isolation
- [ ] Configure branding in frontend
- [ ] Set up monitoring
- [ ] Document custom configuration

---

## 📞 Support

**Questions?** Contact: support@orbiteos.nl  
**Documentation:** https://docs.orbiteos.io/multi-tenancy  
**Issues:** https://github.com/orbiteos/platform/issues

---

**OrbitEOS Platform - Powering the Multi-Tenant Energy Transition**
