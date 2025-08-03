# Troubleshooting SFTP File Processing

This guide covers common issues, diagnostic procedures, and solutions for the EDI Lens SFTP file processing system.

## Quick Diagnostic Commands

### System Health Check

```bash
# Check all services are running
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Check service logs
./run.sh dev:logs

# Test authentication
./run.sh dev:sftp:process --auth-token "$TEST_JWT" --tenant tenant-a --list-partners
```

### Service Status

```bash
# Backend API health
curl -s http://localhost:3001/api/health

# SFTPGo API health  
curl -s http://localhost:8080/api/v2/healthcheck

# MinIO health
curl -s http://localhost:9000/minio/health/live
```

## Common Issues and Solutions

### 1. Authentication Problems

#### Issue: "Invalid JWT token" Error

**Symptoms:**
```
❌ Authentication failed: Invalid JWT token: Not enough segments
```

**Causes:**
- Malformed JWT token
- Token not properly base64 encoded
- Missing token segments

**Solutions:**
```bash
# Generate a new test token
python3 /tmp/create_test_jwt.py

# Verify token format (should have 3 parts separated by dots)
echo "$JWT_TOKEN" | tr '.' '\n' | wc -l  # Should output 3

# Test with new token
export TEST_JWT="your_new_token_here"
./run.sh dev:sftp:process --auth-token "$TEST_JWT" --tenant tenant-a --list-partners
```

#### Issue: "User does not have access to tenant" Error

**Symptoms:**
```
❌ Authentication failed: User does not have access to tenant 'tenant-c'
```

**Causes:**
- User not in requested tenant's group
- Tenant ID mismatch
- Token doesn't include tenant in groups claim

**Solutions:**
```bash
# Check token contents (decode JWT)
echo "$JWT_TOKEN" | cut -d'.' -f2 | base64 -d | jq .

# Verify groups claim includes target tenant
echo "$JWT_TOKEN" | cut -d'.' -f2 | base64 -d | jq '.groups'

# Use correct tenant from token
./run.sh dev:sftp:process --auth-token "$TEST_JWT" --tenant tenant-a --list-partners
```

#### Issue: "Permission denied" Error

**Symptoms:**
```
❌ Security error: Permission denied: 'sftp:process' required
```

**Causes:**
- Insufficient permissions in JWT token
- Missing required roles

**Solutions:**
```bash
# Check token permissions
echo "$JWT_TOKEN" | cut -d'.' -f2 | base64 -d | jq '.realm_access.roles'

# Generate token with required permissions
python3 /tmp/create_test_jwt.py  # Includes sftp:read, sftp:process, admin

# Use operation that matches your permissions
./run.sh dev:sftp:process --auth-token "$READ_ONLY_JWT" --tenant tenant-a --list-partners  # Only requires sftp:read
```

### 2. Service Connection Issues

#### Issue: Services Won't Start

**Symptoms:**
```
Error response from daemon: port is already allocated
```

**Diagnosis:**
```bash
# Check what's using the ports
lsof -i :2022  # SFTP port
lsof -i :8080  # SFTPGo admin port
lsof -i :9000  # MinIO port
lsof -i :5432  # PostgreSQL port

# Check Docker status
docker info
docker-compose version
```

**Solutions:**
```bash
# Stop conflicting services
sudo lsof -ti:2022 | xargs kill -9  # Kill processes using SFTP port

# Clean up Docker
./run.sh dev:stop
docker system prune -f

# Restart services
./run.sh dev:start
```

#### Issue: "Connection refused" to Services

**Symptoms:**
```
dial tcp 127.0.0.1:8080: connect: connection refused
```

**Diagnosis:**
```bash
# Check if services are actually running
docker ps | grep -E "(sftpgo|minio|backend)"

# Check service logs for errors
./run.sh dev:logs sftpgo
./run.sh dev:logs backend
./run.sh dev:logs minio
```

**Solutions:**
```bash
# Wait for services to fully start
sleep 30

# Restart specific service
docker-compose -f docker/docker-compose.yml restart sftpgo

# Check service health endpoints
curl -f http://localhost:8080/api/v2/healthcheck || echo "SFTPGo not ready"
curl -f http://localhost:9000/minio/health/live || echo "MinIO not ready"
```

### 3. SFTP Connection Issues

#### Issue: Cannot Connect to SFTP Server

**Symptoms:**
```bash
$ sftp -P 2022 testuser@localhost
ssh: connect to host localhost port 2022: Connection refused
```

**Diagnosis:**
```bash
# Check SFTPGo is running and bound to port 2022
docker ps | grep sftpgo
netstat -ln | grep 2022

# Check SFTPGo logs
docker logs sftpgo
```

**Solutions:**
```bash
# Restart SFTPGo service
docker restart sftpgo

# Check SFTPGo configuration
curl http://localhost:8080/api/v2/users

# Verify port mapping in docker-compose.yml
grep -A5 -B5 "2022:2022" docker/docker-compose.yml
```

#### Issue: SFTP Authentication Failed

**Symptoms:**
```bash
$ sftp -P 2022 testuser@localhost
testuser@localhost's password: 
Permission denied, please try again.
```

**Diagnosis:**
```bash
# Check if user exists in SFTPGo
curl -u admin:admin123 http://localhost:8080/api/v2/users

# Check SFTPGo logs for authentication attempts
docker logs sftpgo | grep -i auth
```

**Solutions:**
```bash
# Access SFTPGo admin interface
open http://localhost:8080/web/admin/
# Login: admin / admin123
# Check user configuration

# Create test user via API
curl -X POST http://localhost:8080/api/v2/users \
  -u admin:admin123 \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "testpass123",
    "home_dir": "/srv/sftpgo/testuser",
    "permissions": {"/": ["*"]}
  }'
```

### 4. File Processing Issues

#### Issue: Files Not Being Processed

**Symptoms:**
- Files uploaded to SFTP but no processing occurs
- No TA1 acknowledgments generated

**Diagnosis:**
```bash
# Check if files exist in MinIO
curl -s http://localhost:9000/edi-lens-schemas/sftp/ | grep -o "sftp/[^<]*"

# Check processing logs
./run.sh dev:logs backend | grep -i sftp

# Try manual processing
./run.sh dev:sftp:process \
  --auth-token "$TEST_JWT" \
  --tenant tenant-a \
  --partner "Partner Name" \
  --discover-files
```

**Solutions:**
```bash
# Verify partner configuration
curl -H "Authorization: Bearer $TEST_JWT" \
  http://localhost:3001/api/trading-partners

# Check database for SFTP configurations
docker exec -it db-app psql -U postgres -d edi_lens \
  -c "SELECT id, partner_id, sftp_enabled, sftp_username FROM sftp_configurations;"

# Manual file processing
./run.sh dev:sftp:process \
  --auth-token "$TEST_JWT" \
  --tenant tenant-a \
  --partner "Partner Name" \
  --process-files
```

#### Issue: File Processing Errors

**Symptoms:**
```
❌ Files failed: 1
  ❌ test_file.edi - error
      Error: File processing failed - check logs for details
```

**Diagnosis:**
```bash
# Check detailed backend logs
./run.sh dev:logs backend | tail -100

# Check validation transaction status
docker exec -it db-app psql -U postgres -d edi_lens \
  -c "SELECT file_name, status, error_message FROM validation_transactions ORDER BY created_at DESC LIMIT 5;"

# Check file processing logs
docker exec -it db-app psql -U postgres -d edi_lens \
  -c "SELECT file_key, status, error_message FROM file_processing_logs ORDER BY created_at DESC LIMIT 5;"
```

**Solutions:**
```bash
# Check EDI file format
head -5 your_edi_file.edi  # Should start with ISA segment

# Validate file manually via API
curl -X POST http://localhost:3001/api/validate \
  -H "Authorization: Bearer $TEST_JWT" \
  -H "Content-Type: application/json" \
  -d '{"edi_data": "ISA*00*...", "file_name": "test.edi"}'

# Check partner profile matching
docker exec -it db-app psql -U postgres -d edi_lens \
  -c "SELECT pp.name, pc.field_identifier, pc.operator, pc.value 
      FROM partner_profiles pp 
      JOIN profile_criteria pc ON pp.id = pc.profile_id 
      WHERE pp.partner_id = YOUR_PARTNER_ID;"
```

### 5. Database Issues

#### Issue: Database Connection Errors

**Symptoms:**
```
sqlalchemy.exc.OperationalError: (psycopg2.OperationalError) could not connect to server
```

**Diagnosis:**
```bash
# Check PostgreSQL container
docker ps | grep postgres
docker logs db-app

# Test database connection
docker exec -it db-app psql -U postgres -l
```

**Solutions:**
```bash
# Restart database
docker restart db-app

# Wait for database to be ready
timeout 60 bash -c 'until docker exec db-app pg_isready -U postgres; do sleep 1; done'

# Check database exists
docker exec -it db-app psql -U postgres -c "SELECT datname FROM pg_database WHERE datname = 'edi_lens';"
```

#### Issue: Migration Errors

**Symptoms:**
```
alembic.util.exc.CommandError: Target database is not up to date.
```

**Solutions:**
```bash
# Check current migration status
./run.sh dev:migrate:run

# View migration history
docker exec backend alembic -c alembic.ini history

# Apply pending migrations
docker exec backend alembic -c alembic.ini upgrade head
```

### 6. Storage Issues

#### Issue: MinIO Connection Errors

**Symptoms:**
```
botocore.exceptions.EndpointConnectionError: Could not connect to the endpoint URL
```

**Diagnosis:**
```bash
# Check MinIO status
docker ps | grep minio
curl -s http://localhost:9000/minio/health/live

# Check MinIO logs
docker logs minio
```

**Solutions:**
```bash
# Restart MinIO
docker restart minio

# Verify MinIO credentials in environment
grep -E "(STORAGE_|MINIO_)" .env.dev

# Test MinIO connection
docker exec backend python -c "
import boto3
client = boto3.client('s3', endpoint_url='http://minio:9000', aws_access_key_id='admin', aws_secret_access_key='password')
print(client.list_buckets())
"
```

#### Issue: S3 Bucket Errors

**Symptoms:**
```
botocore.exceptions.NoSuchBucket: The specified bucket does not exist
```

**Solutions:**
```bash
# Create bucket manually
docker exec backend python -c "
import boto3
client = boto3.client('s3', endpoint_url='http://minio:9000', aws_access_key_id='admin', aws_secret_access_key='password')
client.create_bucket(Bucket='edi-lens-schemas')
print('Bucket created')
"

# Verify bucket exists
curl -s http://localhost:9000/edi-lens-schemas/ | head -10
```

## Advanced Diagnostics

### Enable Debug Logging

```bash
# Set debug environment variables
export EDI_LENS_LOG_LEVEL=DEBUG
export SQLALCHEMY_ECHO=true

# Restart services with debug logging
./run.sh dev:stop
./run.sh dev:start
```

### Database Query Diagnostics

```bash
# Check tenant data
docker exec -it db-app psql -U postgres -d edi_lens -c "
SELECT 
    tp.id, tp.name, tp.tenant_id,
    sc.sftp_enabled, sc.sftp_username,
    COUNT(fpl.id) as processed_files
FROM trading_partners tp
LEFT JOIN sftp_configurations sc ON tp.id = sc.partner_id
LEFT JOIN file_processing_logs fpl ON tp.id = fpl.partner_id
GROUP BY tp.id, tp.name, tp.tenant_id, sc.sftp_enabled, sc.sftp_username
ORDER BY tp.tenant_id, tp.name;
"

# Check recent validation transactions
docker exec -it db-app psql -U postgres -d edi_lens -c "
SELECT 
    vt.id, vt.file_name, vt.status, vt.source_type,
    vt.created_at, vt.tenant_id
FROM validation_transactions vt
ORDER BY vt.created_at DESC
LIMIT 10;
"
```

### Network Diagnostics

```bash
# Check Docker network
docker network ls
docker network inspect edi-lens-dev_default

# Test inter-service connectivity
docker exec backend curl -s http://minio:9000/minio/health/live
docker exec backend curl -s http://sftpgo:8080/api/v2/healthcheck
```

## Performance Issues

### Slow File Processing

**Symptoms:**
- Files take a long time to process
- High CPU/memory usage

**Diagnosis:**
```bash
# Check system resources
docker stats

# Check backend performance
./run.sh dev:logs backend | grep -E "(processing|duration|memory)"
```

**Solutions:**
```bash
# Increase Docker resource limits
# Edit Docker Desktop settings or docker-compose.yml

# Process files in smaller batches
./run.sh dev:sftp:process \
  --auth-token "$TEST_JWT" \
  --tenant tenant-a \
  --partner "Single Partner" \
  --process-files  # Instead of --process-all
```

### Database Performance

**Symptoms:**
- Slow database queries
- Connection timeouts

**Solutions:**
```bash
# Check database performance
docker exec -it db-app psql -U postgres -d edi_lens -c "
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY total_time DESC 
LIMIT 10;
"

# Add database indexes if needed (consult DBA)
# Increase connection pool size in backend configuration
```

## Emergency Procedures

### Complete System Reset

⚠️ **WARNING**: This deletes all data!

```bash
# Stop all services
./run.sh dev:stop

# Remove all containers and volumes
./run.sh dev:clean

# Restart from scratch
./run.sh dev:start
```

### Backup Critical Data

```bash
# Backup database
docker exec db-app pg_dump -U postgres edi_lens > backup_$(date +%Y%m%d_%H%M%S).sql

# Backup MinIO data
docker exec minio mc mirror /data/edi-lens-schemas ./minio-backup/
```

### Recovery Procedures

```bash
# Restore database
docker exec -i db-app psql -U postgres edi_lens < backup_20231203_143022.sql

# Restore MinIO data
docker exec minio mc mirror ./minio-backup/ /data/edi-lens-schemas
```

## Getting Help

### Log Collection Script

Create a diagnostic information collection script:

```bash
#!/bin/bash
# collect_diagnostics.sh

echo "=== EDI Lens SFTP Diagnostics ==="
echo "Timestamp: $(date)"
echo "System: $(uname -a)"
echo

echo "=== Docker Status ==="
docker version
docker-compose version
echo

echo "=== Service Status ==="
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo

echo "=== Service Health ==="
curl -s http://localhost:3001/api/health | jq . || echo "Backend: FAILED"
curl -s http://localhost:8080/api/v2/healthcheck | jq . || echo "SFTPGo: FAILED"
curl -s http://localhost:9000/minio/health/live || echo "MinIO: FAILED"
echo

echo "=== Recent Logs (last 50 lines) ==="
echo "--- Backend ---"
docker logs --tail 50 backend 2>&1
echo "--- SFTPGo ---"
docker logs --tail 50 sftpgo 2>&1
echo "--- MinIO ---"
docker logs --tail 50 minio 2>&1
```

### Support Information

When reporting issues, include:

1. **Environment Information**
   - Operating system and version
   - Docker and Docker Compose versions
   - Output of diagnostic script

2. **Error Details**
   - Complete error messages
   - Steps to reproduce
   - Expected vs actual behavior

3. **System State**
   - Service logs
   - Database query results
   - Configuration files (sanitized)

### Community Resources

- **GitHub Issues**: Report bugs and feature requests
- **Documentation**: Latest docs and guides
- **Development Chat**: Real-time support for developers

## Next Steps

- [Development](09-development.md) - Development setup and testing
- [API Reference](05-api-reference.md) - REST API documentation
- [Administration](07-administration.md) - System administration