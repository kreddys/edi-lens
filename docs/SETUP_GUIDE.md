# EDI Lens - Complete Setup Guide

Comprehensive setup guide for the EDI Lens project with NiFi EDI processors and automation framework.

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        EDI Lens Project                         │
├─────────────────────────────────────────────────────────────────┤
│ Backend API        │ NiFi Processors    │ Automation Framework │
│ (FastAPI/Python)   │ (Native Python)    │ (Shell/Python)       │
│                    │                    │                      │
│ • REST API         │ • EDI Validation   │ • Environment Setup  │
│ • Schema Engine    │ • Multi-format     │ • Workflow Deploy    │
│ • Multi-tenant     │   Parsing          │ • Testing Suite      │
│ • Database         │ • TA1 Generation   │ • Monitoring         │
└─────────────────────────────────────────────────────────────────┘
```

## 📋 Prerequisites

### Required Software
- **Docker** 20.10+ with Docker Compose v2
- **Python** 3.9+ with pip
- **Poetry** (Python package manager)
- **Git** (version control)
- **curl** (API testing)

### System Requirements
- **RAM**: 8GB minimum (16GB recommended for high-volume processing)
- **Storage**: 10GB free space
- **Network**: Internet access for Docker image downloads
- **Ports**: 8080 (NiFi UI), 8000 (Backend API), 5432 (PostgreSQL)

### Verification
```bash
# Check prerequisites
docker --version && docker compose version
python3 --version && poetry --version
git --version && curl --version

# Check available memory
free -h  # Linux/WSL
top -l 1 | grep PhysMem  # macOS
```

## 🚀 Quick Start (5 Minutes)

### Option 1: Complete Development Setup
```bash
# 1. Clone and setup project
git clone <repository-url> edi-lens
cd edi-lens

# 2. Start services
docker compose up -d

# 3. Setup NiFi automation
./scripts/nifi-automation/nifi-automation setup

# 4. Deploy EDI processors (hot reload for development)
./scripts/nifi-automation/nifi-automation deploy-processors volume

# 5. Deploy and test validation workflow
./scripts/nifi-automation/nifi-automation deploy edi-validation-flow
./scripts/nifi-automation/nifi-automation test edi-validation-flow
```

### Option 2: Backend Only Setup
```bash
# 1. Clone and setup
git clone <repository-url> edi-lens
cd edi-lens

# 2. Install dependencies
poetry install

# 3. Start backend services
docker compose up -d postgres keycloak

# 4. Run backend
poetry run python -m app.main
```

## 🔧 Detailed Setup

### 1. Project Structure Overview
```
edi-lens/
├── 📁 backend/                      # FastAPI backend application
│   ├── app/                         # Application code
│   ├── tests/                       # Backend tests
│   └── pyproject.toml               # Backend dependencies
├── 📁 nifi-edi-processors/          # Native Python NiFi processors
│   ├── processors/                  # Core NiFi processors
│   ├── tests/                       # 130+ processor tests
│   ├── schemas/                     # EDI implementation schemas
│   └── pyproject.toml              # Processor dependencies
├── 📁 scripts/nifi-automation/      # Automation framework
│   ├── nifi-automation             # Main automation script
│   ├── flows/                      # YAML workflow definitions
│   ├── utils/                      # Utility scripts
│   └── docs/                       # Documentation
├── 📁 docker/                      # Docker configurations
│   └── nifi-processors/            # NiFi processor Dockerfiles
└── 📄 run.sh                       # Unified build/test script
```

### 2. Environment Setup

#### Docker Services
```bash
# Start all services
docker compose up -d

# Verify services are running
docker compose ps

# Expected services:
# - postgres (Database)
# - keycloak (Authentication) 
# - nifi (Processing Engine)
# - sftp-server (File Transfer)
```

#### Backend Setup
```bash
# Install Python dependencies
poetry install

# Run database migrations
poetry run alembic upgrade head

# Start backend API
poetry run python -m app.main

# Verify API is running
curl http://localhost:8000/health
```

#### NiFi Processor Setup
```bash
# Deploy processors to NiFi (development mode)
./scripts/nifi-automation/nifi-automation deploy-processors volume

# Verify processors are loaded
docker logs nifi | grep -i "EDI\|FlowFileTransform"

# Check NiFi UI: http://localhost:8080
# Login: superuser@edilens.com / password123456789
```

### 3. Workflow Deployment

#### Available Workflows
- **edi-validation-flow** - Complete EDI schema validation pipeline
- **edi-parsing-flow** - Multi-format EDI parsing (JSON/XML/CSV)
- **edi-complete-flow** - End-to-end processing with TA1 generation

#### Deploy and Test
```bash
# List available workflows
./scripts/nifi-automation/nifi-automation flows

# Deploy validation workflow
./scripts/nifi-automation/nifi-automation deploy edi-validation-flow

# Test with sample data
./scripts/nifi-automation/nifi-automation test edi-validation-flow

# Monitor processing
./scripts/nifi-automation/nifi-automation status edi-validation-flow
```

## 🧪 Testing & Validation

### Backend Tests
```bash
# Run all backend tests
./run.sh dev:test backend:all

# Run specific test categories  
./run.sh dev:test backend:unit      # Unit tests
./run.sh dev:test backend:integration  # Integration tests
./run.sh dev:test backend:e2e       # End-to-end tests
```

### EDI Processor Tests
```bash
# Run all EDI processor tests (130+ tests)
./run.sh dev:test unit:edi

# Run specific test files
cd nifi-edi-processors
python -m pytest tests/test_validation_service.py -v
python -m pytest tests/test_parsing_formats.py -v
python -m pytest tests/test_ta1_generator.py -v
```

### End-to-End Integration Tests
```bash
# Test complete workflow
./scripts/nifi-automation/nifi-automation test edi-validation-flow

# Test with sample EDI files
cp scripts/nifi-automation/tmp/test-data/sample_837p_valid.edi /tmp/nifi-test-data/input/
ls -la /tmp/nifi-test-data/{success,failure,ta1,parsed}/

# Performance testing
for i in {1..100}; do
  cp scripts/nifi-automation/tmp/test-data/sample_837p_valid.edi /tmp/nifi-test-data/input/test_$i.edi
done
```

## 📊 Monitoring & Operations

### Health Checks
```bash
# System status
./scripts/nifi-automation/nifi-automation status

# Service health
curl http://localhost:8000/health          # Backend API
curl http://localhost:8080/nifi/           # NiFi UI
docker compose ps                          # All services

# Resource monitoring
docker stats nifi postgres keycloak       # Container resources
```

### Log Management
```bash
# View service logs
docker logs nifi | tail -50               # NiFi processing logs
docker logs postgres                       # Database logs  
docker logs keycloak                       # Authentication logs

# Search for errors
docker logs nifi | grep -i "error\|exception\|failed"

# Monitor real-time
docker logs -f nifi
```

### Performance Monitoring
```bash
# NiFi processing metrics (via UI)
open http://localhost:8080

# Backend API metrics
curl http://localhost:8000/metrics

# Database performance
docker exec postgres psql -U postgres -c "SELECT * FROM pg_stat_activity;"

# System resources
htop  # or top
df -h  # disk usage
```

## 🔄 Development Workflows

### Hot Reload Development
```bash
# Deploy processors with volume mounting (changes reflect immediately)
./scripts/nifi-automation/nifi-automation deploy-processors volume

# Make changes to processors
vi nifi-edi-processors/processors/edi_validation_processor.py

# Restart specific processor in NiFi UI or redeploy
./scripts/nifi-automation/nifi-automation deploy-processors volume
```

### Backend Development
```bash
# Start backend in development mode (auto-reload)
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run tests on file change
poetry run pytest-watch

# Database development
docker exec -it postgres psql -U postgres
```

### Testing Pipeline
```bash
# Pre-commit testing
./run.sh dev:test unit:all              # All unit tests
poetry run ruff check .                 # Code linting  
poetry run mypy backend/                # Type checking

# Full integration testing
./run.sh dev:test integration:all       # Integration tests
./scripts/nifi-automation/nifi-automation test edi-validation-flow
```

## 🚀 Production Deployment

### Production NiFi Processors
```bash
# Build immutable processor image
./scripts/nifi-automation/nifi-automation deploy-processors rebuild

# Or use Docker directly
docker build -f docker/nifi-processors/Dockerfile.extension -t nifi-edi:latest .
```

### Production Backend
```bash
# Build production image
docker build -t edi-lens-backend:latest .

# Run with production settings
export ENV=production
poetry run python -m app.main
```

### Production Configuration
```bash
# Environment variables
export DATABASE_URL="postgresql://user:pass@host:5432/db"
export KEYCLOAK_URL="https://auth.company.com"
export REDIS_URL="redis://redis:6379"
export LOG_LEVEL="INFO"

# NiFi production settings
# - Increase memory: -Xmx8g
# - Enable clustering  
# - Configure persistent storage
# - Set up monitoring
```

## 🔧 Troubleshooting

### Common Issues

#### 1. Services Won't Start
```bash
# Check port conflicts
netstat -tulpn | grep -E ":(8080|8000|5432)"

# Check Docker resources
docker system df
docker system prune -f

# Restart services
docker compose down && docker compose up -d
```

#### 2. EDI Processors Not Loading
```bash
# Check processor deployment
docker exec nifi ls -la /opt/nifi/nifi-current/python_extensions/edi-processors/

# Check NiFi logs
docker logs nifi | grep -i "python\|edi\|error" | tail -20

# Redeploy processors
./scripts/nifi-automation/nifi-automation deploy-processors volume
```

#### 3. Tests Failing
```bash
# Check test environment
docker compose ps
./scripts/nifi-automation/nifi-automation status

# Run specific failing tests
cd nifi-edi-processors && python -m pytest tests/test_validation_service.py -v -s

# Reset test environment
./scripts/nifi-automation/nifi-automation clean
./scripts/nifi-automation/nifi-automation setup
```

#### 4. Performance Issues
```bash
# Monitor resources
docker stats
htop

# Check NiFi performance
open http://localhost:8080  # View processor statistics

# Optimize configuration
# - Increase NiFi memory: edit docker-compose.yml
# - Increase processor concurrent tasks: via NiFi UI
# - Enable schema caching: processor properties
```

### Emergency Recovery
```bash
# Complete system reset
docker compose down -v  # WARNING: Deletes all data
docker system prune -f
git clean -fdx
./scripts/nifi-automation/nifi-automation setup
```

## 📚 Additional Resources

### Documentation
- **API Documentation**: http://localhost:8000/docs (when running)
- **NiFi Automation**: `scripts/nifi-automation/README.md`
- **EDI Processors**: `nifi-edi-processors/README.md`  
- **Quick Start**: `scripts/nifi-automation/docs/QUICK_START.md`
- **Troubleshooting**: `scripts/nifi-automation/docs/TROUBLESHOOTING.md`

### Key Files
- **Main Script**: `scripts/nifi-automation/nifi-automation`
- **Build Script**: `./run.sh`
- **Docker Compose**: `docker-compose.yml`
- **Backend Config**: `backend/app/core/config.py`

### Support & Development
```bash
# Get help
./scripts/nifi-automation/nifi-automation help
./run.sh help

# View logs
docker logs nifi
docker logs postgres
poetry run python -m app.main --log-level DEBUG
```

---

## 🎯 Next Steps

1. **Complete Setup**: Follow the Quick Start for full environment
2. **Run Tests**: Verify all 130+ tests pass with `./run.sh dev:test unit:edi`  
3. **Deploy Workflows**: Start with `edi-validation-flow`
4. **Test Processing**: Use sample EDI files in `scripts/nifi-automation/tmp/test-data/`
5. **Monitor Performance**: Use NiFi UI and system monitoring tools
6. **Customize**: Modify workflows, add schemas, create custom processors

**Your high-performance EDI processing system is ready for production!** 🚀