# Environment Configuration Guide

This document explains the environment file structure and usage for the EDI Lens project.

## Environment Files Overview

The project uses three standardized environment files, all containing the same variables but with deployment-specific values:

### 📄 `.env.example` (Template)
- **Purpose**: Master template for all environment configurations
- **Usage**: Copy this file to create environment-specific configurations
- **Values**: Default/example values with detailed comments
- **Version Control**: ✅ Committed to repository

### 🐳 `.env.docker` (Docker Environment)
- **Purpose**: For running the full stack in Docker containers
- **Usage**: Used by `./scripts/backend.sh` and Docker Compose
- **Key Differences**:
  - `DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/edi_lens`
  - `NIFI_URL=https://nifi:8443`
  - `NIFI_REGISTRY_URL=http://nifi-registry:18080`
  - `NIFI_WEB_PROXY_HOST=nifi:8443,localhost:8443`
- **Version Control**: ✅ Committed to repository

### 🏠 `.env.local` (Local/Codex Environment)
- **Purpose**: For local development and Codex host-based services
- **Usage**: Used by backend tests and Codex setup scripts
- **Key Differences**:
  - `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edi_lens`
  - `NIFI_URL=https://localhost:8443`
  - `NIFI_REGISTRY_URL=http://localhost:18080`
  - `NIFI_WEB_PROXY_HOST=localhost:8443`
- **Version Control**: ⚠️ Local file (not committed)

## Variable Categories

### 🗄️ Database Configuration
- **PostgreSQL**: Connection settings for main application database
- **NiFi Registry DB**: Separate database for NiFi Registry metadata
- **Codex Settings**: Special configurations for Codex environment

### 🌊 NiFi Configuration
- **Connection**: URL and authentication for NiFi API
- **Security**: SSL/TLS settings and sensitive properties key
- **Performance**: JVM heap memory allocation
- **Networking**: Proxy hosts for Docker/localhost compatibility

### 📋 NiFi Registry Configuration
- **Connection**: URL and authentication for Registry API
- **Database**: PostgreSQL connection for metadata storage
- **Versions**: NiFi and Registry version specifications

### 🔧 Backend Application
- **Metadata**: Application version and debugging flags
- **Security**: SSL verification settings for development
- **Logging**: Component-specific log level overrides

## Deployment Modes

### 🐳 Docker Mode (`./scripts/backend.sh start`)
```bash
# Uses .env.docker automatically
./scripts/backend.sh start    # Start all services in containers
./scripts/backend.sh health   # Check service health
./scripts/backend.sh logs     # View container logs
```

### 🏠 Host/Codex Mode (`scripts/setup_codex.sh`)
```bash
# Uses .env.local automatically
sudo bash scripts/setup_codex.sh        # Install services on host
sudo bash scripts/maintain_codex.sh     # Manage host services
```

### 🧪 Testing Mode
```bash
# Backend tests automatically use .env.local
./scripts/backend.sh test unit           # Unit tests
./scripts/backend.sh test integration    # Integration tests
./scripts/backend.sh test e2e           # End-to-end tests
```

## Key Variables for Each Mode

| Variable | Docker Value | Local Value | Purpose |
|----------|-------------|-------------|----------|
| `DATABASE_URL` | `@db:5432` | `@localhost:5432` | Database connection |
| `NIFI_URL` | `https://nifi:8443` | `https://localhost:8443` | NiFi API endpoint |
| `NIFI_REGISTRY_URL` | `http://nifi-registry:18080` | `http://localhost:18080` | Registry API endpoint |
| `NIFI_WEB_PROXY_HOST` | `nifi:8443,localhost:8443` | `localhost:8443` | Accepted proxy hosts |

## Creating New Environment Files

1. **Copy the template**:
   ```bash
   cp .env.example .env.custom
   ```

2. **Modify values** for your specific deployment

3. **Update Docker Compose** (if needed):
   ```yaml
   env_file:
     - ../.env.custom
   ```

4. **Update scripts** (if needed):
   ```bash
   ENV_FILE="$PROJECT_ROOT/.env.custom"
   ```

## Troubleshooting

### ❌ SSL/SNI Errors
- **Symptom**: `Invalid SNI` errors in backend logs
- **Solution**: Ensure `NIFI_WEB_PROXY_HOST` includes the correct hostname
- **Docker**: Should include `nifi:8443,localhost:8443`
- **Local**: Should include `localhost:8443`

### ❌ Connection Refused
- **Symptom**: Backend cannot connect to NiFi or Registry
- **Solution**: Check URL variables match your deployment mode
- **Docker**: Use service names (`nifi`, `nifi-registry`)
- **Local**: Use `localhost`

### ❌ Session Closed Errors
- **Symptom**: `RuntimeError: Session is closed` in logs
- **Solution**: This should be resolved with the current session management fixes

## Best Practices

✅ **Always use the correct environment file for your deployment mode**
✅ **Keep all environment files synchronized with the same variables**
✅ **Use descriptive comments for complex configurations**
✅ **Test changes in both Docker and local modes**
✅ **Never commit sensitive production values to version control**

---

For more information, see:
- [Backend Architecture](backend/README_ARCHITECTURE.md)
- [Codex Setup Guide](scripts/setup_codex.sh)
- [Docker Development](scripts/backend.sh)