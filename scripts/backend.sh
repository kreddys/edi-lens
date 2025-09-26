#!/bin/bash
# ==============================================================================
# EDI Lens Backend Management Script - SIMPLIFIED
# ==============================================================================
# Simple, focused script for the backend with local-only testing
# Usage: ./scripts/backend.sh [command] [options]
#
# Philosophy: Simple, predictable, fast
# - Single responsibility: manage the backend
# - Clear commands with intuitive names
# - Tests run locally only, connecting to configured endpoints
# - No complex Docker test environment abstractions
# ==============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKER_DIR="$PROJECT_ROOT/docker"
BACKEND_DIR="$PROJECT_ROOT/backend"
DOCKER_COMPOSE=""
ENV_FILE="$PROJECT_ROOT/.env.local"

# Colors and logging
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly PURPLE='\033[0;35m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }
log_debug() { echo -e "${PURPLE}[DEBUG]${NC} $1"; }
log_step() { echo -e "${CYAN}[STEP]${NC} $1"; }

# Cross-platform helpers
show_port_usage() {
    local pattern="$1"

    if command -v lsof >/dev/null 2>&1; then
        lsof -nP -iTCP -sTCP:LISTEN 2>/dev/null | awk -v target="$pattern" 'NR==1 || $9 ~ target'
    elif command -v ss >/dev/null 2>&1; then
        ss -tulpn 2>/dev/null | grep -E "$pattern" || true
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tulpn 2>/dev/null | grep -E "$pattern" || true
    else
        log_warn "Port inspection tools (lsof/ss/netstat) not available"
    fi
}

is_port_in_use() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        lsof -Pi ":$port" -sTCP:LISTEN -t >/dev/null 2>&1
    elif command -v ss >/dev/null 2>&1; then
        ss -tuln | grep -q ":$port "
    elif command -v netstat >/dev/null 2>&1; then
        netstat -tuln | grep -q ":$port "
    else
        return 1
    fi
}

load_project_env() {
    if [[ -f "$ENV_FILE" ]]; then
        log_debug "Loading environment variables from $ENV_FILE"
        set -a
        # shellcheck disable=SC1090
        source "$ENV_FILE"
        set +a
    else
        log_warn "Environment file $ENV_FILE not found; docker compose variables may be unset"
    fi
}

# Check functions
check_docker() {
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running or accessible"
        exit 1
    fi
}

check_docker_compose() {
    check_docker

    if command -v docker-compose >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker-compose"
    elif docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        log_error "Neither 'docker-compose' nor 'docker compose' is available"
        exit 1
    fi
}

check_backend_dir() {
    if [[ ! -d "$BACKEND_DIR" ]]; then
        log_error "Backend directory not found: $BACKEND_DIR"
        exit 1
    fi
}

check_poetry() {
    if ! command -v poetry >/dev/null 2>&1; then
        log_error "Poetry is not installed. Please install Poetry: https://python-poetry.org/docs/#installation"
        exit 1
    fi
}

ensure_backend_container_running() {
    if ! docker ps --format "{{.Names}}" | grep -q "^edi-lens-backend$"; then
        log_error "Backend container is not running. Start services with './scripts/backend.sh start'."
        exit 1
    fi
}

wait_for_container_healthy() {
    local container_name="$1"
    local timeout="${2:-60}"
    local attempt=1

    log_info "Waiting for container '$container_name' to report healthy (timeout: ${timeout}s)..."

    while [[ $attempt -le $timeout ]]; do
        local health_status
        health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "none")

        if [[ "$health_status" == "healthy" ]]; then
            log_success "Container '$container_name' is healthy!"
            return 0
        elif [[ "$health_status" == "none" ]]; then
            # Container doesn't have health check, just check if it's running
            if docker ps --format "{{.Names}}" | grep -q "^$container_name$"; then
                log_success "Container '$container_name' is running (no health check)!"
                return 0
            fi
        fi

        if [[ $((attempt % 10)) -eq 0 ]]; then
            echo -n "."
        fi

        sleep 1
        ((attempt++))
    done

    log_error "Container '$container_name' failed to become healthy within ${timeout}s"
    return 1
}

wait_for_service() {
    local service_name="$1"
    local url="$2"
    local max_attempts=30
    local attempt=1

    log_info "Waiting for $service_name to be ready..."

    while [[ $attempt -le $max_attempts ]]; do
        if curl -s -k "$url" >/dev/null 2>&1; then
            log_success "$service_name is ready!"
            return 0
        fi

        if [[ $((attempt % 5)) -eq 0 ]]; then
            echo -n "."
        fi

        sleep 2
        ((attempt++))
    done

    log_warn "$service_name did not become ready within expected time"
    return 1
}

run_pytest_watch() {
    local -a extra_args=("$@")
    log_info "Starting pytest in watch mode..."

    if ! poetry run pytest --version >/dev/null 2>&1; then
        log_warn "pytest not found. Installing dependencies..."
        poetry install --no-interaction --no-root
    fi

    if command -v pytest-watch >/dev/null 2>&1; then
        poetry run ptw tests/ -- -v "${extra_args[@]}"
    elif poetry run pytest --help | grep -q "\-\-looponfail"; then
        poetry run pytest --looponfail tests/ -v "${extra_args[@]}"
    else
        log_warn "Watch mode not available. Running tests once."
        poetry run pytest tests/ -v "${extra_args[@]}"
    fi
}

show_help() {
    cat <<EOF
EDI Lens Backend Management Script

USAGE:
    ./scripts/backend.sh <command> [options]

COMMANDS:
    start                Start all services in development mode
    dev                  Alias for 'start' (development mode with hot reload)
    prod                 Start all services in production mode
    stop                 Stop all services
    restart              Restart all services
    status               Show service status
    logs [service]       Show logs (all services or specific service)
    build                Build service containers
    clean                Remove all containers and volumes
    shell                Open shell in backend container
    setup                Set up local development environment

TESTING:
    test unit [args]     Run unit tests locally
    test integration [args] Run integration tests locally
    test e2e [args]      Run end-to-end tests locally
    test all [args]      Run all tests locally
    test:watch [args]    Run tests in watch mode
    
    Note: All tests run locally and connect to the configured endpoints in .env

DEVELOPMENT:
    lint                 Run code linting
    format               Format code with black/isort

HEALTH & DEBUGGING:
    health               Check health of all services
    debug                Show debug information
    doctor               Diagnose common issues

EXAMPLES:
    ./scripts/backend.sh start                         # Start all services in dev mode
    ./scripts/backend.sh test unit                     # Run unit tests
    ./scripts/backend.sh test integration              # Run integration tests  
    ./scripts/backend.sh test all                      # Run all tests
    ./scripts/backend.sh logs backend                  # Show backend logs
    ./scripts/backend.sh health                        # Check service health

SERVICES:
    - backend     (port 8000)  FastAPI application
    - nifi        (port 8443)  Apache NiFi (HTTPS)
    - registry    (port 18080) NiFi Registry (HTTP)
    - db          (port 5432)  PostgreSQL database

EOF
}

cmd_start() {
    check_docker
    check_docker_compose

    log_step "Starting EDI Lens backend services..."

    cd "$DOCKER_DIR"
    load_project_env
    
    # Build containers first to ensure latest changes
    log_info "Building containers with latest changes..."
    $DOCKER_COMPOSE build
    
    $DOCKER_COMPOSE up -d

    log_info "Services starting in background..."

    # Wait for key services
    if ! wait_for_container_healthy "edi-lens-db" 120; then
        log_error "Database failed to start within timeout"
        log_info "Showing recent database logs (last 200 lines):"
        docker logs --tail 200 edi-lens-db || true
    fi
    wait_for_service "Registry" "http://localhost:18080/nifi-registry-api/config" || true
    wait_for_service "NiFi" "https://localhost:8443/nifi/" || true
    wait_for_service "Backend" "http://localhost:8000/health" || true

    log_success "All services are running!"
    echo ""
    log_info "Access points:"
    log_info "  Backend API:    http://localhost:8000"
    log_info "  NiFi UI:        https://localhost:8443/nifi/ (admin/adminadmin123)"
    log_info "  Registry UI:    http://localhost:18080/nifi-registry/"
    log_info "  Database:       postgresql://postgres:postgres@localhost:5432/edi_lens"
    echo ""
    log_info "Next steps:"
    log_info "  ./scripts/backend.sh health    # Check service health"
    log_info "  ./scripts/backend.sh test unit # Run tests"
    log_info "  ./scripts/backend.sh logs      # View logs"
    echo ""
    log_info "Development mode: Hot reload is enabled. Changes to src/ will automatically restart the backend."
}

cmd_prod() {
    check_docker
    check_docker_compose

    log_step "Starting EDI Lens backend services in PRODUCTION mode..."

    cd "$DOCKER_DIR"
    load_project_env
    
    # Build containers first to ensure latest changes
    log_info "Building containers for production..."
    $DOCKER_COMPOSE -f docker-compose.yml -f docker-compose.prod.yml build
    
    $DOCKER_COMPOSE -f docker-compose.yml -f docker-compose.prod.yml up -d

    log_info "Services starting in background..."

    # Wait for key services
    if ! wait_for_container_healthy "edi-lens-db" 120; then
        log_error "Database failed to start within timeout"
        log_info "Showing recent database logs (last 200 lines):"
        docker logs --tail 200 edi-lens-db || true
    fi
    wait_for_service "Registry" "http://localhost:18080/nifi-registry-api/config" || true
    wait_for_service "NiFi" "https://localhost:8443/nifi/" || true
    wait_for_service "Backend" "http://localhost:8000/health" || true

    log_success "All services are running in PRODUCTION mode!"
    echo ""
    log_info "Access points:"
    log_info "  Backend API:    http://localhost:8000"
    log_info "  NiFi UI:        https://localhost:8443/nifi/ (admin/adminadmin123)"
    log_info "  Registry UI:    http://localhost:18080/nifi-registry/"
    log_info "  Database:       postgresql://postgres:postgres@localhost:5432/edi_lens"
    echo ""
    log_info "Production mode: Optimized for performance, no hot reload."
}

cmd_stop() {
    check_docker_compose

    log_step "Stopping EDI Lens backend services..."

    cd "$DOCKER_DIR"
    load_project_env
    $DOCKER_COMPOSE down

    log_success "All services stopped"
}

cmd_restart() {
    log_step "Restarting EDI Lens backend services..."
    cmd_stop
    sleep 2
    cmd_start
}

cmd_status() {
    check_docker

    log_step "Service status:"
    echo ""
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|edi-lens-)" || true
    echo ""

    # Quick health check
    log_info "Quick health check:"
    for service in "Backend:http://localhost:8000/health" "Registry:http://localhost:18080/nifi-registry-api/config" "NiFi:https://localhost:8443/nifi/"; do
        name="${service%%:*}"
        url="${service#*:}"
        if curl -s -k "$url" >/dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} $name"
        else
            echo -e "  ${RED}✗${NC} $name"
        fi
    done
}

cmd_logs() {
    check_docker_compose

    local service="${1:-}"
    cd "$DOCKER_DIR"
    load_project_env

    if [[ -n "$service" ]]; then
        log_info "Showing logs for: $service"
        $DOCKER_COMPOSE logs -f "$service"
    else
        log_info "Showing logs for all services (Ctrl+C to exit)"
        $DOCKER_COMPOSE logs -f
    fi
}

cmd_build() {
    check_docker_compose

    log_step "Building services..."

    cd "$DOCKER_DIR"
    load_project_env
    $DOCKER_COMPOSE build --no-cache

    log_success "Build complete"
}

cmd_clean() {
    check_docker_compose

    log_warn "This will remove all containers and volumes for the backend"
    local response=""
    if ! read -r -p "Are you sure? (y/N): " response; then
        echo
        log_warn "Input not received. Cleanup cancelled"
        return 1
    fi
    echo

    if [[ $response =~ ^[Yy]$ ]]; then
        log_step "Cleaning up backend containers and volumes..."

        cd "$DOCKER_DIR"
        load_project_env
        $DOCKER_COMPOSE down -v --remove-orphans

        # Remove images
        local image_ids
        image_ids=$(docker image ls --format '{{.Repository}} {{.ID}}' | awk '$1 ~ /edi-lens/ {print $2}')
        if [[ -n ${image_ids:-} ]]; then
            log_info "Removing backend images..."
            while IFS= read -r image_id; do
                [[ -n $image_id ]] && docker image rm -f "$image_id" >/dev/null 2>&1 || true
            done <<<"$image_ids"
        else
            log_info "No backend images to remove"
        fi

        log_success "Cleanup complete"
    else
        log_info "Cleanup cancelled"
    fi
}

cmd_shell() {
    check_docker

    if ! docker ps --format "{{.Names}}" | grep -q "^edi-lens-backend$"; then
        log_error "Backend container is not running. Start services with './scripts/backend.sh start'."
        exit 1
    fi

    log_info "Opening shell in backend container..."
    docker exec -it edi-lens-backend bash
}

cmd_setup() {
    check_backend_dir
    check_poetry

    log_step "Setting up development environment..."

    cd "$BACKEND_DIR"

    log_info "Installing Python dependencies..."
    poetry install

    log_info "Setting up pre-commit hooks..."
    poetry run pre-commit install || log_warn "Pre-commit hooks setup failed (optional)"

    log_success "Development environment ready!"
    log_info "Next steps:"
    log_info "  ./scripts/backend.sh start    # Start services"
    log_info "  ./scripts/backend.sh test     # Run tests"
}

cmd_test() {
    check_backend_dir
    check_poetry

    local test_type="${1:-all}"
    local -a extra_args=()
    if (( $# > 1 )); then
        extra_args=("${@:2}")
    fi
    cd "$BACKEND_DIR"

    log_step "Running $test_type tests..."

    # Load environment configuration from .env.local file for local testing
    local local_env_file="$PROJECT_ROOT/.env.local"
    if [[ -f "$local_env_file" ]]; then
        log_debug "Loading local environment variables from $local_env_file"
        set -a
        # shellcheck disable=SC1090
        source "$local_env_file"
        set +a
    else
        log_warn "Local environment file not found: $local_env_file"
        log_info "Using fallback localhost URLs for local testing"
        export NIFI_URL=https://localhost:8443
        export NIFI_REGISTRY_URL=http://localhost:18080
    fi

    case "$test_type" in
        unit)
            log_info "Running unit tests locally..."
            
            # Ensure virtualenv deps are installed
            if ! poetry run pytest --version >/dev/null 2>&1; then
                log_warn "pytest not found in the virtualenv. Installing dependencies with poetry..."
                poetry install --no-interaction || {
                    log_error "'poetry install' failed. Please check your environment or run 'poetry install' in $BACKEND_DIR"
                    exit 1
                }
            fi

            if (( ${#extra_args[@]} )); then
                poetry run pytest tests/unit/ -v "${extra_args[@]}"
            else
                poetry run pytest tests/unit/ -v
            fi
            ;;
        integration)
            log_info "Running integration tests locally..."
            log_info "Tests will connect to services using URLs from .env file"

            # Check if services are running
            if ! curl -s -k "${NIFI_URL:-https://localhost:8443}/nifi/" >/dev/null 2>&1; then
                log_warn "NiFi not reachable at ${NIFI_URL:-https://localhost:8443} - consider starting services first"
            fi
            if ! curl -s "${NIFI_REGISTRY_URL:-http://localhost:18080}/nifi-registry-api/config" >/dev/null 2>&1; then
                log_warn "Registry not reachable at ${NIFI_REGISTRY_URL:-http://localhost:18080} - consider starting services first"
            fi
            
            if (( ${#extra_args[@]} )); then
                poetry run pytest tests/integration/ -v "${extra_args[@]}"
            else
                poetry run pytest tests/integration/ -v
            fi
            ;;
        e2e)
            log_info "Running e2e tests locally..."
            log_info "Tests will connect to services using URLs from .env file"
            
            if (( ${#extra_args[@]} )); then
                poetry run pytest tests/e2e/ -v "${extra_args[@]}"
            else
                poetry run pytest tests/e2e/ -v
            fi
            ;;
        all)
            log_info "Running all tests locally..."
            
            log_info "Running unit tests..."
            poetry run pytest tests/unit/ -v
            
            log_info "Running integration tests..."
            if (( ${#extra_args[@]} )); then
                cmd_test integration "${extra_args[@]}"
            else
                cmd_test integration
            fi
            
            log_info "Running e2e tests..."
            if (( ${#extra_args[@]} )); then
                cmd_test e2e "${extra_args[@]}"
            else
                cmd_test e2e
            fi
            ;;
        watch)
            run_pytest_watch "${extra_args[@]:-}"
            ;;
        *)
            log_error "Unknown test type: $test_type"
            log_info "Available types: unit, integration, e2e, all, watch"
            exit 1
            ;;
    esac

    log_success "$test_type tests completed"
}

cmd_test_watch() {
    cmd_test watch
}

cmd_lint() {
    check_backend_dir
    check_poetry

    log_step "Running linters..."

    cd "$BACKEND_DIR"
    poetry run ruff check src/ tests/
    poetry run mypy src/

    log_success "Linting complete"
}

cmd_format() {
    check_backend_dir
    check_poetry

    log_step "Formatting code..."

    cd "$BACKEND_DIR"
    poetry run black src/ tests/
    poetry run isort src/ tests/
    poetry run ruff check --fix src/ tests/

    log_success "Code formatting complete"
}

cmd_health() {
    log_step "Checking service health..."
    echo ""

    # Check if services are running
    local services=("edi-lens-db" "edi-lens-registry" "edi-lens-nifi" "edi-lens-backend")
    local all_running=true

    for service in "${services[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^$service$"; then
            echo -e "  ${GREEN}✓${NC} $service (running)"
        else
            echo -e "  ${RED}✗${NC} $service (not running)"
            all_running=false
        fi
    done

    if [[ "$all_running" == "false" ]]; then
        echo ""
        log_warn "Some services are not running. Use './scripts/backend.sh start' to start them."
        return 1
    fi

    echo ""
    log_info "Checking service endpoints..."

    # Health check endpoints
    local endpoints=(
        "Backend API:http://localhost:8000/health"
        "NiFi Health:http://localhost:8000/health/nifi"
        "Registry Health:http://localhost:8000/health/registry"
        "NiFi UI:https://localhost:8443/nifi/"
        "Registry UI:http://localhost:18080/nifi-registry-api/config"
    )

    for endpoint in "${endpoints[@]}"; do
        name="${endpoint%%:*}"
        url="${endpoint#*:}"

        if curl -s -k "$url" >/dev/null 2>&1; then
            echo -e "  ${GREEN}✓${NC} $name"
        else
            echo -e "  ${RED}✗${NC} $name"
        fi
    done

    echo ""
    log_success "Health check complete"
}

cmd_debug() {
    log_step "Gathering debug information..."

    echo ""
    echo "=== Docker Info ==="
    docker version 2>/dev/null || echo "Docker not available"

    echo ""
    echo "=== Running Containers ==="
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|edi-lens-)" || true

    echo ""
    echo "=== Port Usage ==="
    show_port_usage ":(8000|8443|18080|5432)"

    echo ""
    echo "=== Service Health ==="
    cmd_health

    echo ""
    echo "=== Recent Backend Logs ==="
    docker logs edi-lens-backend --tail 10 2>/dev/null || echo "Backend container not running"
}

cmd_doctor() {
    log_step "Diagnosing common issues..."

    local issues_found=false

    # Check Docker
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running"
        issues_found=true
    else
        log_success "Docker is running"
    fi

    # Check ports
    local ports=(8000 8443 18080 5432)
    for port in "${ports[@]}"; do
        if is_port_in_use "$port"; then
            if docker ps --format "{{.Ports}}" | grep -q ":$port->"; then
                log_success "Port $port is used by Docker (expected)"
            else
                log_warn "Port $port is in use by another process"
                issues_found=true
            fi
        fi
    done

    # Check backend directory
    if [[ ! -d "$BACKEND_DIR/src" ]]; then
        log_error "Backend source directory not found"
        issues_found=true
    else
        log_success "Backend source directory exists"
    fi

    # Check Poetry
    if command -v poetry >/dev/null 2>&1; then
        log_success "Poetry is installed"
    else
        log_warn "Poetry is not installed (needed for local development)"
    fi

    if [[ "$issues_found" == "false" ]]; then
        log_success "No issues found!"
    else
        echo ""
        log_info "Common solutions:"
        log_info "  - Ensure Docker is running"
        log_info "  - Stop conflicting services on ports 8000, 8443, 18080, 5432"
        log_info "  - Install Poetry: https://python-poetry.org/docs/#installation"
    fi
}

# Main command dispatcher
main() {
    if [[ $# -eq 0 ]] || [[ "$1" == "help" ]] || [[ "$1" == "--help" ]]; then
        show_help
        exit 0
    fi

    local command="$1"
    shift

    case "$command" in
        start) cmd_start "$@" ;;
        dev) cmd_start "$@" ;;
        prod) cmd_prod "$@" ;;
        stop) cmd_stop "$@" ;;
        restart) cmd_restart "$@" ;;
        status) cmd_status "$@" ;;
        logs) cmd_logs "$@" ;;
        build) cmd_build "$@" ;;
        clean) cmd_clean "$@" ;;
        shell) cmd_shell "$@" ;;
        setup) cmd_setup "$@" ;;
        test) cmd_test "$@" ;;
        test:watch) cmd_test_watch "$@" ;;
        lint) cmd_lint "$@" ;;
        format) cmd_format "$@" ;;
        health) cmd_health "$@" ;;
        debug) cmd_debug "$@" ;;
        doctor) cmd_doctor "$@" ;;
        *)
            log_error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function
main "$@"