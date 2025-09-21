# EDI-Lens Codex Cloud Setup

## Complete One-Command Setup

Run this **single command** to set up, start, verify, and test the complete EDI-Lens environment in Codex:

```bash
./scripts/setup_codex.sh
```

This script performs **everything automatically**:

## Current Implementation Status

### 📦 Phase 1: Installation & Configuration - **✅ COMPLETED & VALIDATED**
- ✅ Install all system dependencies (PostgreSQL, Java, etc.) with automatic dependency fixing
- ✅ Initialize PostgreSQL cluster properly for Codex environment
- ✅ Download and configure MinIO (working - bucket creation verified)
- 🔄 Download and configure Keycloak (database connection fixed)
- 🔧 Download and configure SFTPGo, NiFi, NiFi Registry (pending validation)
- ✅ Set up PostgreSQL databases for all services
- 🔧 Install Python backend dependencies (pending validation)
- 🔧 Install Node.js frontend dependencies (pending validation)

### 🚀 Phase 2: Service Startup - **🔧 IN DEVELOPMENT**
- 🔄 Start all infrastructure services automatically
- 🔧 Start backend and frontend applications
- 🔧 Wait for services to stabilize

### 🔍 Phase 3: Health Verification - **🔧 IN DEVELOPMENT**
- 🔧 Verify all services are running and healthy
- 🔧 Check all HTTP endpoints are responding
- 🔧 Validate database connections

### 🌐 Phase 4: Integration Testing - **🔧 IN DEVELOPMENT**
- 🔧 Test API connectivity
- 🔧 Verify database integration
- 🔧 Test Keycloak authentication
- 🔧 Verify MinIO storage access

### 🧪 Phase 5: Comprehensive Testing - **🔧 IN DEVELOPMENT**
- 🔧 Run backend unit tests
- 🔧 Run backend integration tests
- 🔧 Run backend end-to-end tests
- 🔧 Run frontend tests (if configured)

## Recent Validation & Enhancements

### ✅ Completed Validations (September 2025)
- **Dependency Resolution**: Enhanced script with `apt --fix-broken install` to handle package conflicts automatically
- **PostgreSQL Initialization**: Fixed PostgreSQL cluster initialization for Codex Docker environment
- **Environment Setup**: Verified Codex environment (Python 3.12.10, Node.js v22.19.0, Go 1.24.3)
- **MinIO Configuration**: Validated object storage setup with bucket creation
- **Database Creation**: Successfully created PostgreSQL databases for all services (main app, Keycloak, SFTPGo, NiFi Registry)

### 🔍 Issues Identified & Resolved
- **PostgreSQL Startup**: The original script used `service postgresql start` which failed in Codex. Fixed with proper cluster initialization using `initdb` and direct `pg_ctl` commands.
- **Package Dependencies**: System package installation encountered broken dependencies. Added automatic dependency resolution.
- **Keycloak Database Connection**: Keycloak startup was failing due to PostgreSQL not being properly initialized. Resolved by fixing PostgreSQL setup sequence.

### 🔧 Pending Validation Tasks
- Complete Keycloak startup with database connection
- Validate SFTPGo, NiFi, and NiFi Registry setup
- Test complete service integration
- Validate backend and frontend application startup
- Run comprehensive health checks and testing phases

## Post-Setup Management

### Check Service Status
```bash
./scripts/check_services.sh
```

### Restart All Services
```bash
./scripts/restart_services.sh
```

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| **Frontend** | http://localhost:3000 | - |
| **Backend API** | http://localhost:8000 | - |
| **Keycloak** | http://localhost:8180 | admin / admin_codex_2024 |
| **SFTPGo** | http://localhost:8280 | admin / sftpgo_admin_2024 |
| **MinIO Console** | http://localhost:9001 | codex_minio_access / codex_minio_secret_2024 |
| **NiFi** | https://localhost:8443 | admin / nifi_admin_codex_2024 |
| **NiFi Registry** | http://localhost:18081 | - |

## Configuration

All configuration is stored in `.env.codex` file which is automatically created during setup.

## Logs

Service logs are available in `codex-services/logs/` directory.

## Troubleshooting

### Reset Everything
```bash
# Stop all services
pkill -f "minio\|keycloak\|sftpgo\|nifi\|uvicorn\|npm"

# Remove services directory
rm -rf codex-services/

# Re-run setup
./scripts/setup_codex.sh
```

### Check Individual Service
```bash
# Check if service is running
ps aux | grep <service-name>

# Check service logs
tail -f codex-services/logs/<service>.log
```

### Common Issues

**Permission errors:**
```bash
sudo chown -R $USER:$USER codex-services/
```

**Port conflicts:**
Edit `.env.codex` to change service ports, then re-run setup.

**Database connection issues:**
```bash
# Restart PostgreSQL
sudo service postgresql restart
```

This setup provides a complete EDI-Lens environment ready for development and testing in Codex Cloud!