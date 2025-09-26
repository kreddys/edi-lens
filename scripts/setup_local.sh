#!/usr/bin/env bash
# ==============================================================================
# EDI LENS - LOCAL DEVELOPMENT SETUP
# ==============================================================================
# Sets up local development environment with Docker containers for
# infrastructure (PostgreSQL, NiFi, NiFi Registry) and local backend
# ==============================================================================

set -euo pipefail

# --- Output helpers -----------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

info() { printf "${BLUE}[INFO]${NC} %s\n" "$1"; }
success() { printf "${GREEN}[SUCCESS]${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; exit 1; }
status() { printf "${CYAN}[STATUS]${NC} %s\n" "$1"; }

# --- Configuration ------------------------------------------------------------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_DIR="$PROJECT_ROOT/docker"
BACKEND_DIR="$PROJECT_ROOT/backend"
ENV_FILE="$PROJECT_ROOT/.env.local"

# --- Utility Functions -------------------------------------------------------
require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        error "Required command '$cmd' is not available. Please install it first."
    fi
}

check_docker() {
    if ! docker info >/dev/null 2>&1; then
        error "Docker is not running or accessible"
    fi
}

check_docker_compose() {
    if command -v docker-compose >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker-compose"
    elif docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        error "Neither 'docker-compose' nor 'docker compose' is available"
    fi
}

wait_for_service() {
    local url="$1"
    local name="$2"
    local max_attempts="${3:-30}"
    local attempt=1

    info "Waiting for $name to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if [[ "$url" == https:* ]]; then
            if curl -kfs "$url" >/dev/null 2>&1; then
                success "$name is ready!"
                return 0
            fi
        else
            if curl -fs "$url" >/dev/null 2>&1; then
                success "$name is ready!"
                return 0
            fi
        fi
        printf "."
        sleep 2
        attempt=$((attempt + 1))
    done
    warn "$name failed to start after $max_attempts attempts"
    return 1
}

# --- Environment Setup -------------------------------------------------------
create_env_file() {
    if [ -f "$ENV_FILE" ]; then
        info "Using existing $ENV_FILE"
        return 0
    fi

    info "Creating local development environment file: $ENV_FILE"
    cat > "$ENV_FILE" <<'EOF_ENV'
# ==============================================================================
# EDI LENS - LOCAL DEVELOPMENT ENVIRONMENT CONFIGURATION
# ==============================================================================
# This environment is used for local development where:
# - Infrastructure runs in Docker containers (DB, NiFi, Registry)
# - Backend runs locally with Poetry
# ==============================================================================

# --- Database Configuration (Docker container) ---
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=edi_lens
POSTGRES_MULTIPLE_DATABASES=edi_lens,nifi_registry,keycloak

# Database URLs for local backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edi_lens

# --- NiFi Registry Configuration (Docker container) ---
NIFI_REGISTRY_WEB_HTTP_HOST=0.0.0.0
NIFI_REGISTRY_WEB_HTTP_PORT=18080
NIFI_REGISTRY_DB_URL=jdbc:postgresql://db:5432/nifi_registry
NIFI_REGISTRY_DB_USER=postgres
NIFI_REGISTRY_DB_PASS=postgres
NIFI_REGISTRY_DB_CLASS=org.postgresql.Driver
NIFI_REGISTRY_DB_DRIVER_CLASS=org.postgresql.Driver
NIFI_REGISTRY_DB_DRIVER_DIRECTORY=/opt/nifi-registry/nifi-registry-current/lib

# --- NiFi Configuration (Docker container) ---
NIFI_WEB_HTTPS_PORT=8443
NIFI_WEB_HTTPS_HOST=0.0.0.0
NIFI_WEB_PROXY_HOST=localhost:8443,nifi:8443
NIFI_USERNAME=admin
NIFI_PASSWORD=adminadmin123
NIFI_SENSITIVE_PROPS_KEY=local_nifi_secret_key_2024_pass!
NIFI_JVM_HEAP_INIT=2g
NIFI_JVM_HEAP_MAX=4g

# --- Service URLs for local backend ---
NIFI_URL=https://localhost:8443
NIFI_REGISTRY_URL=http://localhost:18080
NIFI_VERIFY_SSL=false
REGISTRY_VERIFY_SSL=false

# --- Application Configuration ---
DEBUG=true
EOF_ENV
    chmod 644 "$ENV_FILE" || true
}

load_environment() {
    if [ -f "$ENV_FILE" ]; then
        set -a
        source "$ENV_FILE"
        set +a
        info "Loaded environment from $ENV_FILE"
    else
        error "Environment file not found: $ENV_FILE"
    fi
}

# --- Service Setup Functions -------------------------------------------------
setup_backend_dependencies() {
    info "====================================================================="
    info "🐍 BACKEND DEPENDENCIES SETUP"
    info "====================================================================="

    if [ ! -d "$BACKEND_DIR" ]; then
        warn "Backend directory not found at $BACKEND_DIR - skipping backend setup"
        return 0
    fi

    if [ ! -f "$BACKEND_DIR/pyproject.toml" ]; then
        warn "pyproject.toml not found in backend directory - skipping backend setup"
        return 0
    fi

    # Check if poetry is available
    if ! command -v poetry >/dev/null 2>&1; then
        info "Installing Poetry..."
        curl -sSL https://install.python-poetry.org | python3 -
        export PATH="$HOME/.local/bin:$PATH"
    fi

    cd "$BACKEND_DIR"

    # Check if dependencies are already installed
    if poetry env info --path >/dev/null 2>&1; then
        local venv_path
        venv_path=$(poetry env info --path)
        if [ -d "$venv_path" ] && poetry check >/dev/null 2>&1; then
            success "✓ Backend dependencies already installed and up to date"
            cd "$PROJECT_ROOT"
            return 0
        fi
    fi

    info "Installing backend dependencies with Poetry..."
    poetry install --with dev

    success "✅ Backend dependencies installed successfully"
    cd "$PROJECT_ROOT"
}

setup_docker_infrastructure() {
    info "====================================================================="
    info "🐳 DOCKER INFRASTRUCTURE SETUP"
    info "====================================================================="

    check_docker
    check_docker_compose

    # Check if infrastructure is already running
    if docker ps --format "{{.Names}}" | grep -q "^edi-lens-db$" && \
       docker ps --format "{{.Names}}" | grep -q "^edi-lens-nifi$" && \
       docker ps --format "{{.Names}}" | grep -q "^edi-lens-registry$"; then
        info "Infrastructure containers already running - checking health"

        if wait_for_service "http://localhost:18080/nifi-registry-api/config" "Registry" 10 && \
           wait_for_service "https://localhost:8443/nifi/" "NiFi" 10; then
            success "✓ Infrastructure is already healthy"
            return 0
        else
            info "Infrastructure containers running but not healthy - restarting"
        fi
    fi

    cd "$DOCKER_DIR"

    info "Starting Docker infrastructure services..."
    $DOCKER_COMPOSE up -d

    info "Waiting for services to be ready..."

    # Wait for database
    info "Waiting for PostgreSQL..."
    local attempt=1
    while [ $attempt -le 30 ]; do
        if docker exec edi-lens-db pg_isready -U postgres >/dev/null 2>&1; then
            success "PostgreSQL is ready!"
            break
        fi
        printf "."
        sleep 2
        attempt=$((attempt + 1))
    done

    # Wait for Registry and NiFi
    wait_for_service "http://localhost:18080/nifi-registry-api/config" "NiFi Registry" 60
    wait_for_service "https://localhost:8443/nifi/" "NiFi" 120

    success "✅ Docker infrastructure is ready"
}

# --- Main Setup Function -----------------------------------------------------
local_setup_main() {
    local start_time=$(date +%s)

    info "====================================================================="
    info "🚀 EDI LENS - LOCAL DEVELOPMENT SETUP"
    info "====================================================================="
    info "Setting up local development environment"
    info "Infrastructure: Docker containers"
    info "Backend: Local with Poetry"
    info "Timestamp: $(date)"
    info "====================================================================="

    # Step 1: Prerequisites check
    info "📋 STEP 1/5: Prerequisites check"
    require_cmd docker
    require_cmd curl
    check_docker
    check_docker_compose

    # Step 2: Environment setup
    info "📋 STEP 2/5: Environment setup"
    create_env_file
    load_environment

    # Step 3: Backend dependencies
    info "📋 STEP 3/5: Backend dependencies"
    setup_backend_dependencies

    # Step 4: Docker infrastructure
    info "📋 STEP 4/5: Docker infrastructure"
    setup_docker_infrastructure

    # Step 5: Final verification
    info "📋 STEP 5/5: Final verification"
    verify_setup

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))

    echo ""
    echo "====================================================================="
    success "🎉 LOCAL DEVELOPMENT SETUP COMPLETED"
    echo "====================================================================="
    info "⏱️  Total setup time: ${duration} seconds"
    echo ""
    info "🌐 Service endpoints:"
    info "  PostgreSQL : localhost:5432 (user: postgres/postgres)"
    info "  NiFi       : https://localhost:8443 (user: admin/adminadmin123)"
    info "  Registry   : http://localhost:18080"
    info "  Backend    : Ready for local startup"
    echo ""
    info "🚀 Next steps:"
    info "  Start backend: cd backend && poetry run uvicorn src.main:app --reload"
    info "  Or use:       ./scripts/maintain_local.sh start-backend"
    echo ""
    info "🔧 Maintenance commands:"
    info "  Start all     : ./scripts/maintain_local.sh start"
    info "  Stop all      : ./scripts/maintain_local.sh stop"
    info "  Status        : ./scripts/maintain_local.sh status"
    info "  Start backend : ./scripts/maintain_local.sh start-backend"
    info "  Stop backend  : ./scripts/maintain_local.sh stop-backend"
    echo "====================================================================="
}

verify_setup() {
    info "Verifying local development setup..."

    # Check Docker containers
    local containers=("edi-lens-db" "edi-lens-nifi" "edi-lens-registry")
    for container in "${containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^$container$"; then
            success "✓ $container is running"
        else
            error "✗ $container is not running"
        fi
    done

    # Check service endpoints
    if curl -fs "http://localhost:18080/nifi-registry-api/config" >/dev/null 2>&1; then
        success "✓ Registry API is responding"
    else
        warn "⚠ Registry API is not responding"
    fi

    if curl -kfs "https://localhost:8443/nifi/" >/dev/null 2>&1; then
        success "✓ NiFi UI is responding"
    else
        warn "⚠ NiFi UI is not responding"
    fi

    # Check backend dependencies
    cd "$BACKEND_DIR"
    if poetry env info --path >/dev/null 2>&1; then
        success "✓ Backend dependencies are installed"
    else
        warn "⚠ Backend dependencies may not be installed"
    fi
    cd "$PROJECT_ROOT"

    success "Setup verification complete"
}

# --- Main Execution ----------------------------------------------------------
local_setup_main "$@"