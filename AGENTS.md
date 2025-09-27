# EDI Lens - Agent Development Guide

Welcome to the EDI Lens project! This guide provides essential information for AI agents working on this codebase.

## 🚀 Quick Setup

### Unified Development Interface

**The project automatically detects your environment and uses the appropriate backend:**

```bash
# Start all services (auto-detects Docker vs native environment)
bash scripts/maintain.sh start

# Check service status
bash scripts/maintain.sh status
```

**Environment Detection:**
- **Local Development**: Uses Docker containers (maintain_local.sh)
- **Codex Environment**: Uses native services with sudo (maintain_codex.sh)
- **Auto-Detection**: Checks for Codex markers, PostgreSQL service, environment variables

### 🚨 CRITICAL: Always Use the Unified Maintenance Script

**NEVER run services directly!** Always use the unified maintenance script:

#### ❌ **DON'T DO THIS:**
```bash
npm run dev                    # DON'T run frontend directly
poetry run uvicorn src.main:app  # DON'T run backend directly  
docker-compose up              # DON'T use docker-compose directly
```

#### ✅ **DO THIS INSTEAD:**
```bash
# Unified interface (auto-detects environment)
bash scripts/maintain.sh start        # Start all services
bash scripts/maintain.sh status       # Check health  
bash scripts/maintain.sh test unit    # Run tests
bash scripts/maintain.sh logs backend # Debug issues
```

## 🏗️ Project Structure

```
edi-lens/
├── backend/                 # FastAPI backend application
│   ├── src/                # Source code
│   │   ├── api/           # FastAPI routes and dependencies
│   │   ├── clients/       # NiFi and Registry API clients
│   │   ├── core/          # Core configuration and database
│   │   ├── models/        # Pydantic models
│   │   └── services/      # Domain services and orchestration
│   ├── tests/             # Test suites
│   └── pyproject.toml     # Poetry configuration
├── frontend/               # React/Vite frontend
├── scripts/               # Development and deployment scripts
├── nifi-edi-processors/   # Custom NiFi processors for EDI parsing
└── .env.local             # Environment configuration
```

## 🧪 Testing & Development Commands

### 📋 **Complete Command Reference**

The unified `maintain.sh` script automatically detects your environment and provides a consistent interface:

```bash
# All commands use the same syntax regardless of environment
bash scripts/maintain.sh <command>
```

#### **Essential Commands**
```bash
start                # Start all services (frontend + backend + infrastructure)
stop                 # Stop all services gracefully
restart              # Stop and start all services
status               # Show service health summary
dev                  # Alias for 'start' - development mode
```

#### **Testing Commands**
```bash
test                 # Run all tests (backend + frontend)
test unit            # Run unit tests (backend + frontend)
test integration     # Run integration tests (backend + frontend)
test e2e             # Run end-to-end tests (backend + frontend)
test watch           # Run backend tests in watch mode
```

#### **Debugging Commands**
```bash
logs backend         # Show backend API logs
logs frontend        # Show frontend dev server logs
logs nifi            # Show NiFi service logs
logs registry        # Show NiFi Registry logs
logs db              # Show PostgreSQL logs
```

#### **Maintenance Commands**
```bash
clean                # DESTRUCTIVE: Remove all data, containers, volumes
```

### 🚀 **Quick Start Workflows**

#### **Daily Development Workflow**
```bash
# Start everything for development
bash scripts/maintain.sh start

# Check that all services are healthy
bash scripts/maintain.sh status

# Run tests after making changes
bash scripts/maintain.sh test unit

# View logs if there are issues
bash scripts/maintain.sh logs backend
bash scripts/maintain.sh logs frontend

# Clean restart when needed
bash scripts/maintain.sh restart
```

#### **Complete Testing Workflow**
```bash
# Ensure all services are running
bash scripts/maintain.sh status

# Run comprehensive test suite
bash scripts/maintain.sh test all

# Run specific test types
bash scripts/maintain.sh test unit         # Fast unit tests
bash scripts/maintain.sh test integration  # API integration tests  
bash scripts/maintain.sh test e2e          # Full end-to-end tests

# Run tests in watch mode during development
bash scripts/maintain.sh test watch
```

### 🌐 **Service Endpoints**

When services are running, access them at:

- **Frontend**: http://localhost:3000 (React/Vite dev server)
- **Backend API**: http://localhost:8000 (FastAPI + docs at `/docs`)
- **NiFi**: https://localhost:8443/nifi/ (user: `admin`)
- **NiFi Registry**: http://localhost:18080/nifi-registry/
- **PostgreSQL**: localhost:5432 (database: `edi_lens`)

### 🧪 **Test Types Explained**

#### **Unit Tests** (`test unit`)
- **Backend**: Tests isolated components without external dependencies
- **Frontend**: Currently not configured (shows as skipped)
- **Speed**: Fast (< 30 seconds)
- **Location**: `backend/tests/unit/`

#### **Integration Tests** (`test integration`) 
- **Backend**: Tests API clients and service integrations (47 tests)
- **Frontend**: Currently not configured (shows as skipped)
- **Speed**: Medium (~15 seconds)
- **Requirements**: Running NiFi, Registry, and PostgreSQL
- **Location**: `backend/tests/integration/`

#### **End-to-End Tests** (`test e2e`)
- **Backend**: Tests complete workflows from API to NiFi deployment (2 tests)
- **Frontend**: Playwright tests covering full user workflows (7 tests)
- **Speed**: Slow (~10 seconds)
- **Requirements**: All services running and healthy
- **Location**: `backend/tests/e2e/`, `frontend/src/tests/e2e/`

### 🔧 **Development Tools**

#### **Backend Management**
```bash
# Check backend dependencies
cd backend && poetry check

# Interactive backend development  
cd backend && poetry shell

# Run backend directly (for debugging)
cd backend && poetry run uvicorn src.main:app --reload
```

#### **Frontend Management**  
```bash
# Check frontend dependencies
cd frontend && npm list

# Run frontend directly (for debugging)
cd frontend && npm run dev

# Run frontend tests directly
cd frontend && npm run test:e2e
```

### 📊 **Service Health Monitoring**

# Check all logs
ls -la logs/                    # Local development logs
ls -la ~/.codex-services/logs/  # Codex environment logs
```

## 📋 Environment Configuration

The project uses `.env.local` for all environment configuration:

- **PostgreSQL**: `postgres/postgres@localhost:5432`
- **NiFi**: `admin/adminadmin123@https://localhost:8443`
- **NiFi Registry**: `http://localhost:18080`
- **Backend API**: `http://localhost:8000`

## 🎯 Key Technologies

- **Backend**: FastAPI, Python 3.12, Poetry, PostgreSQL
- **Frontend**: React, TypeScript, Vite
- **Data Processing**: Apache NiFi, NiFi Registry
- **EDI Processing**: Custom Python processors for X12 EDI parsing
- **Testing**: pytest, Docker Compose for integration testing

## 📚 Important Files

### Configuration
- `.env.local` - Environment variables for all services
- `backend/pyproject.toml` - Python dependencies and project config

### Scripts
- `scripts/maintain.sh` - **UNIFIED SCRIPT** - Auto-detects environment and delegates appropriately
- `scripts/setup_codex.sh` - Complete Codex environment setup (includes frontend + backend)
- `scripts/maintain_codex.sh` - Codex service management (called automatically by maintain.sh)
- `scripts/maintain_local.sh` - Local development service management (called automatically by maintain.sh)

### Testing
- `backend/tests/conftest.py` - Test configuration and fixtures
- `backend/tests/env/` - Environment templates for testing

## 🔍 Architecture Overview

### Backend (FastAPI)
- **API Layer**: REST endpoints for workflow management
- **Services Layer**: Domain logic for NiFi orchestration
- **Clients Layer**: API clients for NiFi and Registry
- **Core Layer**: Database, configuration, logging

### Data Flow
1. **Upload EDI files** via REST API
2. **Parse and validate** using custom NiFi processors
3. **Transform data** through configurable NiFi workflows
4. **Store results** in PostgreSQL database
5. **Version control** workflows in NiFi Registry

## 🚨 Important Notes

- Always ensure services are running before tests with `bash scripts/maintain.sh status`
- Backend dependencies are managed with Poetry
- Frontend dependencies are managed with npm
- All services run on localhost with standard ports
- Check service health with maintenance script before testing
- **The unified maintain.sh script auto-detects your environment** - no need to worry about Docker vs native services
- Ignore any directories that end with `_legacy`; they contain deprecated code that should not be modified or considered during development or reviews.

## 🆘 Troubleshooting

### 🔍 **Diagnostic Commands**

#### **Check Service Health**
```bash
# Quick health check - shows service status
bash scripts/maintain.sh status
```

#### **View Service Logs**
```bash
# Backend API issues
bash scripts/maintain.sh logs backend

# Frontend development server issues  
bash scripts/maintain.sh logs frontend

# NiFi data processing issues
bash scripts/maintain.sh logs nifi

# NiFi Registry version control issues
bash scripts/maintain.sh logs registry

# Database connection issues
bash scripts/maintain.sh logs db
```

### 🚨 **Common Issues & Solutions**

#### **Services Not Starting**
```bash
# Step 1: Check if ports are in use
netstat -tulpn | grep -E ":3000|:8000|:8443|:18080|:5432"

# Step 2: Clean restart everything
bash scripts/maintain.sh stop
bash scripts/maintain.sh start

# Step 3: If still failing, check logs
bash scripts/maintain.sh logs backend
bash scripts/maintain.sh logs frontend
```

#### **Tests Failing**
```bash
# Step 1: Verify all services are healthy
bash scripts/maintain.sh status

# Step 2: Check for service errors
bash scripts/maintain.sh logs backend
bash scripts/maintain.sh logs nifi

# Step 3: Run tests with proper environment
bash scripts/maintain.sh test integration
```

#### **Backend Issues**
```bash
# Check backend service health
bash scripts/maintain.sh logs backend

# Interactive debugging
cd backend && poetry shell
poetry run uvicorn src.main:app --reload

# Verify Python dependencies
cd backend && poetry check
poetry install --with dev
```

#### **Frontend Issues**  
```bash
# Check frontend development server
bash scripts/maintain.sh logs frontend

# Interactive debugging
cd frontend && npm run dev

# Verify Node.js dependencies
cd frontend && npm list
npm ci
```

#### **Database Connection Issues**
```bash
# Check PostgreSQL status
bash scripts/maintain.sh logs db

# Test database connectivity
bash scripts/maintain.sh status
```

#### **NiFi/Registry Issues**
```bash
# Check NiFi logs
bash scripts/maintain.sh logs nifi
bash scripts/maintain.sh logs registry

# Verify NiFi web interface
curl -k https://localhost:8443/nifi/

# Check NiFi Registry connectivity  
curl http://localhost:18080/nifi-registry/
```

### 🔧 **Advanced Troubleshooting**

#### **Clean Environment Reset**
```bash
# WARNING: This removes all data!
bash scripts/maintain.sh clean

# Then restart fresh
bash scripts/maintain.sh start
```

#### **Individual Service Management**
```bash
# Stop specific services if needed
pkill -f "uvicorn.*src.main:app"    # Stop backend
pkill -f "npm.*dev"                 # Stop frontend

# Check what's running on ports
lsof -i :3000  # Frontend port
lsof -i :8000  # Backend port
lsof -i :8443  # NiFi port
```

#### **Environment Configuration Issues**
```bash
# Verify environment file exists
ls -la .env.local

# Check environment variables are loading
bash scripts/maintain.sh status
```

### 📋 **Environment-Specific Notes**

#### **Local Development (Docker-based)**
- Services run in Docker containers
- Data persists in Docker volumes
- No `sudo` required for most operations
- Use `bash scripts/maintain.sh` commands

#### **Codex Environment (Native services)**
- Services installed directly on system
- Requires `sudo` for service management  
- More production-like setup
- Use `bash scripts/maintain.sh` commands (automatically detects and uses sudo)

### 🎯 **Quick Resolution Checklist**

1. **✅ Check service status**: `bash scripts/maintain.sh status`
2. **✅ View relevant logs**: `bash scripts/maintain.sh logs [service]`
3. **✅ Restart services**: `bash scripts/maintain.sh restart`
4. **✅ Verify environment**: Check `.env.local` file exists
5. **✅ Clean restart** (if needed): `bash scripts/maintain.sh clean && bash scripts/maintain.sh start`

For persistent issues, check the detailed service logs and ensure all dependencies are properly installed.
