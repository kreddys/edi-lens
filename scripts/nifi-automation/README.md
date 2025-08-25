# NiFi EDI Processing Automation

Comprehensive automation framework for setting up and managing EDI processing workflows in Apache NiFi with native Python processors and YAML-based configuration.

## 🚀 Quick Start

**Complete setup (recommended):**
```bash
# From project root - Deploy processors and create environment
./scripts/nifi-automation/nifi-automation setup

# Deploy EDI processors to NiFi (hot reload for development)
./scripts/nifi-automation/nifi-automation deploy-processors volume

# Deploy pre-configured EDI workflows
./scripts/nifi-automation/nifi-automation deploy edi-validation-flow
./scripts/nifi-automation/nifi-automation test edi-validation-flow
```

**Quick reference:**
```bash
./scripts/nifi-automation/nifi-automation flows      # List available flows
./scripts/nifi-automation/nifi-automation status     # Check system status
./scripts/nifi-automation/nifi-automation help       # Get help
```

## 📁 Directory Structure

```
scripts/nifi-automation/
├── README.md                    # This comprehensive guide
├── nifi-automation              # 🎯 MAIN INTERFACE - unified command system
├── flows/                       # EDI workflow configurations
│   ├── edi-validation-flow.yaml # EDI schema validation workflow
│   ├── edi-parsing-flow.yaml    # Multi-format EDI parsing workflow
│   └── README.md               # Flow configuration documentation
├── docs/                       # Additional documentation
│   ├── QUICK_START.md          # Getting started guide
│   └── TROUBLESHOOTING.md      # Problem solving guide
├── utils/                      # Internal automation utilities
│   ├── nifi-complete-setup.sh  # Environment and service setup
│   ├── nifi-flow-manager.py    # YAML-based workflow management
│   ├── nifi-restart-clean.sh   # Emergency recovery operations
│   ├── nifi-setup-environment.sh # NiFi environment configuration
│   └── nifi-test-workflow.sh   # Automated end-to-end testing
└── tmp/                        # Temporary test data (git ignored)
    └── test-data/              # Sample EDI files for testing
```

## 🎯 Commands Reference

### Core Commands
```bash
# Environment setup
./scripts/nifi-automation/nifi-automation setup           # Complete environment setup
./scripts/nifi-automation/nifi-automation restart         # Emergency NiFi restart

# EDI Processor Management  
./scripts/nifi-automation/nifi-automation deploy-processors [method]
  # volume  - Hot reload development (default)
  # rebuild - Production Docker build
  # copy    - Direct container copy

# Workflow Management
./scripts/nifi-automation/nifi-automation flows           # List available flows
./scripts/nifi-automation/nifi-automation deploy <flow>   # Deploy workflow
./scripts/nifi-automation/nifi-automation test <flow>     # Test workflow
./scripts/nifi-automation/nifi-automation status [flow]   # Check status
./scripts/nifi-automation/nifi-automation clean [flow]    # Clean workflows

# Help & Information
./scripts/nifi-automation/nifi-automation help            # Show all commands
```

### Common Workflows
```bash
# Development Setup (Hot Reload)
./scripts/nifi-automation/nifi-automation setup
./scripts/nifi-automation/nifi-automation deploy-processors volume
./scripts/nifi-automation/nifi-automation deploy edi-validation-flow
./scripts/nifi-automation/nifi-automation test edi-validation-flow

# Production Deployment
./scripts/nifi-automation/nifi-automation setup
./scripts/nifi-automation/nifi-automation deploy-processors rebuild
./scripts/nifi-automation/nifi-automation deploy edi-parsing-flow

# Status & Monitoring
./scripts/nifi-automation/nifi-automation status              # All flows
./scripts/nifi-automation/nifi-automation status edi-validation-flow

# Troubleshooting
./scripts/nifi-automation/nifi-automation clean              # Clean all
./scripts/nifi-automation/nifi-automation restart            # Emergency restart
```

## 🔧 Prerequisites & Architecture

### Requirements
1. **Docker & Docker Compose** - NiFi containerization
2. **Python 3.9+** - EDI processors and automation scripts
3. **curl** - NiFi API communication
4. **EDI Lens Backend** - Complete project with schemas and test data

### Architecture Overview
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ nifi-automation │───▶│ Apache NiFi      │───▶│ EDI Processors  │
│ (Control Layer) │    │ (Container)      │    │ (Python Native) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ YAML Workflows  │    │ Flow Management  │    │ Schema Engines  │
│ & Test Data     │    │ & Monitoring     │    │ & Validation    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

### EDI Processors Integration
- **Validation Processor** - Schema-based EDI validation with detailed findings
- **Parsing Processor** - Multi-format output (JSON/XML/CSV) with metadata
- **TA1 Generator** - Automatic acknowledgment response generation

## 📊 Generated Components

### EDI Processing Workflows

**Validation Flow:**
```
[GetFile] → [EDI Validation] → [TA1 Generator] → [EDI Parser] → [PutFile Success]
                    ↓                ↓               ↓
             [PutFile Failure]  [PutFile TA1]  [PutFile Parsed]
```

**Complete Processing Pipeline:**
```
Input EDI → Validation → TA1 Acknowledgment → Multi-format Parsing → Output
    │            │              │                        │
    ▼            ▼              ▼                        ▼
Raw Files   Validation     TA1 Response           JSON/XML/CSV
              Report        Document               Structured Data
```

### Test Data & Environment
- **Valid 837P EDI** - Clean healthcare claims for successful processing
- **Invalid 837P EDI** - Validation error scenarios and edge cases  
- **Complex Multi-Claim EDI** - High-volume processing scenarios
- **Schema Files** - Implementation guide schemas (837P, 270, etc.)

### Directory Structure Created
```
/tmp/nifi-test-data/              # NiFi processing directories
├── input/                        # Source EDI files
├── success/                      # Successfully processed files
├── failure/                      # Validation failures
├── ta1/                         # Generated TA1 responses
└── parsed/                       # Multi-format parsed output

scripts/nifi-automation/tmp/      # Local automation data
└── test-data/                    # Sample EDI files for testing
```

## 🧪 Testing & Validation

### Automated Testing
```bash
# Test specific workflow
./scripts/nifi-automation/nifi-automation test edi-validation-flow
./scripts/nifi-automation/nifi-automation test edi-parsing-flow

# Run comprehensive test suite  
./scripts/nifi-automation/utils/nifi-test-workflow.sh

# Test EDI processors unit tests (130+ tests)
./run.sh dev:test unit:edi
```

### Manual Testing
```bash
# Deploy processors and test validation
./scripts/nifi-automation/nifi-automation deploy-processors volume
./scripts/nifi-automation/nifi-automation deploy edi-validation-flow

# Test with sample EDI files

docker exec -it nifi mkdir -p /tmp/nifi-test-data/input

docker cp scripts/nifi-automation/tmp/test-data/sample_837p_valid.edi nifi:/tmp/nifi-test-data/input/

docker cp scripts/nifi-automation/tmp/test-data/sample_837p_invalid.edi nifi:/tmp/nifi-test-data/input/

# Monitor processing results
./scripts/nifi-automation/nifi-automation status edi-validation-flow
ls -la /tmp/nifi-test-data/{success,failure,ta1,parsed}/

# View processed results
cat /tmp/nifi-test-data/success/*.json       # Validation results
cat /tmp/nifi-test-data/ta1/*.edi           # TA1 acknowledgments  
cat /tmp/nifi-test-data/parsed/*.json       # Parsed EDI data
```

### Performance Testing
```bash
# Monitor NiFi container performance
docker stats nifi

# Check processor throughput in NiFi UI
open http://localhost:8080  # Login: superuser@edilens.com / password123456789

# High-volume testing
for i in {1..100}; do
  cp scripts/nifi-automation/tmp/test-data/sample_837p_valid.edi /tmp/nifi-test-data/input/test_$i.edi
done
```

## 🔍 Monitoring & Troubleshooting

### System Status & Health Checks
```bash
# Check overall system status
./scripts/nifi-automation/nifi-automation status

# Check specific workflow status  
./scripts/nifi-automation/nifi-automation status edi-validation-flow

# Test workflow functionality
./scripts/nifi-automation/nifi-automation test edi-validation-flow

# Verify processor deployment
docker exec nifi ls -la /opt/nifi/nifi-current/python_extensions/edi-processors/

# Check NiFi container health
docker logs nifi | tail -50
docker exec nifi ps aux | grep python

# Access NiFi Web UI
open http://localhost:8080  # Login: superuser@edilens.com / password123456789
```

### Common Issues & Solutions

#### 1. EDI Processors Not Loading
```bash
# Check processor deployment status
docker exec nifi ls -la /opt/nifi/nifi-current/python_extensions/edi-processors/

# Redeploy processors with hot reload
./scripts/nifi-automation/nifi-automation deploy-processors volume

# Check NiFi logs for Python errors
docker logs nifi | grep -i "python\|error\|exception" | tail -20

# Verify processor initialization
docker logs nifi | grep -i "FlowFileTransform\|EDI"
```

#### 2. Workflow Deployment Issues
```bash
# Clean existing workflows
./scripts/nifi-automation/nifi-automation clean

# Force cleanup and restart NiFi
./scripts/nifi-automation/nifi-automation restart

# Redeploy with fresh start
./scripts/nifi-automation/nifi-automation setup
./scripts/nifi-automation/nifi-automation deploy-processors volume
./scripts/nifi-automation/nifi-automation deploy edi-validation-flow
```

#### 3. Processing Failures
```bash
# Check workflow status
./scripts/nifi-automation/nifi-automation status edi-validation-flow

# Verify test directories exist
docker exec nifi mkdir -p /tmp/nifi-test-data/{input,success,failure,ta1,parsed}

# Check for schema files
docker exec nifi ls -la /opt/nifi/schemas/

# Test with known good EDI file
./scripts/nifi-automation/nifi-automation test edi-validation-flow
```

#### 4. Schema Loading Issues
```bash
# Verify schema files are present
docker exec nifi ls -la /opt/nifi/schemas/

# Copy schemas if missing (run setup again)
./scripts/nifi-automation/nifi-automation setup

# Check schema permissions
docker exec nifi chmod -R 644 /opt/nifi/schemas/

# Test schema loading in processor
docker logs nifi | grep -i "schema\|837"
```

#### 5. Performance Issues
```bash
# Monitor container resources
docker stats nifi

# Check processor queue status in NiFi UI
open http://localhost:8080

# Increase processor concurrent tasks (via NiFi UI):
# Right-click processor → Configure → Scheduling → Concurrent tasks: 2-4

# Monitor processing throughput
./scripts/nifi-automation/nifi-automation status edi-validation-flow
```

### Emergency Recovery
```bash
# Complete system reset (last resort)
./scripts/nifi-automation/nifi-automation restart

# Full environment rebuild
docker-compose down
docker system prune -f
./scripts/nifi-automation/nifi-automation setup
```

## 🎛️ Configuration & Customization

### EDI Processor Properties
**Validation Processor:**
- `Validation Schema`: `837.5010.X222.A1.json` (or custom schema)
- `SNIP Level`: `3` (1-5, where 5 is most strict validation)
- `Tenant ID`: `tenant-a` (multi-tenant schema resolution)
- `Schema Base Path`: `/opt/nifi/schemas` (container path)
- `Cache Schemas`: `true` (performance optimization)

**Parsing Processor:**
- `Output Format`: `JSON` (JSON/XML/CSV options)
- `Include Metadata`: `true` (adds processing metadata)
- `Schema Name`: `837.5010.X222.A1.json` (for parsing guidance)
- `Tenant ID`: `tenant-a`

**TA1 Generation Processor:**
- `Force TA1 Generation`: `false` (generate only when requested)
- `TA1 Control Number Strategy`: `AUTO` (automatic numbering)

### Advanced Configuration
```bash
# Custom schema deployment
cp custom-schema.json nifi-edi-processors/schemas/
./scripts/nifi-automation/nifi-automation setup  # Redeploys schemas

# Modify workflow YAML files
vi scripts/nifi-automation/flows/edi-validation-flow.yaml

# Custom test data
cp custom-edi-file.edi scripts/nifi-automation/tmp/test-data/
```

## 📈 Performance & Scalability

### High-Volume Processing
```bash
# Test processor throughput (30,000+ segments/second capable)
./run.sh dev:test unit:edi  # Verify all 130+ tests pass

# Bulk testing with multiple files
for i in {1..1000}; do
  cp scripts/nifi-automation/tmp/test-data/sample_837p_valid.edi \
     /tmp/nifi-test-data/input/bulk_test_$i.edi
done

# Monitor processing performance
docker stats nifi
./scripts/nifi-automation/nifi-automation status edi-validation-flow
```

### Performance Optimization
1. **Processor Tuning** - Increase concurrent tasks (2-4 per processor)
2. **Memory Management** - Adjust NiFi JVM settings in docker-compose
3. **Batch Processing** - Configure GetFile to process multiple files per batch
4. **Schema Caching** - Enable schema caching for faster validation
5. **Container Resources** - Allocate adequate CPU/memory to NiFi container

## 🔗 Integration Points

### EDI Lens Backend Integration
- **Shared Schemas** - Uses same implementation guide schemas (837P, 270, etc.)
- **Common Validation Logic** - Consistent validation results across components  
- **Multi-Tenant Support** - Compatible tenant isolation and routing
- **Error Reporting** - Unified error codes and messages

### Docker Environment Integration
- **Compose Compatibility** - Works with existing docker-compose.yml
- **Volume Management** - Hot reload support for development workflows
- **Network Integration** - Proper container networking and port management
- **Resource Sharing** - Shared directories and schema files

### Enterprise Features
- **NiFi Registry** - Compatible with flow versioning and deployment
- **Monitoring Integration** - Logs work with Prometheus/Grafana stacks
- **Multi-Environment** - Supports dev/staging/production deployments
- **Audit Trails** - Complete processing lineage and provenance

## 📝 Important Notes

✅ **Design Principles:**
- **Idempotent Operations** - All commands safe to run multiple times
- **Clean Temporary Files** - Uses `/tmp/` to avoid project clutter  
- **Comprehensive Error Handling** - Graceful failure recovery
- **Hot Reload Support** - Development-friendly volume mounting

✅ **Compatibility:**
- **NiFi**: 1.23.0+ with Python processor support
- **Python**: 3.9+ for EDI processors and automation
- **Docker**: 20.10+ with compose v2
- **EDI Standards**: X12 5010+ healthcare transactions

⚠️ **Production Considerations:**
- Use `deploy-processors rebuild` for immutable deployments
- Monitor NiFi container resource usage under load
- Configure appropriate schema caching for your volume
- Test thoroughly with your specific EDI transaction types

---

*Built for high-performance EDI processing in Apache NiFi with native Python processors* 🚀