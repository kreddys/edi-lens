# Authentication Configuration Guide

This guide covers the standardized authentication configuration for EDI Lens, including environment-driven setup, token generation, and service account management.

## 📋 Overview

EDI Lens uses a **standardized, environment-driven authentication system** with Keycloak as the identity provider. All client configurations, secrets, and URLs are managed through environment variables, ensuring consistency across development, staging, and production environments.

## 🏗️ Architecture

### Authentication Methods by Endpoint Type

EDI Lens implements **different authentication methods for different types of endpoints**:

#### 1. EDI Processing Endpoints (`/api/v1/edi/*`)
- **Authentication**: Service account tokens
- **Use Case**: NiFi processors and automated workflows
- **Token Type**: Client credentials grant
- **Examples**: `/validate-realtime`, `/generate-ta1`, `/parse`

#### 2. Schema Management Endpoints (`/api/v1/schemas/*`)
- **Authentication**: User tokens with tenant permissions
- **Use Case**: User-facing tenant-specific operations
- **Token Type**: Password grant with tenant group membership
- **Examples**: `/schemas`, `/schemas/{name}`

#### 3. User Profile Endpoints (`/api/v1/users/*`)
- **Authentication**: User tokens
- **Use Case**: User profile management
- **Token Type**: Password grant
- **Examples**: `/users/me`

## 🔧 Environment Configuration

### Required Environment Variables

All authentication configuration is driven by environment variables defined in `.env.dev`:

```bash
# --- Keycloak Base Configuration ---
KEYCLOAK_URL=http://keycloak:8080              # Internal service URL
KEYCLOAK_BROWSER_URL=http://localhost:8081     # Public browser URL
KEYCLOAK_REALM=edi-lens                        # Keycloak realm name

# --- Main Application Clients ---
KEYCLOAK_BACKEND_CLIENT_ID=edi-lens-backend
KEYCLOAK_BACKEND_CLIENT_SECRET=this-is-a-very-secret-key-change-it
KEYCLOAK_UI_CLIENT_ID=edi-lens-ui

# --- Service Account Clients ---
KEYCLOAK_NIFI_CLIENT_ID=nifi-service
KEYCLOAK_NIFI_CLIENT_SECRET=nifi-service-secret
KEYCLOAK_SFTPGO_CLIENT_ID=sftpgo
KEYCLOAK_SFTPGO_CLIENT_SECRET=a_very_secure_sftpgo_secret_change_it
```

### Client Types and Usage

| Client ID | Type | Purpose | Authentication Flow |
|-----------|------|---------|-------------------|
| `edi-lens-backend` | Confidential | Backend API service authentication | Client credentials |
| `edi-lens-ui` | Public | Frontend user authentication | Authorization code |
| `nifi-service` | Service Account | NiFi workflow automation | Client credentials |
| `sftpgo` | Confidential | SFTPGo admin SSO | Authorization code |

## 🎫 Token Generation

### Using the Token Generation Script

The `scripts/get_auth_token.py` script provides a unified way to generate authentication tokens:

#### Service Account Tokens

```bash
# Generate NiFi service token
python scripts/get_auth_token.py --service nifi-service

# Generate backend service token  
python scripts/get_auth_token.py --service backend

# With verbose output
python scripts/get_auth_token.py --service nifi-service --verbose
```

#### User Tokens

```bash
# Generate user token
python scripts/get_auth_token.py --user admin.a@edilens.com --password password --tenant tenant-a
```

#### Environment-Driven Configuration

The script automatically reads configuration from environment variables:

- `KEYCLOAK_BROWSER_URL` - Keycloak public URL
- `KEYCLOAK_REALM` - Keycloak realm name
- `KEYCLOAK_*_CLIENT_ID` - Client IDs for different services
- `KEYCLOAK_*_CLIENT_SECRET` - Client secrets for authentication

### Token Usage Examples

#### EDI Endpoints (Service Tokens)

```bash
# Generate token
TOKEN=$(python scripts/get_auth_token.py --service nifi-service)

# Use with EDI endpoint
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"edi_content":"...","tenant_id":"tenant-a","workflow_id":"test"}' \
     http://localhost:3001/api/v1/edi/generate-ta1
```

#### Schema Endpoints (User Tokens)

```bash
# Generate user token
USER_TOKEN=$(python scripts/get_auth_token.py --user admin.a@edilens.com --password password --tenant tenant-a)

# Use with schema endpoint
curl -H "Authorization: Bearer $USER_TOKEN" \
     -H "X-Tenant-Id: tenant-a" \
     http://localhost:3001/api/v1/schemas
```

## 🔐 Security Model

### Service Account Permissions

Service accounts have specific permissions for their use cases:

**NiFi Service Account (`nifi-service`)**:
- `edi:process` - Process EDI content
- `edi:validate` - Validate EDI documents
- `edi:generate-acknowledgments` - Generate TA1/997 acknowledgments
- `validation:run` - Run validation services
- `schemas:read` - Read EDI schemas

**Backend Service Account (`edi-lens-backend`)**:
- Internal service communication
- API-to-API authentication

### User Permissions

User permissions are based on **realm roles** and **tenant group membership**:

**Realm Roles**:
- `admin` - Administrative privileges
- `validation:run` - Can run EDI validation
- `schemas:read/create/update` - Schema management
- `workflow:read/write/admin` - Workflow management

**Tenant Groups**:
- `tenant-a`, `tenant-b` - Tenant membership for data isolation

### Composite Roles

Pre-configured composite roles combine multiple permissions:

- **`tenant-admin`** - Full tenant control
- **`tenant-viewer`** - Read-only tenant access  
- **`superuser`** - Global administrator

## 🛠️ Setup and Configuration

### Automatic Setup

The authentication system is configured automatically using:

```bash
# Run Keycloak realm setup (reads from environment)
python backend/scripts/setup_keycloak_realm.py
```

This script:
- Creates the `edi-lens` realm
- Configures all clients using environment variables
- Sets up roles and permissions
- Creates default users for testing
- Configures service account roles

### Manual Configuration

If you need to modify the configuration:

1. **Update Environment Variables**:
   ```bash
   # Edit .env.dev with new client IDs/secrets
   vim .env.dev
   ```

2. **Re-run Setup Script**:
   ```bash
   python backend/scripts/setup_keycloak_realm.py
   ```

3. **Test Configuration**:
   ```bash
   ./scripts/test_auth_config.sh
   ```

## 🧪 Testing and Validation

### Automated Testing

Use the provided test script to validate your authentication configuration:

```bash
./scripts/test_auth_config.sh
```

This script tests:
- Environment variable loading
- Token generation for all service types
- API endpoint authentication
- End-to-end authentication flow

### Manual Testing

#### Test Service Token Generation

```bash
# Source environment
source .env.dev

# Test NiFi service token
python scripts/get_auth_token.py --service nifi-service --verbose

# Test backend service token
python scripts/get_auth_token.py --service backend --verbose
```

#### Test API Authentication

```bash
# Generate token and test API
TOKEN=$(python scripts/get_auth_token.py --service nifi-service)
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:3001/api/v1/health
```

## 🔄 Migration from Previous Configuration

### Changes Made in Cleanup

The authentication configuration was standardized with these changes:

1. **Removed Fake Token Generation**:
   - Eliminated mock/fake JWT tokens
   - All tokens now come from Keycloak

2. **Environment-Driven Configuration**:
   - Removed hardcoded client IDs ("nifi-service", "sftpgo")
   - All configuration via environment variables

3. **Simplified Token Script**:
   - Removed `--real` flag (always real tokens)
   - Removed hardcoded client mappings
   - Auto-detection of configuration from environment

4. **Updated Keycloak Setup**:
   - Dynamic client creation based on environment
   - Consistent variable naming

### Before and After

**Before (Hardcoded)**:
```python
# Hardcoded in script
client_id_mapping = {
    "nifi-service": "nifi-service",
    "edi-lens-backend": "edi-lens-backend"
}
client_secret = "nifi-service-secret"  # Hardcoded
```

**After (Environment-Driven)**:
```python
# Read from environment
client_id = os.getenv("KEYCLOAK_NIFI_CLIENT_ID", "nifi-service")
client_secret = os.getenv("KEYCLOAK_NIFI_CLIENT_SECRET", "nifi-service-secret")
```

## 🚨 Troubleshooting

### Common Issues

#### 1. Token Generation Fails

**Error**: `401 Unauthorized`
**Cause**: Incorrect client credentials
**Solution**: Verify environment variables are set correctly

```bash
echo $KEYCLOAK_NIFI_CLIENT_SECRET
```

#### 2. API Returns "Invalid service credentials"

**Cause**: Using wrong token type for endpoint
**Solution**: Use service tokens for EDI endpoints, user tokens for schema endpoints

#### 3. "Access denied to tenant" Error

**Cause**: Service token used with user endpoint, or user lacks tenant membership
**Solution**: 
- Use user tokens for tenant-specific endpoints
- Verify user is member of tenant group

#### 4. Environment Variables Not Loading

**Cause**: `.env.dev` not sourced
**Solution**:
```bash
source .env.dev
# or
set -a && source .env.dev && set +a
```

### Debug Commands

```bash
# Check environment variables
env | grep KEYCLOAK

# Test token generation with verbose output
python scripts/get_auth_token.py --service nifi-service --verbose

# Decode JWT token (for debugging)
echo "TOKEN_HERE" | cut -d. -f2 | base64 -d | jq
```

## 📚 Related Documentation

- [Keycloak Setup Guide](keycloak_setup_guide.md) - Detailed Keycloak configuration
- [API Authentication](../architecture.md#authentication) - API authentication architecture
- [Multi-Tenancy Guide](../architecture.md#multi-tenancy) - Tenant isolation and security

## 📝 Best Practices

1. **Always use environment variables** for client configuration
2. **Use appropriate token types** for different endpoint categories
3. **Test authentication** after any configuration changes
4. **Rotate secrets regularly** in production environments
5. **Monitor token expiration** and implement refresh logic where needed
6. **Use verbose mode** during development for debugging

---

> **Note**: This configuration supports the current NiFi-workflow architecture where EDI processing is handled by service accounts, while user-facing operations require tenant-specific user authentication.