#!/bin/bash
# ==============================================================================
# EDI Lens New Backend Management Script
# ==============================================================================
# Simple, focused script for the new backend architecture
# Usage: ./scripts/backend.sh [command] [options]
#
# Philosophy: Simple, predictable, fast
# - Single responsibility: manage the new backend only
# - Clear commands with intuitive names
# - Fast feedback and helpful error messages
# - No complex environment abstractions
# ==============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKER_DIR="$PROJECT_ROOT/docker"
BACKEND_DIR="$PROJECT_ROOT/backend"

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

# Utility functions
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
}

check_docker_compose() {
    if command -v "docker-compose" >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker-compose"
    elif docker compose version >/dev/null 2>&1; then
        DOCKER_COMPOSE="docker compose"
    else
        log_error "Neither 'docker-compose' nor 'docker compose' is available."
        exit 1
    fi
}

check_backend_dir() {
    if [[ ! -d "$BACKEND_DIR" ]]; then
        log_error "Backend directory not found at $BACKEND_DIR"
        exit 1
    fi
}

check_poetry() {
    if ! command -v poetry >/dev/null 2>&1; then
        log_error "Poetry is not installed. Please install it first: https://python-poetry.org/docs/#installation"
        exit 1
    fi
}

wait_for_service() {
    local service_name="$1"
    local url="$2"
    local max_attempts=30
    local attempt=1

    log_info "Waiting for $service_name to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if curl -s -k "$url" >/dev/null 2>&1; then
            log_success "$service_name is ready!"
            return 0
        fi

        echo -n "."
        sleep 2
        ((attempt++))
    done

    echo ""
    log_error "$service_name failed to start within $((max_attempts * 2)) seconds"
    return 1
}

# Command implementations
show_help() {
    cat << EOF
EDI Lens New Backend Management Script
=====================================

USAGE:
    ./scripts/backend.sh <command> [options]

COMMANDS:
    start                Start all services (Docker Compose)
    stop                 Stop all services
    restart              Restart all services
    status               Show service status
    logs [service]       Show logs (all services or specific service)
    build                Build/rebuild services
    clean                Clean up containers and volumes
    shell                Open shell in backend container

DEVELOPMENT:
    setup                Install dependencies and prepare development environment
    test [type]          Run tests (unit, integration, e2e, or all)
    test:watch           Run tests in watch mode
    lint                 Run code linting
    format               Format code with black/isort

HEALTH & DEBUGGING:
    health               Check health of all services
    debug                Show debug information
    doctor               Diagnose common issues

EXAMPLES:
    ./scripts/backend.sh start              # Start all services
    ./scripts/backend.sh test unit          # Run unit tests
    ./scripts/backend.sh logs backend       # Show backend logs
    ./scripts/backend.sh health             # Check service health

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
    $DOCKER_COMPOSE up -d

    log_info "Services starting in background..."

    # Wait for key services
    wait_for_service "Database" "postgresql://postgres:postgres@localhost:5432/edi_lens" || true
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
}

cmd_stop() {
    check_docker_compose

    log_step "Stopping EDI Lens backend services..."

    cd "$DOCKER_DIR"
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
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|edi-lens-)"
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
    $DOCKER_COMPOSE build --no-cache

    log_success "Build complete"
}

cmd_clean() {
    check_docker_compose

    log_warn "This will remove all containers and volumes for the backend"
    read -p "Are you sure? (y/N): " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_step "Cleaning up backend containers and volumes..."

        cd "$DOCKER_DIR"
        $DOCKER_COMPOSE down -v --remove-orphans

        # Remove images
        docker images | grep -E "(edi-lens|docker)" | awk '{print $3}' | xargs -r docker rmi -f || true

        log_success "Cleanup complete"
    else
        log_info "Cleanup cancelled"
    fi
}

cmd_shell() {
    check_docker

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
    cd "$BACKEND_DIR"

    log_step "Running $test_type tests..."

    case "$test_type" in
        unit)
            poetry run pytest tests/unit/ -v "${@:2}"
            ;;
        integration)
            log_info "Ensuring services are running for integration tests..."
            if ! curl -s http://localhost:8000/health >/dev/null 2>&1; then
                log_warn "Backend not running. Starting services..."
                cmd_start
            fi
            poetry run pytest tests/integration/ -v "${@:2}"
            ;;
        e2e)
            log_info "Ensuring services are running for e2e tests..."
            if ! curl -s http://localhost:8000/health >/dev/null 2>&1; then
                log_warn "Backend not running. Starting services..."
                cmd_start
            fi
            poetry run pytest tests/e2e/ -v "${@:2}"
            ;;
        all)
            log_info "Running all tests..."
            poetry run pytest tests/unit/ -v
            if curl -s http://localhost:8000/health >/dev/null 2>&1; then
                poetry run pytest tests/integration/ -v
                poetry run pytest tests/e2e/ -v
            else
                log_warn "Services not running. Skipping integration and e2e tests."
                log_info "Run './scripts/backend.sh start' first to run all tests."
            fi
            ;;
        watch)
            poetry run pytest tests/unit/ -v --watch
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
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep -E "(NAMES|edi-lens-)"

    echo ""
    echo "=== Port Usage ==="
    netstat -tulpn 2>/dev/null | grep -E ":(8000|8443|18080|5432)" || echo "netstat not available"

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
        if netstat -tuln 2>/dev/null | grep -q ":$port "; then
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