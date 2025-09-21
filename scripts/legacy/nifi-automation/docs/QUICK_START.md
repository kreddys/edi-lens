# NiFi EDI Processing - Quick Start Guide

## 🚀 Complete Setup (3 Commands)

```bash
# 1. Environment and NiFi setup
./scripts/nifi-automation/nifi-automation setup

# 2. Deploy EDI processors (hot reload for development)
./scripts/nifi-automation/nifi-automation deploy-processors volume

# 3. Deploy and test validation workflow
./scripts/nifi-automation/nifi-automation deploy edi-validation-flow
./scripts/nifi-automation/nifi-automation test edi-validation-flow
```

## 🆘 If Something Goes Wrong

```bash
# Clean restart (fixes most issues)
./scripts/nifi-automation/nifi-automation restart

# Or complete reset
./scripts/nifi-automation/nifi-automation clean
```

## ✅ Verify Everything Works

```bash
# Check system status
./scripts/nifi-automation/nifi-automation status

# Check specific workflow
./scripts/nifi-automation/nifi-automation status edi-validation-flow

# Run EDI processor tests (130+ tests)
./run.sh dev:test unit:edi
```

## 🎯 Access Your NiFi Environment

1. **Open NiFi UI:** http://localhost:8080
2. **Login:** superuser@edilens.com / password123456789  
3. **View deployed workflows:** Processors auto-configured and connected
4. **Test processing:** Drop EDI files and watch them process

## 📊 What You Get

### EDI Processing Capabilities
- **3 Native Python Processors:** Validation, Parsing, TA1 Generation
- **Multi-format Output:** JSON, XML, CSV with metadata
- **Schema-based Validation:** Implementation guide compliance 
- **130+ Unit Tests:** Comprehensive test coverage

### Automated Workflows  
- **Validation Flow:** Complete EDI validation with error handling
- **Parsing Flow:** Multi-format EDI-to-structured-data conversion
- **TA1 Response Flow:** Automatic acknowledgment generation
- **Test Data Processing:** Automated end-to-end validation

## 🔧 Command Reference

### Core Operations
```bash
# Check system/workflow status  
./scripts/nifi-automation/nifi-automation status [flow-name]

# Deploy processors (development hot-reload)
./scripts/nifi-automation/nifi-automation deploy-processors volume

# Deploy/manage workflows
./scripts/nifi-automation/nifi-automation deploy <flow-name>
./scripts/nifi-automation/nifi-automation test <flow-name>
./scripts/nifi-automation/nifi-automation clean [flow-name]

# List available workflows
./scripts/nifi-automation/nifi-automation flows

# Emergency operations
./scripts/nifi-automation/nifi-automation restart
```

### Available Workflows
- `edi-validation-flow` - Complete EDI validation pipeline
- `edi-parsing-flow` - Multi-format EDI parsing workflow  
- More flows available in `scripts/nifi-automation/flows/`

## 🧪 Quick Test

```bash
# Test with sample EDI files
cp scripts/nifi-automation/tmp/test-data/sample_837p_valid.edi /tmp/nifi-test-data/input/
cp scripts/nifi-automation/tmp/test-data/sample_837p_invalid.edi /tmp/nifi-test-data/input/

# Check processing results (after 10 seconds)
ls -la /tmp/nifi-test-data/{success,failure,ta1,parsed}/
cat /tmp/nifi-test-data/success/*.json | head -20

# Or use automated testing
./scripts/nifi-automation/nifi-automation test edi-validation-flow
```

## 📂 Directory Structure Created

```
/tmp/nifi-test-data/
├── input/           # Drop EDI files here for processing
├── success/         # Successfully validated EDI → JSON
├── failure/         # Validation failures with detailed errors  
├── ta1/            # Generated TA1 acknowledgment responses
└── parsed/         # Multi-format parsed EDI (JSON/XML/CSV)
```

## 🔍 Troubleshooting

**Processors not loading?**
```bash
./scripts/nifi-automation/nifi-automation deploy-processors volume
docker logs nifi | grep -i "python\|error" | tail -10
```

**Workflows not working?** 
```bash
./scripts/nifi-automation/nifi-automation clean
./scripts/nifi-automation/nifi-automation deploy edi-validation-flow
```

**Complete reset needed?**
```bash
./scripts/nifi-automation/nifi-automation restart
./scripts/nifi-automation/nifi-automation setup
```

**Need detailed help?**
```bash
./scripts/nifi-automation/nifi-automation help
cat scripts/nifi-automation/docs/TROUBLESHOOTING.md
```

## 🎉 You're Ready!

Your **high-performance NiFi EDI processing system** is ready with:
- ✅ **Native Python processors** with 30,000+ segments/second capability  
- ✅ **Multi-format output** (JSON/XML/CSV) with metadata
- ✅ **Comprehensive validation** using implementation guide schemas
- ✅ **130+ automated tests** ensuring reliability
- ✅ **Hot reload development** workflow for rapid iteration

**Happy EDI Processing!** 🚀