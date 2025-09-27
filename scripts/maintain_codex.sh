#!/usr/bin/env bash
# ==============================================================================
# EDI LENS - CODEX MAINTENANCE SCRIPT
# ==============================================================================
# Comprehensive maintenance script that starts all services, checks their health,
# and provides detailed status reporting. This script is designed to be run by
# Codex's container caching system to quickly resume services from cached state.
# ==============================================================================

set -euo pipefail

# --- Environment Normalization ------------------------------------------------
# When this script is invoked through the unified wrapper it may be executed via
# `sudo`, which resets the PATH and hides user-level installations (like Poetry
# under ~/.local/bin).  Re-add those common locations so that tools installed
# during setup are discoverable.
add_to_path_if_exists() {
    local dir="$1"
    if [ -d "$dir" ] && [[ ":$PATH:" != *":$dir:"* ]]; then
        PATH="$dir:$PATH"
    fi
}

add_to_path_if_exists "$HOME/.local/bin"

if [ -n "${SUDO_USER:-}" ]; then
    sudo_user_home=$(getent passwd "$SUDO_USER" 2>/dev/null | cut -d: -f6)
    if [ -n "$sudo_user_home" ]; then
        add_to_path_if_exists "$sudo_user_home/.local/bin"
    fi
fi

export PATH

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
error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; }
status() { printf "${CYAN}[STATUS]${NC} %s\n" "$1"; }

# --- Configuration ------------------------------------------------------------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICES_DIR_DEFAULT="/opt/codex-services"
SERVICES_DIR_FALLBACK="$PROJECT_ROOT/.codex-services"

# Determine services directory
if [ -d "$SERVICES_DIR_DEFAULT" ]; then
    SERVICES_DIR="$SERVICES_DIR_DEFAULT"
else
    SERVICES_DIR="$SERVICES_DIR_FALLBACK"
fi

add_to_path_if_exists "$SERVICES_DIR/bin"

ENV_FILE="$PROJECT_ROOT/.env.local"
LOGS_DIR="$SERVICES_DIR/logs"

# Load environment if available
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# Set defaults
: "${NIFI_VERSION:=2.6.0}"
: "${NIFI_REGISTRY_VERSION:=2.6.0}"
: "${POSTGRES_DB:=edi_lens}"
: "${POSTGRES_USER:=edi_user}"
: "${POSTGRES_PASSWORD:=codex_password_2024}"
: "${POSTGRES_NIFI_REGISTRY_DB:=nifi_registry}"
: "${POSTGRES_NIFI_REGISTRY_USER:=nifi_registry}"
: "${POSTGRES_NIFI_REGISTRY_PASSWORD:=nifi_registry_password_2024}"
: "${POSTGRES_PORT:=5432}"
: "${NIFI_ADMIN_USER:=admin}"
: "${NIFI_ADMIN_PASSWORD:=nifi_admin_codex_2024}"
: "${NIFI_SENSITIVE_PROPS_KEY:=codex_nifi_secret_key_2024_pass!}"
: "${NIFI_WEB_PROXY_HOST:=localhost:8443}"

# --- Service Health Check Functions ------------------------------------------
check_port() {
    local port="$1"
    local timeout="${2:-5}"
    
    if [ "$port" = "8443" ]; then
        timeout "$timeout" curl -kfs "https://localhost:$port/" >/dev/null 2>&1
    else
        timeout "$timeout" bash -c "echo >/dev/tcp/localhost/$port" 2>/dev/null ||
        timeout "$timeout" curl -fs "http://localhost:$port/" >/dev/null 2>&1
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

get_service_status() {
    local name="$1"
    local pattern="$2"
    local port="$3"
    local pids
    
    if pids=$(pgrep -f "$pattern" 2>/dev/null); then
        if check_port "$port" 2; then
            echo "✅ HEALTHY (PIDs: $pids)"
            return 0
        else
            echo "⚠️  RUNNING_NO_RESPONSE (PIDs: $pids)"
            return 1
        fi
    else
        echo "❌ STOPPED"
        return 2
    fi
}

get_backend_status() {
    local backend_dir="$PROJECT_ROOT/backend"
    
    # Check if backend dependencies are installed
    if [ ! -d "$backend_dir" ]; then
        echo "❌ MISSING"
        return 2
    fi
    
    if ! command -v poetry >/dev/null 2>&1; then
        echo "❌ NO_POETRY"
        return 2
    fi
    
    cd "$backend_dir"
    if poetry env info --path >/dev/null 2>&1; then
        local venv_path
        venv_path=$(poetry env info --path)
        if [ -d "$venv_path" ] && poetry check >/dev/null 2>&1; then
            echo "✅ DEPENDENCIES_OK"
            cd "$PROJECT_ROOT"
            return 0
        else
            echo "⚠️  DEPENDENCIES_OUTDATED"
            cd "$PROJECT_ROOT"
            return 1
        fi
    else
        echo "❌ NOT_INSTALLED"
        cd "$PROJECT_ROOT"
        return 2
    fi
}

get_frontend_status() {
    local status
    local health_msg=""
    local pid=""
    
    # Check if frontend process is running (look for npm run dev or vite dev)
    if pid=$(pgrep -f "vite.*dev" 2>/dev/null || pgrep -f "npm.*dev" 2>/dev/null | head -1); then
        if check_port "3000" 2; then
            status="✓ Frontend running (PID: $pid, health check: OK)"
        else
            status="⚠ Frontend running but not responding (PID: $pid)"
        fi
    else
        status="✗ Frontend not running"
    fi
    
    echo "$status"
}

start_backend_service() {
    info "🚀 Starting Backend API..."
    
    local backend_dir="$PROJECT_ROOT/backend"
    
    if [ ! -d "$backend_dir" ]; then
        error "Backend directory not found at $backend_dir"
        return 1
    fi

    # Check if backend is already running
    if check_port "8000" 2; then
        success "Backend API already running on port 8000"
        return 0
    fi

    cd "$backend_dir"
    
    # Check if dependencies are installed
    if ! poetry env info --path >/dev/null 2>&1; then
        error "Backend dependencies not installed. Please run setup script first."
        cd "$PROJECT_ROOT"
        return 1
    fi

    info "Starting backend service..."
    
    # Start backend in background
    nohup poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > "$LOGS_DIR/backend.log" 2>&1 &
    
    # Wait for backend to be ready
    if wait_for_service "http://localhost:8000/health" "Backend API" 30; then
        success "✅ Backend API started successfully"
        cd "$PROJECT_ROOT"
        return 0
    else
        error "❌ Failed to start Backend API"
        cd "$PROJECT_ROOT"
        return 1
    fi
}

start_frontend_service() {
    info "🌐 Starting Frontend..."
    
    local frontend_dir="$PROJECT_ROOT/frontend"
    
    if [ ! -d "$frontend_dir" ]; then
        warn "Frontend directory not found - skipping"
        return 1
    fi

    # Check if already running
    if check_port "3000" 2; then
        success "✓ Frontend already running on port 3000"
        return 0
    fi

    cd "$frontend_dir"
    
    # Check if dependencies are installed
    if [ ! -d "node_modules" ]; then
        warn "Frontend dependencies not installed - skipping frontend startup"
        cd "$PROJECT_ROOT"
        return 1
    fi

    # Start frontend in background
    nohup npm run dev > "$LOGS_DIR/frontend.log" 2>&1 &
    cd "$PROJECT_ROOT"
    
    # Wait for frontend to be ready
    if wait_for_service "http://localhost:3000" "Frontend" 30; then
        success "✅ Frontend started successfully"
        return 0
    else
        warn "Frontend failed to start - check logs at $LOGS_DIR/frontend.log"
        return 1
    fi
}

# --- Service Management Functions --------------------------------------------
start_postgresql() {
    info "🐘 Starting PostgreSQL..."
    
    local status_msg
    status_msg=$(get_service_status "PostgreSQL" "postgres.*main" "5432")
    status "PostgreSQL status: $status_msg"
    
    if [[ "$status_msg" == *"HEALTHY"* ]]; then
        success "PostgreSQL already running and healthy"
        return 0
    fi
    
    # Check if PostgreSQL is installed
    if [ ! -f "/var/lib/postgresql/16/main/PG_VERSION" ]; then
        error "PostgreSQL not installed. Please run setup script first."
        return 1
    fi
    
    # Start PostgreSQL if not running
    if ! pgrep -f "postgres.*main" >/dev/null; then
        info "Starting PostgreSQL server..."
        mkdir -p /var/log/postgresql
        chown postgres:postgres /var/log/postgresql 2>/dev/null || true
        
        su - postgres -c '/usr/lib/postgresql/16/bin/pg_ctl start -D /var/lib/postgresql/16/main -l /var/log/postgresql/postgresql-16-main.log -o "-c config_file=/etc/postgresql/16/main/postgresql.conf"' >/dev/null 2>&1
        sleep 5
    fi
    
    # Verify databases exist
    if ! sudo -u postgres psql -lqt | cut -d '|' -f 1 | grep -qw "$POSTGRES_DB"; then
        info "Creating missing databases..."
        sudo -u postgres psql -c "CREATE USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD' CREATEDB;" 2>/dev/null || true
        sudo -u postgres psql -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;" 2>/dev/null || true
        sudo -u postgres psql -c "CREATE USER $POSTGRES_NIFI_REGISTRY_USER WITH PASSWORD '$POSTGRES_NIFI_REGISTRY_PASSWORD';" 2>/dev/null || true
        sudo -u postgres psql -c "CREATE DATABASE $POSTGRES_NIFI_REGISTRY_DB OWNER $POSTGRES_NIFI_REGISTRY_USER;" 2>/dev/null || true
    fi
    
    if check_port "5432" 10; then
        success "✅ PostgreSQL started successfully"
        return 0
    else
        error "❌ Failed to start PostgreSQL"
        return 1
    fi
}

start_nifi_registry() {
    info "📋 Starting NiFi Registry..."
    
    local status_msg
    status_msg=$(get_service_status "NiFi Registry" "org.apache.nifi.registry.NiFiRegistry" "18080")
    status "NiFi Registry status: $status_msg"
    
    if [[ "$status_msg" == *"HEALTHY"* ]]; then
        success "NiFi Registry already running and healthy"
        return 0
    fi
    
    local install_dir="$SERVICES_DIR/nifi-registry"
    local registry_home="$install_dir/nifi-registry-$NIFI_REGISTRY_VERSION"
    
    if [ ! -f "$registry_home/bin/nifi-registry.sh" ]; then
        error "NiFi Registry not installed at $registry_home. Please run setup script first."
        return 1
    fi
    
    # Kill any existing processes
    pkill -f "org.apache.nifi.registry.NiFiRegistry" 2>/dev/null || true
    sleep 3
    
    info "Starting NiFi Registry..."
    mkdir -p "$LOGS_DIR"
    cd "$registry_home"
    
    NIFI_REGISTRY_DB_URL="jdbc:postgresql://localhost:$POSTGRES_PORT/$POSTGRES_NIFI_REGISTRY_DB" \
    NIFI_REGISTRY_DB_USER="$POSTGRES_NIFI_REGISTRY_USER" \
    NIFI_REGISTRY_DB_PASS="$POSTGRES_NIFI_REGISTRY_PASSWORD" \
    NIFI_REGISTRY_WEB_HTTP_HOST=0.0.0.0 \
    NIFI_REGISTRY_WEB_HTTP_PORT=18080 \
    nohup ./bin/nifi-registry.sh run > "$LOGS_DIR/nifi-registry.log" 2>&1 &
    
    if wait_for_service "http://localhost:18080/nifi-registry/" "NiFi Registry" 60; then
        success "✅ NiFi Registry started successfully"
        return 0
    else
        error "❌ Failed to start NiFi Registry"
        return 1
    fi
}

start_nifi() {
    info "🌊 Starting Apache NiFi..."
    
    local status_msg
    status_msg=$(get_service_status "NiFi" "org.apache.nifi.NiFi" "8443")
    status "NiFi status: $status_msg"
    
    if [[ "$status_msg" == *"HEALTHY"* ]]; then
        success "NiFi already running and healthy"
        return 0
    fi
    
    local install_dir="$SERVICES_DIR/nifi"
    local nifi_home="$install_dir/nifi-$NIFI_VERSION"
    
    if [ ! -f "$nifi_home/bin/nifi.sh" ]; then
        error "NiFi not installed at $nifi_home. Please run setup script first."
        return 1
    fi
    
    # Kill any existing processes
    pkill -f "org.apache.nifi.NiFi" 2>/dev/null || true
    sleep 5
    
    # Check for start script
    local start_script="$nifi_home/start_nifi.sh"
    if [ ! -f "$start_script" ]; then
        error "NiFi start script not found. Please run setup script first."
        return 1
    fi
    
    info "Starting NiFi..."
    mkdir -p "$LOGS_DIR"
    
    # Ensure nifi user exists and has proper permissions
    if ! id -u nifi >/dev/null 2>&1; then
        useradd --system --no-create-home --home-dir "$nifi_home" --shell /usr/sbin/nologin nifi 2>/dev/null || true
    fi
    chown -R nifi:nifi "$nifi_home" 2>/dev/null || true
    
    su -s /bin/bash nifi -c "$start_script" >> "$LOGS_DIR/nifi.log" 2>&1 &
    
    sleep 10
    if wait_for_service "https://localhost:8443/nifi/" "NiFi" 180; then
        success "✅ NiFi started successfully"
        return 0
    else
        error "❌ Failed to start NiFi"
        return 1
    fi
}

# --- Status Reporting Functions ----------------------------------------------
show_service_summary() {
    info "====================================================================="
    info "🔍 SERVICE STATUS SUMMARY"
    info "====================================================================="
    
    local postgres_status
    local registry_status  
    local nifi_status
    local backend_status
    local frontend_status
    
    postgres_status=$(get_service_status "PostgreSQL" "postgres.*main" "5432" || echo "❌ STOPPED")
    registry_status=$(get_service_status "NiFi Registry" "org.apache.nifi.registry.NiFiRegistry" "18080" || echo "❌ STOPPED")
    nifi_status=$(get_service_status "NiFi" "org.apache.nifi.NiFi" "8443" || echo "❌ STOPPED")
    backend_status=$(get_backend_status || echo "❌ NOT_READY")
    frontend_status=$(get_frontend_status || echo "❌ NOT_READY")
    
    printf "%-20s %s\n" "PostgreSQL:" "$postgres_status"
    printf "%-20s %s\n" "NiFi Registry:" "$registry_status"
    printf "%-20s %s\n" "NiFi:" "$nifi_status"
    printf "%-20s %s\n" "Backend API:" "$backend_status"
    printf "%-20s %s\n" "Frontend:" "$frontend_status"
    
    if [[ "$postgres_status" == *"HEALTHY"* ]] && 
       [[ "$registry_status" == *"HEALTHY"* ]] && 
       [[ "$nifi_status" == *"HEALTHY"* ]] &&
       [[ "$backend_status" == *"DEPENDENCIES_OK"* ]]; then
        echo ""
        success "🎉 All services and dependencies are ready!"
        show_service_endpoints
        return 0
    else
        echo ""
        warn "⚠️  Some services or dependencies need attention"
        return 1
    fi
}

show_service_endpoints() {
    info "====================================================================="
    info "🌐 SERVICE ENDPOINTS"
    info "====================================================================="
    echo "  Frontend   : http://localhost:3000"
    echo "  Backend API: http://localhost:8000 (docs: http://localhost:8000/docs)"
    echo "  PostgreSQL : localhost:${POSTGRES_PORT:-5432} (database: $POSTGRES_DB)"
    echo "  NiFi       : https://localhost:8443 (user: $NIFI_ADMIN_USER)"
    echo "  Registry   : http://localhost:18080"
    echo ""
    echo "  Logs       : $LOGS_DIR"
    echo "  Services   : $SERVICES_DIR"
}

show_detailed_status() {
    info "====================================================================="
    info "📊 DETAILED SYSTEM STATUS"
    info "====================================================================="
    
    # System resources
    info "💻 System Resources:"
    echo "  Memory: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
    echo "  Disk: $(df -h "$SERVICES_DIR" | awk 'NR==2 {print $3 "/" $2 " (" $5 " used)"}')"
    
    # Service directories
    info "📁 Service Directories:"
    if [ -d "$SERVICES_DIR" ]; then
        local size=$(du -sh "$SERVICES_DIR" 2>/dev/null | cut -f1 || echo "unknown")
        echo "  Services dir: $SERVICES_DIR ($size)"
        
        for service in postgresql nifi nifi-registry; do
            if [ -d "$SERVICES_DIR/$service" ]; then
                local svc_size=$(du -sh "$SERVICES_DIR/$service" 2>/dev/null | cut -f1 || echo "unknown")
                echo "    ✓ $service ($svc_size)"
            else
                echo "    ✗ $service (missing)"
            fi
        done
    else
        echo "    ✗ Services directory not found: $SERVICES_DIR"
    fi
    
    # Log files
    info "📋 Recent Log Activity:"
    if [ -d "$LOGS_DIR" ]; then
        for log in postgresql nifi-registry nifi; do
            local logfile="$LOGS_DIR/${log}.log"
            if [ -f "$logfile" ]; then
                local size=$(du -sh "$logfile" 2>/dev/null | cut -f1 || echo "0")
                local lines=$(wc -l < "$logfile" 2>/dev/null || echo "0")
                echo "    $log.log: $size ($lines lines)"
            fi
        done
    else
        echo "    No logs directory found"
    fi
}

# --- Main Functions ----------------------------------------------------------
maintenance_start_all() {
    info "====================================================================="
    info "🚀 STARTING ALL CODEX SERVICES"
    info "====================================================================="
    
    local failed=0
    
    # Start services in dependency order
    start_postgresql || ((failed++))
    start_nifi_registry || ((failed++))
    start_nifi || ((failed++))
    start_backend_service || ((failed++))
    start_frontend_service || ((failed++))
    
    echo ""
    if [ $failed -eq 0 ]; then
        success "🎉 All services started successfully!"
        show_service_endpoints
    else
        error "❌ $failed service(s) failed to start"
        show_service_summary
        return 1
    fi
}

maintenance_stop_all() {
    info "====================================================================="
    info "🛑 STOPPING ALL CODEX SERVICES"
    info "====================================================================="
    
    info "Stopping Frontend..."
    pkill -f "vite.*dev" 2>/dev/null || pkill -f "npm.*dev" 2>/dev/null || true
    
    info "Stopping Backend API..."
    pkill -f "uvicorn.*src.main:app" 2>/dev/null || true
    
    info "Stopping NiFi..."
    pkill -f "org.apache.nifi.NiFi" 2>/dev/null || true
    
    info "Stopping NiFi Registry..."
    pkill -f "org.apache.nifi.registry.NiFiRegistry" 2>/dev/null || true
    
    info "Stopping PostgreSQL..."
    if [ -f "/var/lib/postgresql/16/main/PG_VERSION" ]; then
        su - postgres -c '/usr/lib/postgresql/16/bin/pg_ctl stop -D /var/lib/postgresql/16/main' >/dev/null 2>&1 || true
    fi
    
    sleep 5
    success "All services stopped"
}

show_logs() {
    local service="$1"
    local log_file=""
    
    case "$service" in
        "backend")
            log_file="$LOGS_DIR/backend.log"
            ;;
        "frontend")
            log_file="$LOGS_DIR/frontend.log"
            ;;
        "nifi")
            log_file="$LOGS_DIR/nifi.log"
            ;;
        "registry")
            log_file="$LOGS_DIR/nifi-registry.log"
            ;;
        "db"|"postgres"|"postgresql")
            log_file="/var/log/postgresql/postgresql-16-main.log"
            ;;
        *)
            error "Unknown service: $service"
            info "Available services: backend, frontend, nifi, registry, db"
            return 1
            ;;
    esac
    
    if [ -f "$log_file" ]; then
        info "Showing logs for $service ($log_file):"
        echo "====================================================================="
        tail -f "$log_file"
    else
        warn "Log file not found: $log_file"
        return 1
    fi
}

clean_all() {
    info "Performing deep clean..."
    
    # Stop services first
    maintenance_stop_all
    
    # Remove service directories and data
    info "Removing service data..."
    rm -rf "$SERVICES_DIR" 2>/dev/null || true
    
    # Remove postgres data if it exists
    if [ -d "/var/lib/postgresql" ]; then
        info "Removing PostgreSQL data..."
        rm -rf /var/lib/postgresql/16/main 2>/dev/null || true
    fi
    
    # Clean log files
    info "Cleaning log files..."
    rm -rf "$LOGS_DIR" 2>/dev/null || true
    rm -f "$PROJECT_ROOT/logs/"* 2>/dev/null || true
    
    success "Deep clean completed - database and all data removed"
}

run_tests() {
    local test_type="${1:-all}"
    
    info "🧪 Running combined test suite: $test_type"
    echo ""

    # Run backend tests
    info "📦 BACKEND TESTS"
    info "====================="
    run_backend_tests "$test_type"
    
    echo ""
    
    # Run frontend tests
    info "🌐 FRONTEND TESTS"
    info "====================="
    run_frontend_tests "$test_type"
    
    echo ""
    success "✅ Combined test suite completed: $test_type"
}

run_backend_tests() {
    local test_type="${1:-all}"
    local backend_dir="$PROJECT_ROOT/backend"

    if [ ! -d "$backend_dir" ]; then
        warn "Backend directory not found - skipping backend tests"
        return 0
    fi

    cd "$backend_dir"

    if ! command -v poetry >/dev/null 2>&1; then
        error "Poetry is not available. Please run sudo bash scripts/setup_codex.sh to provision backend dependencies."
        cd "$PROJECT_ROOT"
        return 1
    fi

    local venv_path=""
    if ! venv_path=$(poetry env info --path 2>/dev/null); then
        error "Backend virtual environment not found. Run sudo bash scripts/setup_codex.sh or execute \"poetry install --with dev\" inside backend/ to install dependencies."
        cd "$PROJECT_ROOT"
        return 1
    fi

    if [ ! -x "$venv_path/bin/pytest" ]; then
        error "Pytest is missing from the Poetry environment. Re-run the setup script or install backend dev dependencies."
        cd "$PROJECT_ROOT"
        return 1
    fi

    case "$test_type" in
        unit)
            info "Running backend unit tests..."
            poetry run pytest tests/unit/
            success "Unit tests completed"
            ;;
        integration)
            info "Running backend integration tests..."
            poetry run pytest tests/integration/
            success "Integration tests completed"
            ;;
        e2e)
            info "Running backend end-to-end tests..."
            poetry run pytest tests/e2e/
            success "End-to-end tests completed"
            ;;
        all)
            info "Running all backend tests..."
            poetry run pytest tests/
            success "All tests completed"
            ;;
        watch)
            info "Running backend tests in watch mode..."
            poetry run pytest tests/ --watch
            ;;
        *)
            warn "Unknown backend test type: $test_type"
            ;;
    esac
    
    cd "$PROJECT_ROOT"
}

run_frontend_tests() {
    local test_type="${1:-all}"
    local frontend_dir="$PROJECT_ROOT/frontend"
    
    if [ ! -d "$frontend_dir" ]; then
        warn "Frontend directory not found at $frontend_dir"
        return 0
    fi

    cd "$frontend_dir"

    case "$test_type" in
        unit|integration)
            info "Running frontend $test_type tests..."
            if command -v npm >/dev/null 2>&1 && npm run "test:$test_type" --silent >/dev/null 2>&1; then
                npm run "test:$test_type"
            else
                warn "Frontend $test_type tests not available - skipping"
            fi
            ;;
        e2e)
            info "Running frontend E2E tests..."
            if command -v npm >/dev/null 2>&1 && npm run test:e2e --silent >/dev/null 2>&1; then
                npm run test:e2e
            else
                warn "Frontend E2E tests not available - skipping"
            fi
            ;;
        all)
            info "Running all frontend tests..."
            
            # Run integration tests if available
            if npm run test:integration --silent >/dev/null 2>&1; then
                info "→ Frontend integration tests"
                npm run test:integration
            else
                warn "Frontend integration tests not available - skipping"
            fi
            
            # Run E2E tests if available
            if npm run test:e2e --silent >/dev/null 2>&1; then
                info "→ Frontend E2E tests"
                npm run test:e2e
            else
                warn "Frontend E2E tests not available - skipping"
            fi
            ;;
        *)
            warn "Unknown frontend test type: $test_type - skipping frontend tests"
            ;;
    esac

    cd "$PROJECT_ROOT"
}

maintenance_restart_all() {
    info "====================================================================="
    info "🔄 RESTARTING ALL CODEX SERVICES"
    info "====================================================================="
    
    maintenance_stop_all
    sleep 3
    maintenance_start_all
}

usage() {
    cat <<EOF
EDI Lens Codex Development Maintenance

USAGE:
    $0 <command> [options]

ESSENTIAL COMMANDS:
    start                Start all services (infrastructure + backend + frontend)
    stop                 Stop all services
    restart              Restart all services
    status               Show detailed status of all services
    logs [service]       Show logs (backend, frontend, nifi, registry, db)
    clean                DESTRUCTIVE: Remove all containers, volumes, and data

DEVELOPMENT COMMANDS:
    test [type]          Run combined tests - both backend and frontend (unit, integration, e2e, all, watch)
    dev                  Start in development mode (infrastructure + backend + frontend)

TEST TYPES:
    unit                 Run unit tests (backend + frontend)
    integration          Run integration tests (backend + frontend) 
    e2e                  Run end-to-end tests (backend + frontend)
    all                  Run all test types (default)
    watch                Run backend tests in watch mode (backend only)

EXAMPLES:
    $0 start             # Start everything
    $0 status            # Show status
    $0 logs backend      # Show backend logs
    $0 test unit         # Run unit tests (backend + frontend)
    $0 test integration  # Run integration tests (backend + frontend)
    $0 test e2e          # Run E2E tests (backend + frontend)
    $0 clean             # Nuclear option - removes all data

SERVICES:
    - PostgreSQL (port 5432)
    - NiFi (port 8443)
    - Registry (port 18080)  
    - Backend API (port 8000)
    - Frontend (port 3000)

EOF
}

# --- Main Script Logic -------------------------------------------------------
main() {
    local command="${1:-start}"
    
    case "$command" in
        start|dev)
            maintenance_start_all
            ;;
        stop)
            maintenance_stop_all
            ;;
        restart)
            maintenance_restart_all
            ;;
        status)
            show_service_summary
            ;;
        detailed)
            show_detailed_status
            show_service_summary
            ;;
        test)
            local test_type="${2:-all}"
            run_tests "$test_type"
            ;;
        logs)
            local service="$2"
            if [ -z "$service" ]; then
                error "Please specify a service: backend, frontend, nifi, registry, db"
                exit 1
            fi
            show_logs "$service"
            ;;
        clean)
            clean_all
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

# Ensure we're running as root for service management
if [ "$EUID" -ne 0 ]; then
    error "This script must be run as root to manage services"
    exit 1
fi

main "$@"