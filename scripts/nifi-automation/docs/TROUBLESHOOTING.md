# NiFi EDI Validation - Troubleshooting Guide

## 🚨 Quick Fixes

### Problem: Workflow Not Working
**Solution:** Run the clean restart script
```bash
./scripts/nifi-automation/nifi_restart_clean.sh
```

### Problem: Duplicate Processors
**Solution:** Force cleanup
```bash
python3 scripts/nifi-automation/nifi_flow_manager.py cleanup --force
```

### Problem: Processors Won't Start
**Solution:** Check status and restart
```bash
python3 scripts/nifi-automation/nifi_flow_manager.py status --verbose
python3 scripts/nifi-automation/nifi_flow_manager.py restart
```

## 🔍 Diagnostic Commands

### Check Overall Status
```bash
# Flow status with details
python3 scripts/nifi-automation/nifi_flow_manager.py status --verbose

# Container status
docker ps | grep nifi
docker logs nifi --tail 20

# Test environment
./scripts/nifi-automation/test_workflow.sh
```

### Check File Processing
```bash
# Input directory
docker exec nifi ls -la /tmp/nifi-test-data/

# Results
docker exec nifi ls -la /tmp/nifi-test-data/success/
docker exec nifi ls -la /tmp/nifi-test-data/failure/

# Sample result
docker exec nifi cat /tmp/nifi-test-data/success/*.json | head -10
```

### Check NiFi Logs
```bash
# Recent errors
docker logs nifi 2>&1 | grep -E "(ERROR|Exception)" | tail -10

# EDI processor logs
docker logs nifi 2>&1 | grep -E "(EDI|Validation)" | tail -10

# Python errors
docker logs nifi 2>&1 | grep -E "(Python|py4j)" | tail -10
```

## 🛠️ Step-by-Step Debugging

### Step 1: Verify Environment
```bash
# Check containers
docker ps | grep -E "(nifi|postgres)"

# Check NiFi accessibility
curl -s http://localhost:8080/nifi > /dev/null && echo "✅ NiFi accessible" || echo "❌ NiFi not accessible"

# Check authentication
python3 -c "
import requests
response = requests.post('http://localhost:8080/nifi-api/access/token',
    data={'username': 'superuser@edilens.com', 'password': 'password123456789'},
    headers={'Content-Type': 'application/x-www-form-urlencoded'})
print('✅ Auth working' if response.status_code == 201 else f'❌ Auth failed: {response.status_code}')
"
```

### Step 2: Check Processors
```bash
# List processors
python3 scripts/nifi-automation/nifi_flow_manager.py status

# Check for EDI processors
python3 -c "
import requests
token = requests.post('http://localhost:8080/nifi-api/access/token',
    data={'username': 'superuser@edilens.com', 'password': 'password123456789'},
    headers={'Content-Type': 'application/x-www-form-urlencoded'}).text
response = requests.get('http://localhost:8080/nifi-api/flow/processor-types',
    headers={'Authorization': f'Bearer {token}'})
types = [t['type'] for t in response.json()['processorTypes'] if 'EDI' in t['type']]
print(f'EDI processors available: {len(types)}')
for t in types: print(f'  - {t}')
"
```

### Step 3: Test Flow Creation
```bash
# Clean slate
python3 scripts/nifi-automation/nifi_flow_manager.py cleanup --force

# Create flow
python3 scripts/nifi-automation/nifi_flow_manager.py create --config scripts/nifi-automation/flows/edi-validation-flow.yaml

# Check result
python3 scripts/nifi-automation/nifi_flow_manager.py status
```

### Step 4: Test Processing
```bash
# Ensure test environment
docker exec nifi mkdir -p /tmp/nifi-test-data/{success,failure}
docker cp scripts/nifi-automation/tmp/test-data/sample_837p_valid.edi nifi:/tmp/nifi-test-data/

# Start processors
python3 scripts/nifi-automation/nifi_flow_manager.py start

# Create test file
docker exec nifi cp /tmp/nifi-test-data/sample_837p_valid.edi /tmp/nifi-test-data/debug_test_$(date +%s).edi

# Wait and check
sleep 15
docker exec nifi ls -la /tmp/nifi-test-data/success/
```

## 🔧 Common Error Patterns

### Error: "Processor has validation errors"
**Cause:** Configuration issues
**Solution:**
```bash
# Check specific errors
python3 scripts/nifi-automation/nifi_flow_manager.py status --verbose

# Common fixes:
# 1. Directory doesn't exist
docker exec nifi mkdir -p /tmp/nifi-test-data

# 2. Schema not found
docker cp nifi-edi-processors/schemas/837.5010.X222.A1.json nifi:/opt/nifi/schemas/

# 3. Property name mismatch - check YAML configuration
```

### Error: "AttributeError: 'Relationship' object has no attribute '_get_object_id'"
**Cause:** Python-Java bridge issue
**Solution:**
```bash
# This is fixed in the current code, but if you see it:
# 1. Restart NiFi
docker restart nifi

# 2. Redeploy processors
cd docker/nifi-processors && ./deploy-edi-processors.sh volume && cd ../..
```

### Error: "The desired state is not set"
**Cause:** API format issue
**Solution:**
```bash
# This is fixed in the current code
# If you still see it, try manual start in UI or restart
./scripts/nifi-automation/nifi_restart_clean.sh
```

### Error: "409 Conflict" during cleanup
**Cause:** Processors are running and can't be deleted
**Solution:**
```bash
# Use force cleanup
python3 scripts/nifi-automation/nifi_flow_manager.py cleanup --force

# Or manual stop first
python3 scripts/nifi-automation/nifi_flow_manager.py stop
python3 scripts/nifi-automation/nifi_flow_manager.py cleanup
```

## 🆘 Emergency Procedures

### Complete Reset
If everything is broken:
```bash
# 1. Stop all containers
docker-compose down

# 2. Remove NiFi data (optional - loses all flows)
docker volume rm edi-lens_nifi-data

# 3. Restart everything
docker-compose up -d

# 4. Wait for startup
sleep 180

# 5. Run clean setup
./scripts/nifi-automation/nifi_restart_clean.sh
```

### Partial Reset (Keep Data)
```bash
# 1. Clean restart script
./scripts/nifi-automation/nifi_restart_clean.sh

# 2. If that fails, manual restart
docker restart nifi
sleep 180
cd docker/nifi-processors && ./deploy-edi-processors.sh volume && cd ../..
python3 scripts/nifi-automation/nifi_flow_manager.py create --config scripts/nifi-automation/flows/edi-validation-flow.yaml --start
```

## 📞 Getting Help

### Collect Debug Information
```bash
# Create debug report
echo "=== NiFi Debug Report ===" > debug_report.txt
echo "Date: $(date)" >> debug_report.txt
echo "" >> debug_report.txt

echo "=== Container Status ===" >> debug_report.txt
docker ps | grep nifi >> debug_report.txt
echo "" >> debug_report.txt

echo "=== Flow Status ===" >> debug_report.txt
python3 scripts/nifi-automation/nifi_flow_manager.py status --verbose >> debug_report.txt 2>&1
echo "" >> debug_report.txt

echo "=== Recent Logs ===" >> debug_report.txt
docker logs nifi --tail 50 >> debug_report.txt 2>&1

echo "Debug report saved to debug_report.txt"
```

### Check Documentation
- Main README: `scripts/nifi-automation/README.md`
- Flow configuration: `scripts/nifi-automation/flows/README.md`
- Quick start: `scripts/nifi-automation/QUICK_START.md`

### Manual Verification
1. **NiFi UI:** http://localhost:8080 (superuser@edilens.com / password123456789)
2. **Check processors:** Look for validation errors (yellow triangles)
3. **Check connections:** Ensure all relationships are connected
4. **Check logs:** Look for Python/Java bridge errors