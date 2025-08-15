# Authentication Quick Reference

Quick reference for EDI Lens authentication configuration and token usage.

## 🔧 Environment Variables

```bash
# Copy to .env.dev and customize
KEYCLOAK_BROWSER_URL=http://localhost:8081
KEYCLOAK_REALM=edi-lens

# Main clients
KEYCLOAK_BACKEND_CLIENT_ID=edi-lens-backend
KEYCLOAK_BACKEND_CLIENT_SECRET=your-backend-secret
KEYCLOAK_UI_CLIENT_ID=edi-lens-ui

# Service accounts
KEYCLOAK_NIFI_CLIENT_ID=nifi-service
KEYCLOAK_NIFI_CLIENT_SECRET=nifi-service-secret
KEYCLOAK_SFTPGO_CLIENT_ID=sftpgo
KEYCLOAK_SFTPGO_CLIENT_SECRET=sftpgo-secret
```

## 🎫 Token Generation

```bash
# Service tokens (for EDI endpoints)
python scripts/get_auth_token.py --service nifi-service
python scripts/get_auth_token.py --service backend

# User tokens (for schema/user endpoints)
python scripts/get_auth_token.py --user admin.a@edilens.com --password password --tenant tenant-a
```

## 🛠️ Setup Commands

```bash
# 1. Setup Keycloak realm and clients
python backend/scripts/setup_keycloak_realm.py

# 2. Test configuration
./scripts/test_auth_config.sh

# 3. Source environment (for manual testing)
source .env.dev
```

## 🚀 API Usage Examples

### EDI Endpoints (Service Token)

```bash
TOKEN=$(python scripts/get_auth_token.py --service nifi-service)

# TA1 Generation
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"edi_content":"ISA*...","tenant_id":"tenant-a","acknowledgment_code":"A","workflow_id":"test"}' \
     http://localhost:3001/api/v1/edi/generate-ta1

# EDI Validation
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"edi_content":"ISA*...","tenant_id":"tenant-a","workflow_id":"test","validation_schema":"837"}' \
     http://localhost:3001/api/v1/edi/validate-realtime
```

### Schema Endpoints (User Token)

```bash
USER_TOKEN=$(python scripts/get_auth_token.py --user admin.a@edilens.com --password password --tenant tenant-a)

# List schemas
curl -H "Authorization: Bearer $USER_TOKEN" \
     -H "X-Tenant-Id: tenant-a" \
     http://localhost:3001/api/v1/schemas

# Get schema
curl -H "Authorization: Bearer $USER_TOKEN" \
     -H "X-Tenant-Id: tenant-a" \
     http://localhost:3001/api/v1/schemas/837
```

## 🏗️ Endpoint Authentication Matrix

| Endpoint Category | Authentication Method | Token Type | Example |
|-------------------|----------------------|------------|---------|
| `/api/v1/edi/*` | `require_service_auth()` | Service Token | NiFi workflows |
| `/api/v1/schemas/*` | `require_permission()` | User Token + Tenant | Schema management |
| `/api/v1/users/*` | `get_current_user()` | User Token | Profile management |

## 🔍 Debugging

```bash
# Check environment
env | grep KEYCLOAK

# Verbose token generation
python scripts/get_auth_token.py --service nifi-service --verbose

# Decode JWT payload (replace TOKEN_HERE)
echo "TOKEN_HERE" | cut -d. -f2 | base64 -d | jq

# Test API health
curl http://localhost:3001/api/v1/health
```

## ❌ Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Wrong client credentials | Check `KEYCLOAK_*_CLIENT_SECRET` |
| `Invalid service credentials` | Wrong token type | Use service token for `/edi/*` endpoints |
| `Access denied to tenant` | User lacks tenant access | Use user token with tenant membership |
| `Could not validate credentials` | Expired/invalid token | Generate new token |

## 📖 Full Documentation

- [Authentication Configuration Guide](authentication_configuration_guide.md) - Complete setup guide
- [Keycloak Setup Guide](keycloak_setup_guide.md) - Keycloak configuration details

---

> **💡 Tip**: Use `./scripts/test_auth_config.sh` to validate your entire authentication setup automatically.