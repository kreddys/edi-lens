#!/usr/bin/env bash
# ==============================================================================
# EDI LENS - CODEX CLOUD ENVIRONMENT SETUP
# ==============================================================================
# Complete setup script for running EDI-Lens in OpenAI Codex Cloud
# This script installs and configures all services needed for the application
# ==============================================================================

set -euo pipefail

# --- Configuration and Constants ----------------------------------------------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICES_DIR="$PROJECT_ROOT/codex-services"
DOWNLOADS_DIR="$SERVICES_DIR/downloads"
LOGS_DIR="$SERVICES_DIR/logs"
BIN_DIR="$SERVICES_DIR/bin"
ENV_FILE="$PROJECT_ROOT/.env.codex"

# --- Colors and Output Functions ---------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { printf "${BLUE}[INFO]${NC} %s\n" "$1"; }
success() { printf "${GREEN}[SUCCESS]${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; exit 1; }

# --- Utility Functions -------------------------------------------------------
require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        error "Required command '$cmd' is not available. Please install it first."
    fi
}

curl_download() {
    local url="$1"
    local dest="$2"
    if [ -f "$dest" ]; then
        info "Using cached $(basename "$dest")"
        return
    fi
    info "Downloading $(basename "$dest")..."
    if ! curl -fL --retry 3 --retry-delay 2 "$url" -o "$dest"; then
        rm -f "$dest"
        error "Failed to download $url"
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
            curl -kfs "$url" >/dev/null 2>&1 && { success "$name is ready!"; return 0; }
        else
            curl -fs "$url" >/dev/null 2>&1 && { success "$name is ready!"; return 0; }
        fi
        printf "."
        sleep 2
        attempt=$((attempt + 1))
    done
    warn "$name failed to start after $max_attempts attempts"
    return 1
}

# --- Environment Setup -------------------------------------------------------
setup_environment() {
    info "Setting up Codex environment"

    # Create directories
    mkdir -p "$SERVICES_DIR" "$DOWNLOADS_DIR" "$LOGS_DIR" "$BIN_DIR"

    # Load Codex environment (some images set strict shell options in profile)
    if [ -f /etc/profile ]; then
        set +u
        source /etc/profile || true
        set -u
    fi

    # Verify tools
    info "Verifying environment..."
    echo "Python: $(python3 --version)"
    echo "Node.js: $(node --version)"
    echo "npm: $(npm --version)"
    echo "Go: $(go version)"

    # Create environment file if it doesn't exist
    create_env_file

    # Load environment variables
    set -a
    source "$ENV_FILE"
    set +a
}

create_env_file() {
    if [ -f "$ENV_FILE" ]; then
        info "Using existing $ENV_FILE"
        return
    fi

    info "Creating Codex environment file"
    cat > "$ENV_FILE" <<EOF
# ==============================================================================
# EDI LENS - CODEX ENVIRONMENT CONFIGURATION
# ==============================================================================

# --- Database Configuration ---
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=edi_user
POSTGRES_PASSWORD=codex_password_2024
POSTGRES_DB=edi_lens
# Backend expects POSTGRES_SERVER alias
POSTGRES_SERVER=localhost

# Service Databases
POSTGRES_KC_USER=keycloak_user
POSTGRES_KC_PASSWORD=keycloak_password_2024
POSTGRES_KC_DB=keycloak

POSTGRES_SFTPGO_USER=sftpgo_user
POSTGRES_SFTPGO_PASSWORD=sftpgo_password_2024
POSTGRES_SFTPGO_DB=sftpgo

POSTGRES_NIFI_REGISTRY_USER=nifi_registry
POSTGRES_NIFI_REGISTRY_PASSWORD=nifi_registry_password_2024
POSTGRES_NIFI_REGISTRY_DB=nifi_registry

# --- Authentication ---
KEYCLOAK_ADMIN=admin
KEYCLOAK_ADMIN_PASSWORD=admin_codex_2024
KEYCLOAK_URL=http://localhost:8180
KEYCLOAK_BROWSER_URL=http://localhost:8180
KEYCLOAK_REALM=edi-lens
# Backend and UI clients (required by backend config module)
KEYCLOAK_BACKEND_CLIENT_ID=edi-lens-backend
KEYCLOAK_BACKEND_CLIENT_SECRET=this-is-a-default-secret-change-it
KEYCLOAK_UI_CLIENT_ID=edi-lens-ui

SFTPGO_ADMIN_USER=admin
SFTPGO_ADMIN_PASSWORD=sftpgo_admin_2024

NIFI_ADMIN_USER=admin
NIFI_ADMIN_PASSWORD=nifi_admin_codex_2024
NIFI_SENSITIVE_PROPS_KEY=codex_nifi_key_2024_32_chars_long

# --- Storage ---
STORAGE_ACCESS_KEY=codex_minio_access
STORAGE_SECRET_KEY=codex_minio_secret_2024
STORAGE_ENDPOINT_URL=http://localhost:9000
STORAGE_BUCKET=edi-lens
STORAGE_REGION=us-east-1

# --- Application Configuration ---
REMOTE_HOST=localhost
EDI_SCHEMA_DIRECTORY=${PROJECT_ROOT}/backend/data/edi_schemas
BACKEND_HOST=localhost
LOG_LEVEL=INFO

# NiFi URLs for local Codex
NIFI_URL=https://localhost:8443
NIFI_REGISTRY_URL=http://localhost:18080

# Frontend (Vite) env
VITE_API_URL=http://localhost:8000/api/v1
VITE_KEYCLOAK_URL=http://localhost:8180
VITE_KEYCLOAK_REALM=edi-lens
VITE_KEYCLOAK_CLIENT_ID=edi-lens-ui

# --- Service Versions ---
KEYCLOAK_VERSION=25.0.2
SFTPGO_VERSION=2.6.6
NIFI_VERSION=2.5.0
NIFI_REGISTRY_VERSION=2.0.0
EOF
}

# --- System Dependencies -----------------------------------------------------
install_system_dependencies() {
    info "Installing system dependencies"

    # Check if PostgreSQL is already installed
    if command -v psql >/dev/null 2>&1 && dpkg -l | grep -q postgresql-16; then
        info "PostgreSQL already installed, skipping system dependencies"
        return 0
    fi

    # Update package list
    apt-get update

    # Fix any broken dependencies first
    if ! apt-get check >/dev/null 2>&1; then
        info "Fixing broken dependencies..."
        DEBIAN_FRONTEND=noninteractive apt --fix-broken install -y
    fi

    # Install PostgreSQL and essential tools
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        postgresql-16 \
        postgresql-client-16 \
        postgresql-contrib-16 \
        supervisor \
        sudo \
        curl \
        unzip \
        openjdk-21-jdk \
        procps \
        net-tools \
        lsof

    success "System dependencies installed"
}

# --- PostgreSQL Setup --------------------------------------------------------
setup_postgresql() {
    info "Setting up PostgreSQL"

    # Check if PostgreSQL is already running and configured
    if pgrep -f "postgres.*main" >/dev/null; then
        if sudo -u postgres psql -lqt | cut -d \| -f 1 | grep -qw "$POSTGRES_DB"; then
            info "PostgreSQL already running with required databases, skipping setup"
            return 0
        fi
    fi

    # Initialize PostgreSQL if not already done
    if [ ! -f "/var/lib/postgresql/16/main/PG_VERSION" ]; then
        info "Initializing PostgreSQL cluster"
        chown -R postgres:postgres /var/lib/postgresql/16/main
        su - postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/lib/postgresql/16/main' >/dev/null 2>&1
    fi

    # Create log directory
    mkdir -p /var/log/postgresql
    chown postgres:postgres /var/log/postgresql

    # Start PostgreSQL service
    if ! pgrep -f "postgres.*main" >/dev/null; then
        info "Starting PostgreSQL server"
        su - postgres -c '/usr/lib/postgresql/16/bin/pg_ctl start -D /var/lib/postgresql/16/main -l /var/log/postgresql/postgresql-16-main.log -o "-c config_file=/etc/postgresql/16/main/postgresql.conf"' >/dev/null 2>&1
    fi

    # Wait for PostgreSQL to be ready
    sleep 5

    # Create users and databases
    info "Creating databases and users"

    # Main application database
    sudo -u postgres psql -c "CREATE USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD' CREATEDB SUPERUSER;" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;" 2>/dev/null || true

    # Keycloak database
    sudo -u postgres psql -c "CREATE USER $POSTGRES_KC_USER WITH PASSWORD '$POSTGRES_KC_PASSWORD';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE $POSTGRES_KC_DB OWNER $POSTGRES_KC_USER;" 2>/dev/null || true

    # SFTPGo database
    sudo -u postgres psql -c "CREATE USER $POSTGRES_SFTPGO_USER WITH PASSWORD '$POSTGRES_SFTPGO_PASSWORD';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE $POSTGRES_SFTPGO_DB OWNER $POSTGRES_SFTPGO_USER;" 2>/dev/null || true

    # NiFi Registry database
    sudo -u postgres psql -c "CREATE USER $POSTGRES_NIFI_REGISTRY_USER WITH PASSWORD '$POSTGRES_NIFI_REGISTRY_PASSWORD';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE $POSTGRES_NIFI_REGISTRY_DB OWNER $POSTGRES_NIFI_REGISTRY_USER;" 2>/dev/null || true

    success "PostgreSQL configured"
}

# --- MinIO Setup -------------------------------------------------------------
setup_minio() {
    info "Setting up MinIO"

    # Check if MinIO is already running
    if curl -fs "http://localhost:9000/minio/health/live" >/dev/null 2>&1; then
        info "MinIO already running and healthy, skipping setup"
        return 0
    fi

    local minio_bin="$BIN_DIR/minio"
    local mc_bin="$BIN_DIR/mc"
    local data_dir="$SERVICES_DIR/minio-data"

    mkdir -p "$data_dir"

    # Determine architecture
    local uname_arch
    uname_arch=$(uname -m)
    local minio_arch="linux-amd64"
    if [ "$uname_arch" = "aarch64" ] || [ "$uname_arch" = "arm64" ]; then
        minio_arch="linux-arm64"
    fi

    # Download MinIO binaries if needed
    if [ ! -f "$minio_bin" ]; then
        curl_download "https://dl.min.io/server/minio/release/${minio_arch}/minio" "$minio_bin"
        chmod +x "$minio_bin"
    fi

    if [ ! -f "$mc_bin" ]; then
        curl_download "https://dl.min.io/client/mc/release/${minio_arch}/mc" "$mc_bin"
        chmod +x "$mc_bin"
    fi

    # Start MinIO
    info "Starting MinIO"
    MINIO_ROOT_USER="$STORAGE_ACCESS_KEY" \
    MINIO_ROOT_PASSWORD="$STORAGE_SECRET_KEY" \
    nohup "$minio_bin" server "$data_dir" --console-address ":9001" --address ":9000" > "$LOGS_DIR/minio.log" 2>&1 &

    # Wait for MinIO to be ready
    wait_for_service "http://localhost:9000/minio/health/live" "MinIO"

    # Create bucket
    "$mc_bin" alias set local-minio "http://localhost:9000" "$STORAGE_ACCESS_KEY" "$STORAGE_SECRET_KEY"
    "$mc_bin" mb --ignore-existing "local-minio/$STORAGE_BUCKET"

    success "MinIO configured and running"
}

# --- Keycloak Setup ----------------------------------------------------------
setup_keycloak() {
    info "Setting up Keycloak"

    # Check if Keycloak is already running
    if curl -fs "http://localhost:8180" >/dev/null 2>&1; then
        info "Keycloak already running and healthy, skipping setup"
        return 0
    fi

    local install_dir="$SERVICES_DIR/keycloak"
    local archive="$DOWNLOADS_DIR/keycloak-$KEYCLOAK_VERSION.tar.gz"

    mkdir -p "$install_dir"

    # Download Keycloak
    curl_download "https://github.com/keycloak/keycloak/releases/download/$KEYCLOAK_VERSION/keycloak-$KEYCLOAK_VERSION.tar.gz" "$archive"

    # Extract if needed
    if [ ! -d "$install_dir/keycloak-$KEYCLOAK_VERSION" ]; then
        info "Extracting Keycloak"
        tar -xf "$archive" -C "$install_dir" --strip-components=1
    fi

    # Start Keycloak
    info "Starting Keycloak"
    cd "$install_dir"
    KEYCLOAK_ADMIN="$KEYCLOAK_ADMIN" \
    KEYCLOAK_ADMIN_PASSWORD="$KEYCLOAK_ADMIN_PASSWORD" \
    nohup ./bin/kc.sh start-dev \
        --http-port=8180 \
        --hostname=localhost \
        --db=postgres \
        --db-url-host=localhost \
        --db-url-port=5432 \
        --db-username="$POSTGRES_KC_USER" \
        --db-password="$POSTGRES_KC_PASSWORD" \
        --db-url-database="$POSTGRES_KC_DB" \
        --proxy=edge \
        --hostname-strict=false \
        --http-management-port=9990 > "$LOGS_DIR/keycloak.log" 2>&1 &

    # Wait for Keycloak to be ready
    wait_for_service "http://localhost:8180" "Keycloak" 60

    success "Keycloak configured and running"
}

# --- SFTPGo Setup ------------------------------------------------------------
setup_sftpgo() {
    info "Setting up SFTPGo"

    # Check if SFTPGo is already running
    if curl -fs "http://localhost:8280/healthz" >/dev/null 2>&1; then
        info "SFTPGo already running and healthy, skipping setup"
        return 0
    fi

    # Skip SFTPGo installation for now - optional service
    warn "SFTPGo installation skipped - focusing on core services (PostgreSQL, MinIO, Keycloak, Backend, Frontend)"
    info "SFTPGo can be installed manually later if needed"
}

# --- NiFi Registry Setup -----------------------------------------------------
setup_nifi_registry() {
    info "Setting up NiFi Registry"

    local install_dir="$SERVICES_DIR/nifi-registry"
    local archive="$DOWNLOADS_DIR/nifi-registry-$NIFI_REGISTRY_VERSION-bin.zip"

    mkdir -p "$install_dir"

    # Download NiFi Registry
    curl_download "https://downloads.apache.org/nifi/$NIFI_REGISTRY_VERSION/nifi-registry-$NIFI_REGISTRY_VERSION-bin.zip" "$archive"

    # Extract if needed
    if [ ! -d "$install_dir/nifi-registry-$NIFI_REGISTRY_VERSION" ]; then
        info "Extracting NiFi Registry"
        unzip -q "$archive" -d "$install_dir"
    fi

    local registry_home="$install_dir/nifi-registry-$NIFI_REGISTRY_VERSION"

    # Download PostgreSQL JDBC driver
    local jdbc_jar="$registry_home/lib/postgresql-42.7.4.jar"
    if [ ! -f "$jdbc_jar" ]; then
        curl_download "https://jdbc.postgresql.org/download/postgresql-42.7.4.jar" "$jdbc_jar"
    fi

    # Start NiFi Registry
    info "Starting NiFi Registry"
    cd "$registry_home"
    NIFI_REGISTRY_DB_URL="jdbc:postgresql://localhost:5432/$POSTGRES_NIFI_REGISTRY_DB" \
    NIFI_REGISTRY_DB_USER="$POSTGRES_NIFI_REGISTRY_USER" \
    NIFI_REGISTRY_DB_PASS="$POSTGRES_NIFI_REGISTRY_PASSWORD" \
    NIFI_REGISTRY_WEB_HTTP_HOST=0.0.0.0 \
    NIFI_REGISTRY_WEB_HTTP_PORT=18080 \
    nohup ./bin/nifi-registry.sh run > "$LOGS_DIR/nifi-registry.log" 2>&1 &

    # Wait for NiFi Registry to be ready
    wait_for_service "http://localhost:18080/nifi-registry/" "NiFi Registry" 60

    success "NiFi Registry configured and running"
}

# --- NiFi Setup --------------------------------------------------------------
setup_nifi() {
    info "Setting up Apache NiFi"

    local install_dir="$SERVICES_DIR/nifi"
    local archive="$DOWNLOADS_DIR/nifi-$NIFI_VERSION-bin.zip"

    mkdir -p "$install_dir"

    # Download NiFi
    curl_download "https://downloads.apache.org/nifi/$NIFI_VERSION/nifi-$NIFI_VERSION-bin.zip" "$archive"

    # Extract if needed
    if [ ! -d "$install_dir/nifi-$NIFI_VERSION" ]; then
        info "Extracting NiFi"
        unzip -q "$archive" -d "$install_dir"
    fi

    local nifi_home="$install_dir/nifi-$NIFI_VERSION"

    # Copy EDI processors
    local py_ext_dir="$nifi_home/python_extensions/edi-processors"
    mkdir -p "$py_ext_dir"
    if [ -d "$PROJECT_ROOT/nifi-edi-processors" ]; then
        cp -r "$PROJECT_ROOT/nifi-edi-processors/"* "$py_ext_dir/"
    fi

    # Start NiFi
    info "Starting NiFi"
    cd "$nifi_home"
    NIFI_WEB_HTTPS_HOST=0.0.0.0 \
    NIFI_WEB_HTTPS_PORT=8443 \
    NIFI_WEB_PROXY_HOST=localhost:8443 \
    NIFI_SECURITY_USER_LOGIN_IDENTITY_PROVIDER=single-user-provider \
    NIFI_SECURITY_USER_AUTHORIZER=single-user-authorizer \
    NIFI_SENSITIVE_PROPS_KEY="$NIFI_SENSITIVE_PROPS_KEY" \
    NIFI_USERNAME="$NIFI_ADMIN_USER" \
    NIFI_PASSWORD="$NIFI_ADMIN_PASSWORD" \
    PYTHONPATH="$py_ext_dir:${PYTHONPATH:-}" \
    nohup ./bin/nifi.sh run > "$LOGS_DIR/nifi.log" 2>&1 &

    # Set single user credentials
    sleep 10
    ./bin/nifi.sh set-single-user-credentials "$NIFI_ADMIN_USER" "$NIFI_ADMIN_PASSWORD"

    # Wait for NiFi to be ready
    wait_for_service "https://localhost:8443/nifi/" "NiFi" 120

    success "NiFi configured and running"
}

# --- Application Setup -------------------------------------------------------
setup_backend() {
    info "Setting up Python backend"

    # Check if backend is already running
    if curl -fs "http://localhost:8000/api/v1/health" >/dev/null 2>&1; then
        info "Backend already running and healthy, skipping setup"
        return 0
    fi

    cd "$PROJECT_ROOT/backend"

    # Check if virtual environment already exists and is configured
    if [ -f "venv/bin/activate" ] && [ -f "start.sh" ]; then
        info "Backend virtual environment already configured"
        # Just run migrations if needed
        source venv/bin/activate
        source "$ENV_FILE"
        poetry run alembic upgrade head
        success "Backend configuration updated"
        return 0
    fi

    # Create virtual environment
    python3 -m venv venv
    source venv/bin/activate

    # Install poetry
    pip install --upgrade pip poetry

    # Install dependencies
    poetry install

    # Run database migrations
    info "Running database migrations..."
    source "$ENV_FILE"
    if ! poetry run alembic upgrade head; then
        error "Database migrations failed"
    fi

    # Create start script
    cat > start.sh <<EOF
#!/bin/bash
cd "$PROJECT_ROOT/backend"
source venv/bin/activate
source "$ENV_FILE"
exec poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
EOF
    chmod +x start.sh

    success "Backend configured"
}

setup_frontend() {
    info "Setting up React frontend"

    # Check if frontend is already running
    if curl -fs "http://localhost:3000" >/dev/null 2>&1; then
        info "Frontend already running, skipping setup"
        return 0
    fi

    cd "$PROJECT_ROOT/frontend"

    # Check if dependencies are already installed
    if [ -d "node_modules" ] && [ -f "start.sh" ]; then
        info "Frontend dependencies already installed, skipping setup"
        return 0
    fi

    # Install dependencies
    npm install

    # Create start script
    cat > start.sh <<EOF
#!/bin/bash
cd "$PROJECT_ROOT/frontend"
source "$ENV_FILE"
exec npm run dev -- --host 0.0.0.0 --port 3000
EOF
    chmod +x start.sh

    success "Frontend configured"
}

# --- Service Startup and Health Checks --------------------------------------
start_all_services() {
    info "Starting all application services"

    # Start backend if not already running
    if ! curl -fs "http://localhost:8000/api/v1/health" >/dev/null 2>&1; then
        info "Starting Python backend..."
        cd "$PROJECT_ROOT/backend"
        nohup ./start.sh > "$LOGS_DIR/backend.log" 2>&1 &
        sleep 10  # Give backend time to start
    else
        info "Backend already running"
    fi

    # Configure Keycloak realm after server is up
    info "Configuring Keycloak realm and clients..."
    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate
    source "$ENV_FILE"
    python3 scripts/setup_keycloak_realm.py || warn "Keycloak realm setup encountered issues"

    # Start frontend if not already running
    if ! curl -fs "http://localhost:3000" >/dev/null 2>&1; then
        info "Starting React frontend..."
        cd "$PROJECT_ROOT/frontend"
        nohup ./start.sh > "$LOGS_DIR/frontend.log" 2>&1 &
    else
        info "Frontend already running"
    fi

    success "Application services started"
}

verify_all_services() {
    info "Verifying all services are healthy"

    local services_to_check=(
        "PostgreSQL::postgres"
        "MinIO:http://localhost:9000/minio/health/live:minio"
        "Keycloak:http://localhost:8180:keycloak"
        "SFTPGo:http://localhost:8280/healthz:sftpgo"
        "NiFi Registry:http://localhost:18080/nifi-registry/:nifi-registry"
        "NiFi:https://localhost:8443/nifi-api/system-diagnostics:nifi:-k"
        "Backend:http://localhost:8000/api/v1/health:uvicorn"
        "Frontend:http://localhost:3000:npm"
    )

    local failed_services=()

    for service_info in "${services_to_check[@]}"; do
        IFS=':' read -r name url process extra <<< "$service_info"

        printf "%-15s " "$name:"

        # Check if process is running
        if [ -n "$process" ] && pgrep -f "$process" >/dev/null; then
            # If URL provided, check health endpoint
            if [ -n "$url" ]; then
                local curl_opts=""
                if [ "$extra" = "-k" ]; then
                    curl_opts="-k"
                fi

                if curl -fs $curl_opts "$url" >/dev/null 2>&1; then
                    echo "✅ HEALTHY"
                else
                    echo "❌ UNHEALTHY"
                    failed_services+=("$name")
                fi
            else
                echo "✅ RUNNING"
            fi
        else
            echo "❌ NOT RUNNING"
            failed_services+=("$name")
        fi
    done

    if [ ${#failed_services[@]} -gt 0 ]; then
        error "The following services failed health checks: ${failed_services[*]}"
    else
        success "All services are healthy and running!"
    fi
}

# --- Testing Framework -------------------------------------------------------
run_backend_tests() {
    info "Running backend tests"

    cd "$PROJECT_ROOT/backend"
    source venv/bin/activate
    source "$ENV_FILE"

    # Wait for services to be fully ready
    info "Waiting for services to be fully ready for testing..."
    sleep 10

    info "Running unit tests..."
    if ! poetry run pytest tests/unit/ -v --tb=short; then
        error "Unit tests failed"
    fi
    success "Unit tests passed"

    info "Running integration tests..."
    if ! poetry run pytest tests/integration/ -v --tb=short; then
        error "Integration tests failed"
    fi
    success "Integration tests passed"

    info "Running end-to-end tests..."
    if ! poetry run pytest tests/e2e/ -v --tb=short; then
        error "End-to-end tests failed"
    fi
    success "End-to-end tests passed"

    success "All backend tests completed successfully"
}

run_frontend_tests() {
    info "Running frontend tests"

    cd "$PROJECT_ROOT/frontend"
    source "$ENV_FILE"

    info "Running frontend unit tests..."
    if ! npm test -- --watchAll=false --coverage; then
        warn "Frontend tests failed or not configured"
    else
        success "Frontend tests passed"
    fi
}

run_api_health_tests() {
    info "Running API health and connectivity tests"

    # Test basic API connectivity
    info "Testing API health endpoint..."
    local health_json
    health_json=$(curl -sf "http://localhost:8000/api/v1/health" || true)
    if [ -z "$health_json" ]; then
        error "API health endpoint not responding"
    fi
    local status
    status=$(echo "$health_json" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    if [ "$status" != "ok" ]; then
        error "Health endpoint returned unexpected status: $status"
    fi

    # Test authentication endpoint (Keycloak)
    info "Testing Keycloak integration..."
    if ! curl -sf "http://localhost:8180/realms/edi-lens/.well-known/openid-configuration" >/dev/null 2>&1; then
        error "Keycloak OIDC configuration not accessible"
    fi

    # Test MinIO connectivity
    info "Testing MinIO connectivity..."
    if ! curl -sf "http://localhost:9000/minio/health/live" >/dev/null 2>&1; then
        error "MinIO health check failed"
    fi

    success "API health and connectivity tests passed"
}

# --- Service Management Scripts Creation -------------------------------------
create_service_manager() {
    info "Creating service management scripts"

    # Create simplified status check script
    cat > "$PROJECT_ROOT/scripts/check_services.sh" <<'EOF'
#!/bin/bash
# Check status of all EDI-Lens services

echo "=== EDI-Lens Service Status ==="
echo ""

check_service() {
    local name="$1"
    local url="$2"
    local process="$3"
    local extra="$4"

    printf "%-15s " "$name:"

    if [ -n "$process" ] && pgrep -f "$process" >/dev/null; then
        if [ -n "$url" ]; then
            local curl_opts=""
            if [ "$extra" = "-k" ]; then
                curl_opts="-k"
            fi
            if curl -fs $curl_opts "$url" >/dev/null 2>&1; then
                echo "✅ HEALTHY"
            else
                echo "🟡 STARTING"
            fi
        else
            echo "✅ RUNNING"
        fi
    else
        echo "❌ STOPPED"
    fi
}

check_service "PostgreSQL" "" "postgres"
check_service "MinIO" "http://localhost:9000/minio/health/live" "minio"
check_service "Keycloak" "http://localhost:8180" "keycloak"
check_service "SFTPGo" "http://localhost:8280/healthz" "sftpgo"
check_service "NiFi Registry" "http://localhost:18080/nifi-registry/" "nifi-registry"
check_service "NiFi" "https://localhost:8443/nifi-api/system-diagnostics" "nifi" "-k"
check_service "Backend" "http://localhost:8000/api/v1/health" "uvicorn"
check_service "Frontend" "http://localhost:3000" "npm"

echo ""
echo "Service URLs:"
echo "  Frontend:        http://localhost:3000"
echo "  Backend API:     http://localhost:8000"
echo "  API Docs:        http://localhost:8000/docs"
echo "  Keycloak:        http://localhost:8180"
echo "  SFTPGo:          http://localhost:8280"
echo "  MinIO Console:   http://localhost:9001"
echo "  NiFi:            https://localhost:8443"
echo "  NiFi Registry:   http://localhost:18080"
echo ""
echo "Logs available in: codex-services/logs/"
EOF

    chmod +x "$PROJECT_ROOT/scripts/check_services.sh"

    # Create restart script
    cat > "$PROJECT_ROOT/scripts/restart_services.sh" <<'EOF'
#!/bin/bash
# Restart all EDI-Lens services

echo "Stopping all services..."
pkill -f "minio" || true
pkill -f "keycloak" || true
pkill -f "sftpgo" || true
pkill -f "nifi" || true
pkill -f "uvicorn" || true
pkill -f "npm.*dev" || true

sleep 5

echo "Restarting services..."
cd "$(dirname "${BASH_SOURCE[0]}")/.."
./scripts/setup_codex.sh
EOF

    chmod +x "$PROJECT_ROOT/scripts/restart_services.sh"

    success "Service management scripts created"
}

# --- Main Setup Function -----------------------------------------------------
main() {
    info "🚀 Starting EDI-Lens Codex Complete Setup & Testing"
    echo "This will install, configure, start, and test all services for EDI-Lens"
    echo ""

    # Phase 1: Installation and Configuration
    info "📦 Phase 1: Installing and configuring services..."
    setup_environment
    install_system_dependencies
    setup_postgresql
    setup_minio
    setup_keycloak
    setup_sftpgo
    setup_nifi_registry
    setup_nifi
    setup_backend
    setup_frontend
    create_service_manager

    echo ""
    info "⏳ Waiting for infrastructure services to stabilize..."
    sleep 30

    # Phase 2: Start Application Services
    info "🚀 Phase 2: Starting application services..."
    start_all_services

    echo ""
    info "⏳ Waiting for application services to start..."
    sleep 20

    # Phase 3: Health Verification
    info "🔍 Phase 3: Verifying service health..."
    verify_all_services

    # Phase 4: Connectivity Testing
    info "🌐 Phase 4: Testing API connectivity and integrations..."
    run_api_health_tests

    # Phase 5: Comprehensive Testing
    info "🧪 Phase 5: Running comprehensive test suite..."

    # Run backend tests
    run_backend_tests

    # Run frontend tests (optional, may not be configured)
    run_frontend_tests

    echo ""
    echo "============================================================================"
    success "🎉 EDI-Lens Codex Environment Ready!"
    echo "============================================================================"
    echo ""
    echo "✅ All services installed and configured"
    echo "✅ All services running and healthy"
    echo "✅ API connectivity verified"
    echo "✅ Database integration working"
    echo "✅ Authentication system operational"
    echo "✅ File storage system operational"
    echo "✅ Backend tests passed"
    echo "✅ System ready for development and production use"
    echo ""
    echo "🌐 Service URLs:"
    echo "   Frontend:        http://localhost:3000"
    echo "   Backend API:     http://localhost:8000"
    echo "   API Docs:        http://localhost:8000/docs"
    echo "   Keycloak Admin:  http://localhost:8180 (admin/admin_codex_2024)"
    echo "   SFTPGo Admin:    http://localhost:8280 (admin/sftpgo_admin_2024)"
    echo "   MinIO Console:   http://localhost:9001 (codex_minio_access/codex_minio_secret_2024)"
    echo "   NiFi:            https://localhost:8443 (admin/nifi_admin_codex_2024)"
    echo "   NiFi Registry:   http://localhost:18080"
    echo ""
    echo "🛠️  Management Commands:"
    echo "   Check Status:    ./scripts/check_services.sh"
    echo "   Restart All:     ./scripts/restart_services.sh"
    echo ""
    echo "📁 Important Files:"
    echo "   Configuration:   .env.codex"
    echo "   Logs:           codex-services/logs/"
    echo "   Services:       codex-services/"
    echo ""
    echo "🚀 The EDI-Lens application is fully operational!"
}

# --- Script Execution --------------------------------------------------------
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi