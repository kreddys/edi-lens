# Testing and Debugging Guide

## Overview

This guide covers testing strategies, debugging techniques, and authentication handling for the NiFi workflow architecture implementation.

## Testing Strategy

### Test Environment Setup

The project uses a comprehensive Docker-based testing environment with multiple test types:

```bash
# Start development environment (auto-reloads on code changes)
./run.sh dev:start

# Check service health
docker ps
./run.sh dev:logs backend
```

### Test Types

#### 1. Unit Tests (Fast, No Docker)
```bash
# Run unit tests - fastest execution, no external dependencies
./run.sh dev:test unit tests/api/test_edi_validation.py -v

# Run specific unit test
./run.sh dev:test unit tests/api/test_edi_validation.py::TestClass::test_method -v
```

#### 2. Integration Tests (With Docker Stack)
```bash
# Run integration tests - tests against real services
./run.sh dev:test integration tests/api/test_edi_validation.py -v

# Run all API integration tests
./run.sh dev:test integration tests/api/ -v
```

#### 3. End-to-End Tests (Full System)
```bash
# Run E2E tests - full system with Keycloak + SFTPGo setup
./run.sh dev:test e2e tests/api/test_edi_validation.py -v
```

### Test Markers

Tests use pytest markers for categorization:

```python
@pytest.mark.unit         # Fast, isolated tests with mocks
@pytest.mark.integration  # Tests against Docker services
@pytest.mark.e2e         # Full system tests
```

## Architecture & Networking

### Service Topology

```
External → Caddy (Reverse Proxy) → Backend Services
Port 3001     ↓
            /api/* → backend:8000
            /minio/* → minio:9001
            /* → admin-ui:3000
```

### Key Ports
- **3001**: Main application (via Caddy)
- **8081**: Keycloak admin UI
- **8082**: SFTPGo admin UI
- **9001**: MinIO console
- **2022**: SFTP server

### Internal vs External Access

**External Testing (through Caddy):**
```bash
curl http://localhost:3001/api/v1/health
curl http://localhost:3001/api/v1/edi/validate-realtime
```

**Internal Testing (direct to backend):**
```bash
docker exec backend curl http://localhost:8000/api/v1/health
```

**Test Framework (ASGI Transport):**
```python
# Tests use FastAPI TestClient with ASGITransport
# This bypasses Docker networking and tests app logic directly
async with AsyncClient(transport=transport, base_url="http://test") as client:
    response = await client.post("/api/v1/edi/validate-realtime", ...)
```

## Authentication & Authorization

### Service Authentication for NiFi

The EDI processing endpoints use service-to-service authentication:

```python
# Service authentication dependency
@router.post("/validate-realtime")
async def validate_realtime_edi(
    request: RealtimeEDIValidationRequest,
    auth: AuthContext = Depends(require_service_auth)  # <-- Service auth
):
```

### Authentication Token Structure

Service tokens must include:
```json
{
    "azp": "nifi-service",           // Authorized party (client)
    "preferred_username": "nifi-processor",
    "aud": "edi-lens-api",          // Audience
    "sub": "service-account-nifi",   // Subject
    "iat": 1640995200,              // Issued at
    "exp": 1640995800               // Expiration
}
```

### Getting Authentication Tokens

Use the Python helper script for debugging:

```bash
# Get service token for testing
python scripts/get_auth_token.py --service nifi-service

# Get user token for manual testing  
python scripts/get_auth_token.py --user admin --password admin --tenant tenant-a

# Test endpoint with token
TOKEN=$(python scripts/get_auth_token.py --service nifi-service)
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"edi_content":"...","tenant_id":"tenant-a","workflow_id":"test","validation_schema":"837.5010.X222.A1.json"}' \
     http://localhost:3001/api/v1/edi/validate-realtime

# Verbose output for debugging
python scripts/get_auth_token.py --service nifi-service --verbose
```

## Debugging Strategies

### 1. Endpoint Discovery

Check available routes:
```bash
docker exec backend python -c "
from src.main import app
print('Available routes:')
for route in app.routes:
    if hasattr(route, 'path'):
        print(f'{route.methods} {route.path}')
"
```

### 2. Test Endpoint Directly

```bash
# Test with FastAPI TestClient
docker exec backend python -c "
from src.main import app
from fastapi.testclient import TestClient
client = TestClient(app)
response = client.get('/api/v1/health')
print('Health check:', response.status_code)
response = client.post('/api/v1/edi/validate-realtime')  
print('EDI endpoint:', response.status_code, response.json())
"
```

### 3. Authentication Debugging

```bash
# Test service auth endpoint
docker exec backend python -c "
from src.core.auth import require_service_auth
print('Service auth dependency available')
"
```

### 4. Schema Import Issues

Check import paths:
```bash
docker exec backend python -c "
from src.api.schemas import RealtimeEDIValidationRequest
print('Schema import successful')
"
```

### 5. Container Health Monitoring

```bash
# Check container status
docker ps --filter "name=backend"

# Check backend logs
./run.sh dev:logs backend

# Check specific service logs
./run.sh dev:logs keycloak
./run.sh dev:logs sftpgo
```

## Common Issues & Solutions

### 1. Import Errors
**Problem**: `ModuleNotFoundError: No module named 'src.api.schemas.edi_schemas'`

**Cause**: Conflicting directory structure (both `schemas.py` file and `schemas/` directory)

**Solution**: Use single `schemas.py` file, avoid nested schema directories

### 2. Route Prefix Issues
**Problem**: Routes appear as `/api/v1/api/v1/edi/...`

**Cause**: Double prefix - router defines `/api/v1/edi` but main app adds `/api/v1`

**Solution**: Use relative prefix in router: `APIRouter(prefix="/edi")`

### 3. Authentication Failures
**Problem**: `401 Unauthorized` or `Not enough segments`

**Cause**: Invalid JWT token format or missing service client configuration

**Solution**: Use proper token structure with correct `azp` field

### 4. Container Networking
**Problem**: `Connection refused` when testing endpoints

**Cause**: Testing wrong port or not using Caddy reverse proxy

**Solution**: Use port 3001 (Caddy) for external testing, or test inside container

## Development Workflow

### 1. Code Changes
```bash
# Start development environment
./run.sh dev:start

# Make code changes (auto-reload enabled)
# No need to restart containers for code changes

# Test changes
./run.sh dev:test integration tests/api/test_edi_validation.py -v
```

### 2. Docker Configuration Changes
```bash
# If changing Docker configs or environment variables
./run.sh dev:stop
./run.sh dev:start
```

### 3. Testing New Endpoints
```bash
# 1. Check endpoint is registered
docker exec backend python -c "from src.main import app; [print(f'{r.methods} {r.path}') for r in app.routes if hasattr(r, 'path')]"

# 2. Test authentication
TOKEN=$(python scripts/get_auth_token.py --service nifi-service)
curl -H "Authorization: Bearer $TOKEN" http://localhost:3001/api/v1/edi/validate-realtime

# 3. Run integration tests
./run.sh dev:test integration tests/api/test_edi_validation.py -v
```

### 4. Debugging Failed Tests
```bash
# Run with verbose output
./run.sh dev:test integration tests/api/test_edi_validation.py::TestClass::test_method -v -s

# Check container logs during test
./run.sh dev:logs backend

# Test manually with curl
curl -v -X POST http://localhost:3001/api/v1/edi/validate-realtime \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"edi_content":"test","tenant_id":"test","workflow_id":"test","validation_schema":"test"}'
```

## Performance Testing

### Load Testing EDI Endpoints
```bash
# Install load testing tools
pip install locust

# Run load tests
locust -f tests/load/test_edi_validation.py --host=http://localhost:3001
```

### Monitoring During Tests
```bash
# Monitor container resources
docker stats

# Monitor backend logs
./run.sh dev:logs backend -f

# Check database connections
docker exec db-app psql -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT count(*) FROM pg_stat_activity;"
```

## Security Testing

### Authentication Testing
```bash
# Test without token
curl -X POST http://localhost:3001/api/v1/edi/validate-realtime

# Test with invalid token
curl -H "Authorization: Bearer invalid-token" http://localhost:3001/api/v1/edi/validate-realtime

# Test with expired token
curl -H "Authorization: Bearer $EXPIRED_TOKEN" http://localhost:3001/api/v1/edi/validate-realtime
```

### Tenant Isolation Testing
```bash
# Test cross-tenant access
TOKEN_A=$(python scripts/get_auth_token.py --user admin --password admin --tenant tenant-a)
curl -H "Authorization: Bearer $TOKEN_A" \
  -d '{"tenant_id":"tenant-b",...}' \
  http://localhost:3001/api/v1/edi/validate-realtime
```

This comprehensive testing and debugging guide ensures reliable development and deployment of the NiFi workflow architecture.