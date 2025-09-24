# EDI Lens - Agent Development Guide

Welcome to the EDI Lens project! This guide provides essential information for AI agents working on this codebase.

## 🚀 Quick Setup

### Codex Environment Setup
```bash
# Initial setup (installs PostgreSQL, NiFi, NiFi Registry, and backend dependencies)
sudo bash scripts/setup_codex.sh

# Check service status
sudo bash scripts/maintain_codex.sh status

# Start all services
sudo bash scripts/maintain_codex.sh start
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

## 🧪 Testing

All backend tests must be run through the management script to ensure proper environment configuration:

### Unit Tests
```bash
./scripts/backend.sh test unit
```
- Tests isolated components without external dependencies
- Runs in local Poetry virtual environment
- Located in `backend/tests/unit/`

### Integration Tests
```bash
./scripts/backend.sh test integration [local|docker]
```
- **Local mode** (default): Connects to localhost services (NiFi, Registry, PostgreSQL)
- **Docker mode**: Runs tests inside backend container
- Tests API clients and service integrations
- Located in `backend/tests/integration/`

### End-to-End Tests
```bash
./scripts/backend.sh test e2e [local|local-verbose|docker|docker-verbose]
```
- Tests complete workflows from API to NiFi deployment
- Use verbose modes for debugging
- Located in `backend/tests/e2e/`

## 🔧 Development Tools

### Backend Management
```bash
./scripts/backend.sh start     # Start backend + dependencies via Docker
./scripts/backend.sh stop      # Stop all containers
./scripts/backend.sh shell     # Interactive shell in backend container
./scripts/backend.sh lint      # Run linting (Black, Ruff, mypy)
./scripts/backend.sh format    # Auto-format code
./scripts/backend.sh test:watch # Watch mode for unit tests
```

### Service Management
```bash
sudo bash scripts/maintain_codex.sh start      # Start all services
sudo bash scripts/maintain_codex.sh stop       # Stop all services
sudo bash scripts/maintain_codex.sh restart    # Restart all services
sudo bash scripts/maintain_codex.sh status     # Service health summary
sudo bash scripts/maintain_codex.sh detailed   # Detailed system status
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
- `backend/README_ARCHITECTURE.md` - Detailed backend architecture

### Scripts
- `scripts/setup_codex.sh` - Complete environment setup
- `scripts/maintain_codex.sh` - Service management and monitoring
- `scripts/backend.sh` - Backend development and testing

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

- Always run tests through `./scripts/backend.sh` scripts
- Use Codex setup scripts for environment initialization
- Backend dependencies are managed with Poetry
- All services run on localhost with standard ports
- Check service health with maintenance script before testing

## 🆘 Troubleshooting

### Service Issues
```bash
# Check all service status
sudo bash scripts/maintain_codex.sh detailed

# Restart problematic services
sudo bash scripts/maintain_codex.sh restart

# Check logs
ls -la /opt/codex-services/logs/  # or ~/.codex-services/logs/
```

### Backend Issues
```bash
# Check backend container logs
./scripts/backend.sh logs

# Interactive debugging
./scripts/backend.sh shell

# Verify dependencies
cd backend && poetry check
```

### Common Solutions
- **Services not starting**: Run setup script again
- **Tests failing**: Verify services are healthy first
- **Connection errors**: Check `.env.local` configuration
- **Permission errors**: Ensure scripts run with appropriate privileges

This guide should help you navigate the EDI Lens codebase efficiently. For detailed architecture information, refer to `backend/README_ARCHITECTURE.md`.