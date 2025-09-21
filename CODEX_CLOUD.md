# EDI-Lens Codex Cloud Configuration

This guide explains how to set up EDI-Lens in Codex cloud environments with optimal container caching.

## Quick Setup

Your `setup_codex.sh` script is **already optimized** for Codex cloud! No modifications needed.

## Codex Cloud Environment Configuration

### 1. Setup Script
```bash
scripts/setup_codex.sh
```

**What it does:**
- ✅ Installs all system dependencies
- ✅ Sets up PostgreSQL with pgvector and Apache AGE extensions
- ✅ Downloads and configures all services (Keycloak, NiFi, SFTPGo, MinIO)
- ✅ Sets up Python backend with Poetry
- ✅ Sets up Node.js frontend with npm
- ✅ Creates environment configuration
- ✅ Runs comprehensive tests (optional with `--skip-*-tests` flags)

### 2. Maintenance Script (Optional)
Since the setup script handles everything, **no maintenance script is needed**. The setup script is idempotent and can run multiple times safely.

## Container Caching Optimization

### Cache-Friendly Features Already Built-In:
1. **Idempotent Operations** - Script can run multiple times safely
2. **Download Caching** - Downloads are skipped if files exist
3. **Service State Checking** - Services aren't reinstalled if already present
4. **Environment Persistence** - Environment variables persist across sessions
5. **Comprehensive Logging** - All operations logged for debugging

### Automatic Cache Invalidation Triggers:
The cache will automatically invalidate when you change:
- `scripts/setup_codex.sh` (setup script)
- Environment variables in Codex settings
- Secrets in Codex settings

## Codex Environment Settings

### Required Environment Variables:
```bash
# No environment variables required!
# The script creates .env.codex with all needed configuration
```

### Optional Optimization Variables:
```bash
# Skip tests for faster setup (optional)
SKIP_BACKEND_TESTS=false
SKIP_FRONTEND_TESTS=false

# Service versions (optional - defaults provided)
KEYCLOAK_VERSION=25.0.2
NIFI_VERSION=2.5.0
NIFI_REGISTRY_VERSION=2.0.0
SFTPGO_VERSION=2.6.6
```

### Internet Access Configuration:
- **Setup Phase**: Full internet access needed for downloads
- **Agent Phase**: Limited internet access sufficient (API calls only)

## Usage Options

### Standard Setup (Recommended)
```bash
scripts/setup_codex.sh
```
- Installs everything and runs all tests
- Takes 10-15 minutes on first run
- Cached container starts in ~2 minutes

### Fast Setup (Skip Tests)
```bash
scripts/setup_codex.sh --skip-all-tests
```
- Installs everything but skips test execution
- Takes 8-12 minutes on first run
- Cached container starts in ~1 minute

### Selective Test Skipping
```bash
# Skip only frontend tests (backend tests still run)
scripts/setup_codex.sh --skip-frontend-tests

# Skip only backend tests (frontend tests still run)
scripts/setup_codex.sh --skip-backend-tests
```

## Service URLs (After Setup)

| Service | URL | Credentials |
|---------|-----|-------------|
| Frontend | http://localhost:3000 | N/A |
| Backend API | http://localhost:8000 | N/A |
| API Documentation | http://localhost:8000/docs | N/A |
| Keycloak Admin | http://localhost:8180 | admin/admin_codex_2024 |
| SFTPGo Admin | http://localhost:8280 | admin/sftpgo_admin_2024 |
| MinIO Console | http://localhost:9001 | codex_minio_access/codex_minio_secret_2024 |
| NiFi | https://localhost:8443 | admin/nifi_admin_codex_2024 |
| NiFi Registry | http://localhost:18080 | N/A |

## Container Caching Behavior

### First Run (Cold Cache):
1. Downloads and installs all dependencies
2. Configures all services
3. Runs tests (if not skipped)
4. **Takes 10-15 minutes**
5. Container state cached for 12 hours

### Subsequent Runs (Warm Cache):
1. Loads cached container with everything pre-installed
2. Checks out your specific branch/commit
3. Starts all services (they're already configured)
4. **Takes 2-3 minutes**

### Cache Sharing:
- Cached containers are shared across team members
- Cache invalidation affects all users
- Manual cache reset available in Codex settings

## Troubleshooting

### Cache Issues:
- Use "Reset cache" button in Codex environment settings
- Check if recent changes to setup script triggered invalidation

### Service Startup Issues:
- Check logs in `codex-services/logs/` directory
- Services may take 1-2 minutes to fully start
- Use `scripts/setup_codex.sh --check-services` to verify status

### Test Failures:
- Use `--skip-*-tests` flags to bypass problematic tests
- Tests are optional for basic functionality
- Frontend tests may have occasional flakiness

## Performance Tips

1. **Use test skipping** for faster iteration during development
2. **Avoid cache invalidation** by not modifying setup scripts frequently
3. **Let services warm up** - allow 2-3 minutes for all services to start
4. **Check service status** with built-in health checks

## Example Codex Cloud Task

```bash
# Your setup_codex.sh automatically handles everything!
# No additional configuration needed

# The agent can then:
# - Run backend tests: cd backend && poetry run pytest
# - Run frontend tests: cd frontend && npm test
# - Start development: Services are already running
# - Make code changes: Full environment is ready
```

Your current `setup_codex.sh` is **production-ready** for Codex cloud! 🚀