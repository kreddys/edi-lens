# CLI Tools for SFTP Operations

The EDI Lens SFTP system provides secure command-line tools for managing and processing SFTP files. All CLI tools require JWT authentication and enforce tenant isolation.

## Overview

The primary CLI tool is the **Secure SFTP Processor** (`secure_sftp_processor.py`), which provides authenticated access to SFTP operations through the `run.sh` orchestration script.

## Authentication Requirements

All CLI operations require:
- **Valid JWT Token**: Authentication token with appropriate permissions
- **Tenant Specification**: Explicit tenant ID for operations
- **Required Permissions**: Minimum permissions based on operation type

### Permission Requirements

| Operation | Required Permissions |
|-----------|---------------------|
| List Partners | `sftp:read` |
| Discover Files | `sftp:read` |
| Process Files | `sftp:read`, `sftp:process` |
| Administrative Tasks | `admin` |

## Secure SFTP Processor

### Basic Usage

```bash
./run.sh dev:sftp:process [OPTIONS] [OPERATION]
```

#### Required Arguments
- `--auth-token TOKEN` - JWT authentication token
- `--tenant TENANT_ID` - Target tenant identifier
- One operation flag (see operations below)

#### Available Operations
- `--list-partners` - List all SFTP partners for tenant
- `--discover-files` - Discover files for specific partner
- `--process-files` - Process files for specific partner
- `--process-all` - Process all files for all tenant partners
- `--audit-log` - Show audit log of operations

#### Partner-Specific Operations
- `--partner PARTNER_NAME` - Required for discover-files and process-files

### Operation Examples

#### 1. List Partners

List all SFTP-enabled partners for a tenant:

```bash
./run.sh dev:sftp:process \
  --auth-token "$JWT_TOKEN" \
  --tenant tenant-a \
  --list-partners
```

**Sample Output:**
```
🛡️  EDI Lens Secure SFTP File Processor
==================================================
🔐 Authenticated as: test-admin
🏢 Tenant: tenant-a
🛡️  Permissions: ['sftp:read', 'admin', 'sftp:process']

✅ Secure SFTP processor initialized

📋 SFTP Partners for Tenant 'tenant-a' (2):
----------------------------------------------------------------------
📂 United Health Group
   SFTP Username: sftp_a1b2c3d4_e5f6g7_123456_xyz789
   Partner ID: 1

📂 Change Healthcare
   SFTP Username: sftp_a1b2c3d4_h8i9j0_789012_abc456
   Partner ID: 2

✅ Operation completed successfully
```

#### 2. Discover Files

Find files in a partner's inbound directory:

```bash
./run.sh dev:sftp:process \
  --auth-token "$JWT_TOKEN" \
  --tenant tenant-a \
  --partner "United Health Group" \
  --discover-files
```

**Sample Output:**
```
📁 Files for Partner 'United Health Group':
--------------------------------------------------
  📄 claim_batch_001.edi
     Full path: sftp/tenant-a/sftp_a1b2c3d4_e5f6g7_123456_xyz789/in/claim_batch_001.edi
  📄 claim_batch_002.edi
     Full path: sftp/tenant-a/sftp_a1b2c3d4_e5f6g7_123456_xyz789/in/claim_batch_002.edi

Total files found: 2
```

#### 3. Process Partner Files

Process all files for a specific partner:

```bash
./run.sh dev:sftp:process \
  --auth-token "$JWT_TOKEN" \
  --tenant tenant-a \
  --partner "United Health Group" \
  --process-files
```

**Sample Output:**
```
🔄 Processing files for partner: United Health Group
============================================================

📊 Processing Results:
📂 Partner: United Health Group
✅ Files processed: 2
❌ Files failed: 0

📋 File Details:
  ✅ claim_batch_001.edi - success
  ✅ claim_batch_002.edi - success

✅ Operation completed successfully
```

#### 4. Process All Files

Process files for all partners in the tenant:

```bash
./run.sh dev:sftp:process \
  --auth-token "$JWT_TOKEN" \
  --tenant tenant-a \
  --process-all
```

**Sample Output:**
```
🔄 Processing all files for tenant: tenant-a
======================================================================

📊 Overall Results:
🏢 Tenant: tenant-a
📂 Partners processed: 2
✅ Total files processed: 3
❌ Total files failed: 0

📋 Partner Details:
  📂 United Health Group:
     ✅ Processed: 2
     ❌ Failed: 0
  📂 Change Healthcare:
     ✅ Processed: 1
     ❌ Failed: 0

✅ Operation completed successfully
```

#### 5. View Audit Log

Show audit log of operations performed in the session:

```bash
./run.sh dev:sftp:process \
  --auth-token "$JWT_TOKEN" \
  --tenant tenant-a \
  --audit-log
```

**Sample Output:**
```
📊 Audit Log (5 operations):
------------------------------------------------------------
[21:39:24] session_start
  Status: STARTED
  User: test-admin
  Tenant: tenant-a

[21:39:25] list_partners
  Status: SUCCESS
  User: test-admin
  Tenant: tenant-a
  Details: {"partner_count": 2}

[21:39:30] process_file_complete
  Status: SUCCESS
  User: test-admin
  Tenant: tenant-a
  Partner ID: 1
  File: sftp/tenant-a/partner1/in/claim_batch_001.edi
  Details: {"validation_status": "accepted", "findings_count": 0}

✅ Operation completed successfully
```

## JWT Token Management

### Generate Test Token

For development and testing, you can generate test JWT tokens:

```bash
# Generate a test token with default permissions
python3 scripts/create_test_jwt.py
```

This generates a token with:
- **Tenants**: `tenant-a`, `tenant-b`
- **Permissions**: `sftp:read`, `sftp:process`, `admin`
- **Validity**: 2 hours

### Token Environment Variables

Set environment variables for easier command usage:

```bash
# Set JWT token
export EDI_LENS_JWT="your_jwt_token_here"

# Set default tenant
export EDI_LENS_TENANT="tenant-a"

# Use in commands
./run.sh dev:sftp:process \
  --auth-token "$EDI_LENS_JWT" \
  --tenant "$EDI_LENS_TENANT" \
  --list-partners
```

### Production Token Management

In production environments:

```bash
# Get token from Keycloak
TOKEN=$(curl -s -X POST "https://your-keycloak/auth/realms/edi-lens/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=your-client-id" \
  -d "client_secret=your-client-secret" \
  | jq -r '.access_token')

# Use token in operations
./run.sh dev:sftp:process --auth-token "$TOKEN" --tenant your-tenant --list-partners
```

## Legacy CLI Tools (Deprecated)

### Legacy SFTP Processor

⚠️ **DEPRECATED**: The legacy SFTP processor is insecure and should not be used in production.

```bash
# Legacy processor (requires user confirmation)
./run.sh dev:sftp:legacy --tenant TENANT --partner PARTNER
```

When executed, you'll receive warnings:
```
⚠️  USING LEGACY SFTP PROCESSOR - NO AUTHENTICATION!
⚠️  THIS IS FOR DEVELOPMENT ONLY - NOT SECURE!
Continue with insecure legacy processor? [y/N]
```

**Security Issues with Legacy Processor:**
- No authentication required
- No tenant validation
- No audit logging
- Cross-tenant access possible
- No permission checking

## Error Handling

### Authentication Errors

```bash
# Invalid token
./run.sh dev:sftp:process --auth-token "invalid_token" --tenant tenant-a --list-partners

# Output:
❌ Authentication failed: Invalid JWT token: Not enough segments
```

### Authorization Errors

```bash
# Cross-tenant access attempt
./run.sh dev:sftp:process --auth-token "$TENANT_A_JWT" --tenant tenant-c --list-partners

# Output:
❌ Authentication failed: User does not have access to tenant 'tenant-c'
```

### Permission Errors

```bash
# Insufficient permissions (user only has sftp:read, trying to process)
./run.sh dev:sftp:process --auth-token "$READ_ONLY_JWT" --tenant tenant-a --process-all

# Output:
❌ Security error: Permission denied: 'sftp:process' required
```

### Operational Errors

```bash
# Partner not found
./run.sh dev:sftp:process --auth-token "$JWT" --tenant tenant-a --partner "Nonexistent Partner" --process-files

# Output:
❌ Security Error: Partner 'Nonexistent Partner' not found in your tenant
```

## Advanced Usage

### Batch Processing Script

Create a script for batch processing multiple tenants:

```bash
#!/bin/bash
# batch_process.sh

TENANTS=("tenant-a" "tenant-b" "tenant-c")
JWT_TOKEN="$1"

if [ -z "$JWT_TOKEN" ]; then
    echo "Usage: $0 <jwt_token>"
    exit 1
fi

for tenant in "${TENANTS[@]}"; do
    echo "Processing tenant: $tenant"
    ./run.sh dev:sftp:process \
        --auth-token "$JWT_TOKEN" \
        --tenant "$tenant" \
        --process-all
    echo "---"
done
```

### Monitoring Script

Create a monitoring script to check partner status:

```bash
#!/bin/bash
# monitor_partners.sh

JWT_TOKEN="$1"
TENANT="$2"

if [ -z "$JWT_TOKEN" ] || [ -z "$TENANT" ]; then
    echo "Usage: $0 <jwt_token> <tenant>"
    exit 1
fi

echo "=== Partner Status Report ==="
echo "Tenant: $TENANT"
echo "Timestamp: $(date)"
echo

# List partners
./run.sh dev:sftp:process \
    --auth-token "$JWT_TOKEN" \
    --tenant "$TENANT" \
    --list-partners

echo
echo "=== File Discovery ==="

# For each partner, discover files (would need to be customized based on actual partners)
# This is a template - adjust partner names as needed
PARTNERS=("United Health Group" "Change Healthcare")

for partner in "${PARTNERS[@]}"; do
    echo "--- $partner ---"
    ./run.sh dev:sftp:process \
        --auth-token "$JWT_TOKEN" \
        --tenant "$TENANT" \
        --partner "$partner" \
        --discover-files 2>/dev/null || echo "Partner not found or no access"
    echo
done
```

## Integration with CI/CD

### GitHub Actions Example

```yaml
# .github/workflows/sftp-processing.yml
name: SFTP File Processing

on:
  schedule:
    - cron: '0 */4 * * *'  # Every 4 hours
  workflow_dispatch:

jobs:
  process-files:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Get Authentication Token
      id: auth
      run: |
        TOKEN=$(curl -s -X POST "${{ secrets.KEYCLOAK_URL }}/auth/realms/edi-lens/protocol/openid-connect/token" \
          -H "Content-Type: application/x-www-form-urlencoded" \
          -d "grant_type=client_credentials" \
          -d "client_id=${{ secrets.KEYCLOAK_CLIENT_ID }}" \
          -d "client_secret=${{ secrets.KEYCLOAK_CLIENT_SECRET }}" \
          | jq -r '.access_token')
        echo "::add-mask::$TOKEN"
        echo "token=$TOKEN" >> $GITHUB_OUTPUT
    
    - name: Process SFTP Files
      run: |
        ./run.sh dev:sftp:process \
          --auth-token "${{ steps.auth.outputs.token }}" \
          --tenant "${{ vars.TENANT_ID }}" \
          --process-all
```

## Troubleshooting

### Common Issues

1. **Command not found**
   ```bash
   # Ensure you're in the project root
   cd /path/to/edi-lens
   ./run.sh dev:sftp:process --help
   ```

2. **Services not running**
   ```bash
   # Start the development environment
   ./run.sh dev:start
   ```

3. **Token expired**
   ```bash
   # Generate a new token
   python3 /tmp/create_test_jwt.py
   ```

4. **Permission denied**
   ```bash
   # Check your token permissions
   # Ensure token includes required scopes: sftp:read, sftp:process
   ```

### Debug Mode

Enable verbose logging by setting environment variables:

```bash
export EDI_LENS_LOG_LEVEL=DEBUG
./run.sh dev:sftp:process --auth-token "$JWT" --tenant tenant-a --list-partners
```

## Next Steps

- [API Reference](05-api-reference.md) - REST API documentation
- [Administration](07-administration.md) - System administration
- [Troubleshooting](08-troubleshooting.md) - Common issues and solutions