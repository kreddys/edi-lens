# EDI Lens Backend - New Architecture Overview

## Purpose

This document outlines the completely redesigned backend architecture for EDI Lens, focusing on simplicity, maintainability, and clear separation of concerns. The new architecture replaces the complex legacy system with a clean, modular approach.

## Architecture Goals

### 1. **Simplicity First**
- Single deployment path through NiFi Registry
- Clear service boundaries with minimal dependencies
- HTTP-based communication with proper HTTPS for NiFi

### 2. **Maintainability**
- Modular design with small, focused services
- Clear error handling with actionable messages
- Comprehensive testing at all levels

### 3. **Development Experience**
- Fast startup times with Docker Compose
- Easy debugging with structured logging
- Hot reload for development

## Infrastructure Overview

### Services Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │  NiFi Registry  │    │      NiFi       │
│   Database      │    │  (HTTP:18080)   │    │  (HTTPS:8443)   │
│                 │    │                 │    │                 │
│  - User data    │    │  - Templates    │    │  - Workflows    │
│  - Registry DB  │    │  - Versions     │    │  - Processing   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                    ┌─────────────────┐
                    │   Backend API   │
                    │  (HTTP:8000)    │
                    │                 │
                    │  - FastAPI      │
                    │  - Health       │
                    │  - Templates    │
                    └─────────────────┘
```

### Key Design Decisions

1. **NiFi with HTTPS**: NiFi 2.5.0 Docker defaults to HTTPS mode with single-user authentication
2. **Registry via HTTP**: NiFi Registry remains on HTTP for simplicity
3. **Clean Volumes**: No complex volume mounting that interferes with NiFi's authentication setup
4. **Standard Naming**: All containers use `edi-lens-*` prefix (no "minimal" references)

## Backend Architecture

### Core Structure

```
backend/
├── src/
│   ├── core/
│   │   ├── config.py          # Configuration management
│   │   └── database.py        # Database connection
│   ├── clients/
│   │   ├── nifi_client.py     # NiFi API client (HTTPS + auth)
│   │   └── registry_client.py # Registry API client (HTTP)
│   ├── services/              # Business logic services
│   ├── models/               # Data models
│   └── main.py               # FastAPI application
├── tests/
│   ├── unit/                 # Mock-based tests
│   ├── integration/          # Against real services
│   └── e2e/                  # Full workflow tests
└── pyproject.toml            # Dependencies
```

### Service Responsibilities

#### **NiFi Client** (`src/clients/nifi_client.py`)
- HTTPS communication with SSL verification disabled for development
- Basic authentication with admin/adminadmin123
- System diagnostics and health checks
- Parameter context management
- Process group operations

#### **Registry Client** (`src/clients/registry_client.py`)
- HTTP communication with NiFi Registry
- Bucket and flow management
- Template versioning
- Flow content operations

#### **Core Services** (Future)
- **Parameter Manager**: Unified parameter context operations
- **Deployment Service**: Registry-first deployment orchestration
- **Validation Service**: Schema, parameter, and NiFi compatibility validation

### Authentication Strategy

#### NiFi (HTTPS)
- **Mode**: Single-user authentication
- **Credentials**: admin / adminadmin123
- **Transport**: HTTPS with self-signed certificates
- **Health Check**: Web UI endpoint (`/nifi/`) - no auth required

#### NiFi Registry (HTTP)
- **Mode**: No authentication (development)
- **Transport**: HTTP
- **Health Check**: Config endpoint (`/nifi-registry-api/config`)

## Docker Configuration

### Services

| Service | Container Name | Port | Protocol | Health Check |
|---------|---------------|------|----------|--------------|
| Database | `edi-lens-db` | 5432 | PostgreSQL | `pg_isready` |
| Registry | `edi-lens-registry` | 18080 | HTTP | `/nifi-registry-api/config` |
| NiFi | `edi-lens-nifi` | 8443 | HTTPS | `/nifi/` (web UI) |
| Backend | `edi-lens-backend` | 8000 | HTTP | `/health` |

### Environment Variables

```bash
# Database
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=edi_lens

# NiFi (HTTPS with authentication)
NIFI_URL=https://localhost:8443
NIFI_USERNAME=admin
NIFI_PASSWORD=adminadmin123

# NiFi Registry (HTTP)
NIFI_REGISTRY_URL=http://localhost:18080
```

### Volume Strategy

- **Persistent Data**: Database, NiFi repositories, Registry flows
- **No Config Volumes**: Allow NiFi to manage its own configuration files
- **Development Volumes**: Backend source code for hot reload

## Development Workflow

### Getting Started

```bash
# Start all services
cd docker
docker-compose up -d

# Check service health
curl http://localhost:8000/health
curl http://localhost:8000/health/nifi
curl http://localhost:8000/health/registry

# Access NiFi UI
open https://localhost:8443/nifi/
# Login: admin / adminadmin123

# Access Registry UI
open http://localhost:18080/nifi-registry/
```

### Testing Strategy

1. **Unit Tests**: Mock external dependencies, test business logic
2. **Integration Tests**: Test against real Docker services
3. **End-to-End Tests**: Full workflow deployment scenarios

```bash
# Run tests
cd backend
poetry install
poetry run pytest tests/unit/ -v
poetry run pytest tests/integration/ -v
```

## Migration from Legacy

### What Changed

1. **Removed Complexity**:
   - No hybrid deployment engine
   - No complex authentication chains
   - No manual component creation fallbacks

2. **Simplified Flow**:
   ```
   OLD: WorkflowService → HybridDeploymentEngine → NiFiService → Multiple clients
   NEW: WorkflowService → DeploymentService → Direct Registry import
   ```

3. **Clear Error Handling**:
   - Structured error types with actionable messages
   - Single validation pipeline
   - Clear separation between client errors and business logic errors

### Backward Compatibility

- **API Endpoints**: Maintain existing REST API contracts
- **Database Schema**: Reuse existing database structure
- **Configuration**: Environment-based configuration compatible with existing deployment

## Next Steps

### Phase 1: Core Functionality ✅
- [x] Docker infrastructure setup
- [x] Basic client connectivity
- [x] Health check endpoints
- [x] Service naming standardization

### Phase 2: Template Operations (Current)
- [ ] Template upload/download via Registry
- [ ] Flow version management
- [ ] Basic validation pipeline

### Phase 3: Workflow Deployment
- [ ] Parameter context management
- [ ] Registry-to-NiFi deployment
- [ ] Deployment status tracking

### Phase 4: Production Features
- [ ] Comprehensive error handling
- [ ] Performance optimization
- [ ] Security hardening
- [ ] Monitoring integration

## Benefits

### For Developers
- **Fast Setup**: `docker-compose up -d` and everything works
- **Clear Architecture**: Easy to understand and modify
- **Better Testing**: Each component can be tested independently
- **Hot Reload**: Changes reflected immediately during development

### For Operations
- **Reliable Deployment**: Single, well-tested deployment path
- **Better Monitoring**: Clear health checks and structured logging
- **Easier Troubleshooting**: Simplified architecture with clear error messages
- **Reduced Maintenance**: Fewer moving parts and cleaner interfaces

### For Users
- **Faster Deployments**: Streamlined process without complex fallbacks
- **Better Error Messages**: Clear indication of what failed and how to fix it
- **More Reliable Workflows**: Thoroughly tested deployment pipeline

## Conclusion

The new backend architecture represents a fundamental shift from complexity to simplicity. By focusing on core functionality and clear separation of concerns, we've created a maintainable, testable, and reliable system that serves as a solid foundation for future development.

The architecture prioritizes developer experience and operational reliability while maintaining the flexibility needed for EDI workflow management. This foundation will support the continued evolution of the EDI Lens platform.