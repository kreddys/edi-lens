# Getting Started with SFTP File Processing

This guide will help you set up and test the SFTP file processing system in your development environment.

## Prerequisites

- Docker and Docker Compose installed
- Git repository cloned locally
- Basic understanding of EDI file formats
- Familiarity with SFTP clients

## Quick Start

### 1. Start the Development Environment

```bash
# Start all services
./run.sh dev:start

# Verify services are running
docker ps
```

This will start:
- **SFTPGo Server** on port 2022 (SFTP) and 8080 (Web Admin)
- **MinIO** for S3-compatible object storage
- **PostgreSQL** database with EDI Lens schema
- **Backend API** with validation services
- **Keycloak** for authentication

### 2. Generate Authentication Token

```bash
# Generate a test JWT token
python3 scripts/create_test_jwt.py
```

This creates a JWT token with access to `tenant-a` and `tenant-b` with the following permissions:
- `sftp:read` - Read SFTP partner information
- `sftp:process` - Process SFTP files
- `admin` - Administrative operations

### 3. List Available Partners

```bash
# Set your JWT token
export TEST_JWT="your_jwt_token_here"

# List partners for tenant-a
./run.sh dev:sftp:process --auth-token "$TEST_JWT" --tenant tenant-a --list-partners
```

Expected output:
```
🛡️  EDI Lens Secure SFTP File Processor
==================================================
🔐 Authenticated as: test-admin
🏢 Tenant: tenant-a
🛡️  Permissions: ['sftp:read', 'admin', 'sftp:process']

✅ Secure SFTP processor initialized

📋 SFTP Partners for Tenant 'tenant-a' (0):
----------------------------------------------------------------------

✅ Operation completed successfully
```

### 4. Create a Trading Partner with SFTP

First, create a trading partner with SFTP configuration:

```bash
# Example curl command to create partner via API
curl -X POST "http://localhost:3001/api/trading-partners" \
  -H "Authorization: Bearer $TEST_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Healthcare Partner",
    "description": "Test partner for SFTP processing",
    "sftp_enabled": true,
    "sftp_username": "test_partner_sftp",
    "sftp_password": "secure_password_123",
    "profiles": [
      {
        "name": "837P Professional Claims",
        "implementation_guide": "X222A1",
        "validation_schema_name": "837.5010.X222.A1",
        "priority": 1,
        "criteria": [
          {
            "field_source": "GS",
            "field_identifier": "GS08",
            "operator": "equals",
            "value": "005010X222A1"
          }
        ]
      }
    ]
  }'
```

### 5. Connect via SFTP Client

Once you have a partner configured, you can connect using any SFTP client:

```bash
# Connect using command-line SFTP
sftp -P 2022 test_partner_sftp@localhost

# Or using GUI clients like FileZilla:
# Host: localhost
# Port: 2022
# Username: test_partner_sftp
# Password: secure_password_123
```

### 6. Upload a Test EDI File

Create a test EDI file and upload it to the inbound directory:

```bash
# Create a test 837P file
cat > test_837p.edi << 'EOF'
ISA*00*          *00*          *ZZ*SUBMITTER_TEST *ZZ*RECEIVER_TEST  *230803*1430*U*00501*000000001*0*P*>~
GS*HC*SUBMITTER_TEST*RECEIVER_TEST*20230803*1430*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*123456789*20230803*1430*CH~
NM1*41*2*TEST SUBMITTER*****46*12345~
PER*IC*CONTACT NAME*TE*5551234567~
NM1*40*2*TEST RECEIVER*****46*67890~
HL*1**20*1~
NM1*85*2*TEST BILLING PROVIDER*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*NY*12345~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*******CI~
NM1*IL*1*DOE*JOHN****MI*123456789~
N3*456 ELM ST~
N4*SOMEWHERE*CA*67890~
DMG*D8*19800101*M~
NM1*PR*2*TEST INSURANCE*****PI*ABC123~
CLM*CLM123*100***11:B:1*Y*A*Y*I~
DTP*431*D8*20230801~
HI*BK:Z1234~
LX*1~
SV1*HC:99213*100*UN*1***1~
DTP*472*D8*20230801~
SE*24*0001~
GE*1*1~
IEA*1*000000001~
EOF

# Upload via SFTP
echo "put test_837p.edi in/" | sftp -P 2022 test_partner_sftp@localhost
```

### 7. Process the File

```bash
# Process files for the specific partner
./run.sh dev:sftp:process --auth-token "$TEST_JWT" --tenant tenant-a --partner "Test Healthcare Partner" --process-files
```

Expected output:
```
🔄 Processing files for partner: Test Healthcare Partner
============================================================

📊 Processing Results:
📂 Partner: Test Healthcare Partner
✅ Files processed: 1
❌ Files failed: 0

📋 File Details:
  ✅ test_837p.edi - success
```

### 8. Check Response Files

Connect back to the SFTP server and check the outbound directory for response files:

```bash
# List files in outbound directory
echo "ls out/" | sftp -P 2022 test_partner_sftp@localhost
```

You should see a TA1 acknowledgment file generated for your processed EDI file.

## Verification Steps

### Check Processing Logs

```bash
# View backend logs
./run.sh dev:logs backend
```

Look for log entries showing:
- SFTP operation logging
- File processing events
- Audit trail entries

### Verify Database Records

You can check that database records were created:

```bash
# Connect to database
docker exec -it db-app psql -U postgres -d edi_lens

# Check validation transactions
SELECT id, file_name, status, source_type FROM validation_transactions ORDER BY created_at DESC LIMIT 5;

# Check file processing logs
SELECT id, file_key, status, tenant_id FROM file_processing_logs ORDER BY created_at DESC LIMIT 5;
```

### Test Security Isolation

Try accessing another tenant's data (this should fail):

```bash
# This should be denied
./run.sh dev:sftp:process --auth-token "$TEST_JWT" --tenant tenant-c --list-partners
```

Expected output:
```
❌ Authentication failed: User does not have access to tenant 'tenant-c'
```

## Web Administration

### SFTPGo Admin Interface

Access the SFTPGo administration interface:

- **URL**: http://localhost:8080/web/admin/
- **Username**: admin
- **Password**: admin123

From here you can:
- View user accounts
- Monitor file transfers
- Configure virtual folders
- View system status

### MinIO Console

Access the MinIO console for object storage management:

- **URL**: http://localhost:9001
- **Username**: admin
- **Password**: password

## Development Commands

### Run Tests

```bash
# Run all test suites
./run.sh dev:test unit
./run.sh dev:test integration
./run.sh dev:test e2e
```

### View Logs

```bash
# View all service logs
./run.sh dev:logs

# View specific service logs
./run.sh dev:logs backend
./run.sh dev:logs sftpgo
```

### Clean Environment

```bash
# Stop all services
./run.sh dev:stop

# Clean up all data (WARNING: This deletes everything)
./run.sh dev:clean
```

## Troubleshooting

### Common Issues

1. **Services won't start**
   ```bash
   # Check Docker is running
   docker info
   
   # Check ports aren't in use
   lsof -i :2022  # SFTP port
   lsof -i :8080  # Admin port
   ```

2. **SFTP connection failed**
   - Verify the partner was created with SFTP enabled
   - Check the username and password are correct
   - Ensure you're connecting to port 2022

3. **Authentication errors**
   - Verify your JWT token is valid and not expired
   - Check the user has access to the specified tenant
   - Ensure required permissions are present

4. **File processing fails**
   - Check the EDI file format is valid
   - Verify the partner profile criteria match the file
   - Review backend logs for detailed error messages

## Next Steps

- [Authentication & Security](03-authentication-security.md) - Learn about the security model
- [File Processing Workflow](04-file-processing-workflow.md) - Understand the processing flow
- [API Reference](05-api-reference.md) - Explore the REST APIs
- [CLI Tools](06-cli-tools.md) - Master the command-line tools