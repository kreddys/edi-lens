#!/usr/bin/env bash
# ==============================================================================
# EDI LENS - LOCAL DEVELOPMENT MAINTENANCE
# ==============================================================================
# Maintenance script for local development environment
# Manages Docker infrastructure and local backend service
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
error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; }
status() { printf "${CYAN}[STATUS]${NC} %s\n" "$1"; }

# --- Configuration ------------------------------------------------------------
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOCKER_DIR="$PROJECT_ROOT/docker"
BACKEND_DIR="$PROJECT_ROOT/backend"
ENV_FILE="$PROJECT_ROOT/.env.local"

# Load environment if available
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

# --- Utility Functions -------------------------------------------------------
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
    warn "$name failed to respond after $max_attempts attempts"
    return 1
}

is_backend_running() {
    curl -fs "http://localhost:8000/health" >/dev/null 2>&1
}

get_backend_pid() {
    pgrep -f "uvicorn.*src.main:app" || true
}

# --- Backend Utilities -------------------------------------------------------
check_backend_dir() {
    if [ ! -d "$BACKEND_DIR" ]; then
        error "Backend directory not found: $BACKEND_DIR"
    fi
}

check_poetry() {
    if ! command -v poetry >/dev/null 2>&1; then
        error "Poetry is not installed. Install it from https://python-poetry.org/docs/"
    fi
}

ensure_pytest_available() {
    if ! poetry run pytest --version >/dev/null 2>&1; then
        warn "Pytest not available in the Poetry environment. Installing backend dependencies..."
        if ! poetry install --with dev --no-interaction; then
            error "Failed to install backend dependencies with Poetry"
        fi
    fi
}

warn_if_unreachable() {
    local name="$1"
    local url="$2"
    local insecure="${3:-}"
    local curl_flags="-fs"

    if [ "$insecure" = "insecure" ]; then
        curl_flags="-kfs"
    fi

    if ! curl $curl_flags "$url" >/dev/null 2>&1; then
        warn "$name not reachable at $url"
    fi
}

run_pytest_suite() {
    local suite_path="$1"
    shift || true
    local -a pytest_args=("$suite_path" "-v")

    if (( $# > 0 )); then
        pytest_args+=("$@")
    fi

    poetry run pytest "${pytest_args[@]}"
}

run_pytest_watch() {
    local -a extra_args=()
    if (( $# )); then
        extra_args=("$@")
    fi

    info "Starting pytest in watch mode..."

    if poetry run ptw --help >/dev/null 2>&1; then
        if (( ${#extra_args[@]} )); then
            poetry run ptw tests/ -- -v "${extra_args[@]}"
        else
            poetry run ptw tests/ -- -v
        fi
    elif poetry run pytest --help | grep -q -- "--looponfail"; then
        if (( ${#extra_args[@]} )); then
            poetry run pytest --looponfail tests/ -v "${extra_args[@]}"
        else
            poetry run pytest --looponfail tests/ -v
        fi
    else
        warn "Watch mode not available. Running tests once instead."
        if (( ${#extra_args[@]} )); then
            run_pytest_suite "tests/" "${extra_args[@]}"
        else
            run_pytest_suite "tests/"
        fi
    fi
}

run_backend_tests() {
    local test_type="${1:-all}"
    if (( $# > 0 )); then
        shift
    fi
    local -a extra_args=("$@")

    check_backend_dir
    check_poetry

    local original_dir="$PWD"
    cd "$BACKEND_DIR"

    ensure_pytest_available

    case "$test_type" in
        unit)
            info "Running backend unit tests..."
            if (( ${#extra_args[@]} )); then
                run_pytest_suite "tests/unit/" "${extra_args[@]}"
            else
                run_pytest_suite "tests/unit/"
            fi
            success "Unit tests completed"
            ;;
        integration)
            info "Running backend integration tests..."
            local nifi_base="${NIFI_URL:-https://localhost:8443}"
            nifi_base="${nifi_base%/}"
            warn_if_unreachable "NiFi" "$nifi_base/nifi/" insecure

            local registry_base="${NIFI_REGISTRY_URL:-http://localhost:18080}"
            registry_base="${registry_base%/}"
            warn_if_unreachable "NiFi Registry" "$registry_base/nifi-registry-api/config"

            if (( ${#extra_args[@]} )); then
                run_pytest_suite "tests/integration/" "${extra_args[@]}"
            else
                run_pytest_suite "tests/integration/"
            fi
            success "Integration tests completed"
            ;;
        e2e)
            info "Running backend end-to-end tests..."
            local backend_base="${BACKEND_URL:-http://localhost:8000}"
            backend_base="${backend_base%/}"
            warn_if_unreachable "Backend API" "$backend_base/health"

            local nifi_base="${NIFI_URL:-https://localhost:8443}"
            nifi_base="${nifi_base%/}"
            warn_if_unreachable "NiFi" "$nifi_base/nifi/" insecure

            local registry_base="${NIFI_REGISTRY_URL:-http://localhost:18080}"
            registry_base="${registry_base%/}"
            warn_if_unreachable "NiFi Registry" "$registry_base/nifi-registry-api/config"

            if (( ${#extra_args[@]} )); then
                run_pytest_suite "tests/e2e/" "${extra_args[@]}"
            else
                run_pytest_suite "tests/e2e/"
            fi
            success "End-to-end tests completed"
            ;;
        all)
            info "Running full backend test suite..."

            info "→ Unit tests"
            if (( ${#extra_args[@]} )); then
                run_pytest_suite "tests/unit/" "${extra_args[@]}"
            else
                run_pytest_suite "tests/unit/"
            fi

            info "→ Integration tests"
            local nifi_base="${NIFI_URL:-https://localhost:8443}"
            nifi_base="${nifi_base%/}"
            warn_if_unreachable "NiFi" "$nifi_base/nifi/" insecure

            local registry_base="${NIFI_REGISTRY_URL:-http://localhost:18080}"
            registry_base="${registry_base%/}"
            warn_if_unreachable "NiFi Registry" "$registry_base/nifi-registry-api/config"
            if (( ${#extra_args[@]} )); then
                run_pytest_suite "tests/integration/" "${extra_args[@]}"
            else
                run_pytest_suite "tests/integration/"
            fi

            info "→ End-to-end tests"
            local backend_base="${BACKEND_URL:-http://localhost:8000}"
            backend_base="${backend_base%/}"
            warn_if_unreachable "Backend API" "$backend_base/health"
            warn_if_unreachable "NiFi" "$nifi_base/nifi/" insecure
            warn_if_unreachable "NiFi Registry" "$registry_base/nifi-registry-api/config"
            if (( ${#extra_args[@]} )); then
                run_pytest_suite "tests/e2e/" "${extra_args[@]}"
            else
                run_pytest_suite "tests/e2e/"
            fi

            success "All backend tests completed"
            ;;
        watch)
            info "Starting backend tests in watch mode..."
            run_pytest_watch "${extra_args[@]}"
            success "Test watch session ended"
            ;;
        *)
            cd "$original_dir"
            error "Unknown test type: $test_type"
            ;;
    esac

    cd "$original_dir"
}

# --- Service Management Functions --------------------------------------------
start_infrastructure() {
    info "Starting Docker infrastructure services..."
    check_docker
    check_docker_compose

    cd "$DOCKER_DIR"
    $DOCKER_COMPOSE up -d

    # Wait for services
    info "Waiting for infrastructure services..."

    # Wait for database
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

    wait_for_service "http://localhost:18080/nifi-registry-api/config" "Registry" 60
    wait_for_service "https://localhost:8443/nifi/" "NiFi" 120

    success "Infrastructure services are running"
}

stop_infrastructure() {
    info "Stopping Docker infrastructure services..."
    check_docker_compose

    cd "$DOCKER_DIR"
    $DOCKER_COMPOSE down

    success "Infrastructure services stopped"
}

start_backend() {
    if is_backend_running; then
        success "Backend is already running"
        return 0
    fi

    info "Starting backend service..."

    if [ ! -d "$BACKEND_DIR" ]; then
        error "Backend directory not found: $BACKEND_DIR"
    fi

    cd "$BACKEND_DIR"

    # Check if poetry env exists
    if ! poetry env info --path >/dev/null 2>&1; then
        warn "Backend dependencies not installed. Run './scripts/setup_local.sh' first"
        return 1
    fi

    # Start backend in background
    info "Starting backend with Poetry..."
    nohup poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > ../logs/backend.log 2>&1 &

    # Wait for backend to be ready
    if wait_for_service "http://localhost:8000/health" "Backend" 30; then
        local pid
        pid=$(get_backend_pid)
        success "Backend started successfully (PID: $pid)"
        cd "$PROJECT_ROOT"
        return 0
    else
        warn "Backend failed to start - check logs at ../logs/backend.log"
        cd "$PROJECT_ROOT"
        return 1
    fi
}

stop_backend() {
    local pid
    pid=$(get_backend_pid)

    if [ -z "$pid" ]; then
        info "Backend is not running"
        return 0
    fi

    info "Stopping backend service (PID: $pid)..."
    kill "$pid" 2>/dev/null || true

    # Wait for process to stop
    local attempt=1
    while [ $attempt -le 10 ]; do
        if ! kill -0 "$pid" 2>/dev/null; then
            success "Backend stopped successfully"
            return 0
        fi
        sleep 1
        attempt=$((attempt + 1))
    done

    # Force kill if still running
    warn "Backend didn't stop gracefully, force killing..."
    kill -9 "$pid" 2>/dev/null || true
    success "Backend stopped"
}

# --- Status Functions --------------------------------------------------------
show_status() {
    info "====================================================================="
    info "📊 LOCAL DEVELOPMENT ENVIRONMENT STATUS"
    info "====================================================================="

    # Check Docker containers
    info "🐳 Docker Infrastructure:"
    local containers=("edi-lens-db" "edi-lens-nifi" "edi-lens-registry")
    local all_running=true

    for container in "${containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^$container$"; then
            local status_info
            status_info=$(docker ps --format "{{.Status}}" --filter "name=$container")
            success "  ✓ $container ($status_info)"
        else
            warn "  ✗ $container (not running)"
            all_running=false
        fi
    done

    # Check backend
    info "🐍 Backend Service:"
    local backend_pid
    backend_pid=$(get_backend_pid)
    if [ -n "$backend_pid" ]; then
        if is_backend_running; then
            success "  ✓ Backend running (PID: $backend_pid, health check: OK)"
        else
            warn "  ⚠ Backend process found (PID: $backend_pid) but health check failed"
        fi
    else
        warn "  ✗ Backend not running"
        all_running=false
    fi

    # Service endpoints
    info "🌐 Service Health:"
    local endpoints=(
        "PostgreSQL:5432"
        "Registry:http://localhost:18080/nifi-registry-api/config"
        "NiFi:https://localhost:8443/nifi/"
        "Backend:http://localhost:8000/health"
    )

    for endpoint in "${endpoints[@]}"; do
        local name="${endpoint%%:*}"
        local check="${endpoint#*:}"

        if [[ "$check" == http* ]]; then
            if [[ "$check" == https:* ]]; then
                if curl -kfs "$check" >/dev/null 2>&1; then
                    success "  ✓ $name"
                else
                    warn "  ✗ $name"
                fi
            else
                if curl -fs "$check" >/dev/null 2>&1; then
                    success "  ✓ $name"
                else
                    warn "  ✗ $name"
                fi
            fi
        else
            # Port check
            local port="$check"
            if nc -z localhost "$port" 2>/dev/null; then
                success "  ✓ $name"
            else
                warn "  ✗ $name"
            fi
        fi
    done

    echo ""
    if [ "$all_running" = true ]; then
        success "🎉 All services are running and healthy!"
    else
        warn "⚠️  Some services need attention"
    fi

    echo ""
    info "🔧 Useful commands:"
    info "  Backend logs: tail -f logs/backend.log"
    info "  NiFi logs:    docker logs edi-lens-nifi"
    info "  Registry logs: docker logs edi-lens-registry"
    info "  DB logs:      docker logs edi-lens-db"
}

show_logs() {
    local service="${1:-}"

    case "$service" in
        backend)
            if [ -f "$PROJECT_ROOT/logs/backend.log" ]; then
                tail -f "$PROJECT_ROOT/logs/backend.log"
            else
                warn "Backend log file not found"
            fi
            ;;
        nifi)
            docker logs -f edi-lens-nifi
            ;;
        registry)
            docker logs -f edi-lens-registry
            ;;
        db)
            docker logs -f edi-lens-db
            ;;
        *)
            info "Available log sources: backend, nifi, registry, db"
            info "Usage: $0 logs <service>"
            ;;
    esac
}

# --- Help Function -----------------------------------------------------------
show_help() {
    cat <<EOF
EDI Lens Local Development Maintenance

USAGE:
    $0 <command> [options]

COMMANDS:
    start                Start all services (infrastructure + backend)
    stop                 Stop all services
    restart              Restart all services

    start-infra          Start only Docker infrastructure
    stop-infra           Stop only Docker infrastructure
    restart-infra        Restart only Docker infrastructure

    start-backend        Start only backend service
    stop-backend         Stop only backend service
    restart-backend      Restart only backend service

    status               Show detailed status of all services
    logs [service]       Show logs (backend, nifi, registry, db)

    test-unit [args]     Run backend unit tests
    test-integration [args]
                         Run backend integration tests
    test-e2e [args]      Run backend end-to-end tests
    test-all [args]      Run the full backend test suite
    test-watch [args]    Run backend tests in watch mode

    health               Quick health check
    clean                Stop all services and clean up

EXAMPLES:
    $0 start             # Start everything
    $0 start-infra       # Start only Docker containers
    $0 start-backend     # Start only backend
    $0 test-integration  # Run backend integration tests
    $0 status            # Show status
    $0 logs backend      # Show backend logs
    $0 restart           # Restart everything

SERVICES:
    Infrastructure (Docker):
      - PostgreSQL (port 5432)
      - NiFi (port 8443)
      - Registry (port 18080)

    Backend (Local):
      - FastAPI backend (port 8000)

EOF
}

# --- Main Command Handler ----------------------------------------------------
main() {
    # Ensure logs directory exists
    mkdir -p "$PROJECT_ROOT/logs"

    case "${1:-help}" in
        start)
            start_infrastructure
            start_backend
            ;;
        stop)
            stop_backend
            stop_infrastructure
            ;;
        restart)
            stop_backend
            stop_infrastructure
            sleep 2
            start_infrastructure
            start_backend
            ;;
        start-infra|start-infrastructure)
            start_infrastructure
            ;;
        stop-infra|stop-infrastructure)
            stop_infrastructure
            ;;
        restart-infra|restart-infrastructure)
            stop_infrastructure
            sleep 2
            start_infrastructure
            ;;
        start-backend)
            start_backend
            ;;
        stop-backend)
            stop_backend
            ;;
        restart-backend)
            stop_backend
            sleep 2
            start_backend
            ;;
        test-unit)
            shift
            run_backend_tests unit "$@"
            ;;
        test-integration)
            shift
            run_backend_tests integration "$@"
            ;;
        test-e2e)
            shift
            run_backend_tests e2e "$@"
            ;;
        test-all)
            shift
            run_backend_tests all "$@"
            ;;
        test-watch)
            shift
            run_backend_tests watch "$@"
            ;;
        status)
            show_status
            ;;
        logs)
            show_logs "${2:-}"
            ;;
        health)
            show_status
            ;;
        clean)
            stop_backend
            stop_infrastructure
            success "All services stopped and cleaned up"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            error "Unknown command: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
