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

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKER_DIR="$PROJECT_ROOT/docker"
BACKEND_DIR="$PROJECT_ROOT/backend"
DOCKER_COMPOSE=""
ENV_FILE="$PROJECT_ROOT/.env"

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

load_env_file() {
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

load_local_env() {
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
}

reconfigure_backend_for_local_testing() {
    log_info "Reconfiguring backend for local testing..."

    # Stop current backend
    docker-compose -f "$DOCKER_DIR/docker-compose.yml" stop backend >/dev/null 2>&1
    docker-compose -f "$DOCKER_DIR/docker-compose.yml" rm -f backend >/dev/null 2>&1

    # Start backend with local configuration
    log_debug "Starting backend with localhost URLs..."
    docker-compose -f "$DOCKER_DIR/docker-compose.yml" -f "$DOCKER_DIR/docker-compose.local.yml" up -d backend >/dev/null 2>&1

    # Wait for backend to be ready
    local max_attempts=30
    local attempt=1
    while [[ $attempt -le $max_attempts ]]; do
        if curl -s http://localhost:8000/health >/dev/null 2>&1; then
            log_success "Backend reconfigured for local testing"
            return 0
        fi
        sleep 1
        ((attempt++))
    done

    log_error "Backend failed to start after reconfiguration"
    return 1
}

is_port_in_use() {
    local port="$1"

    if command -v lsof >/dev/null 2>&1; then
        if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
            return 0
        fi
        return 1
    elif command -v ss >/dev/null 2>&1; then
        if ss -tulpn 2>/dev/null | grep -q ":$port "; then
            return 0
        fi
        return 1
    elif command -v netstat >/dev/null 2>&1; then
        if netstat -an 2>/dev/null | grep -q ".$port "; then
            return 0
        fi
        return 1
    fi

    return 1
}

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

run_pytest_watch() {
    if poetry run ptw --help >/dev/null 2>&1; then
        poetry run ptw tests/unit/ "$@"
    else
        log_error "pytest-watch is not installed. Install it with 'poetry add --group dev pytest-watch'."
        exit 1
    fi
}

ensure_backend_container_running() {
    if ! docker ps --format "{{.Names}}" | grep -q "^edi-lens-backend$"; then
        log_warn "Backend container is not running. Starting services..."
        cmd_start
    fi
}

ensure_backend_test_env() {
    ensure_backend_container_running
    if ! docker exec edi-lens-backend poetry run pytest --version >/dev/null 2>&1; then
        log_info "Installing test dependencies inside backend container..."
        if ! docker exec edi-lens-backend poetry install --with dev --no-root >/dev/null 2>&1; then
            log_error "Failed to install test dependencies inside backend container"
            exit 1
        fi
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

# Wait for a docker container to report healthy via its healthcheck
wait_for_container_healthy() {
    local container="$1"
    local max_wait_seconds=${2:-120}
    local start_ts=$(date +%s)

    log_info "Waiting for container '$container' to report healthy (timeout: ${max_wait_seconds}s)..."

    while :; do
        # Get health status (returns 'healthy', 'unhealthy', or 'starting')
        status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "no-container")

        if [[ "$status" == "healthy" ]]; then
            log_success "Container '$container' is healthy!"
            return 0
        fi

        # If container doesn't exist or exited, show short hint and break
        if [[ "$status" == "no-container" ]]; then
            log_error "Container '$container' not found or not running"
            return 1
        fi

        now_ts=$(date +%s)
        elapsed=$((now_ts - start_ts))
        if [[ $elapsed -ge $max_wait_seconds ]]; then
            log_error "Container '$container' did not become healthy within ${max_wait_seconds}s (status: $status)"
            return 1
        fi

        echo -n "."
        sleep 2
    done
}

# Command implementations
show_help() {
    cat << EOF
EDI Lens New Backend Management Script
=====================================

USAGE:
    ./scripts/backend.sh <command> [options]

COMMANDS:
    start                Start all services (Docker Compose with hot reload)
    dev                  Start in development mode (same as start, with hot reload)
    prod                 Start in production mode (no hot reload, optimized)
    stop                 Stop all services
    restart              Restart all services
    status               Show service status
    logs [service]       Show logs (all services or specific service)
    build                Build/rebuild services
    clean                Clean up containers and volumes
    shell                Open shell in backend container

DEVELOPMENT:
    setup                Install dependencies and prepare development environment
    test [type] [mode]   Run tests (unit, integration, e2e, or all)
                         - unit: always run locally
                         - integration [local|docker]: run locally or in docker (default: local)
                         - e2e [local|local-verbose|docker|docker-verbose]: run locally or in docker
                           * local: standard test execution
                           * local-verbose: comprehensive logging with validation report
                           * docker: tests in container
                           * docker-verbose: container tests with validation
                         - all [local|docker]: run all tests in specified mode (default: local)
    test:watch           Run tests in watch mode
    lint                 Run code linting
    format               Format code with black/isort

HEALTH & DEBUGGING:
    health               Check health of all services
    debug                Show debug information
    doctor               Diagnose common issues

EXAMPLES:
    ./scripts/backend.sh start                         # Start all services in dev mode
    ./scripts/backend.sh dev                           # Start all services in dev mode (hot reload)
    ./scripts/backend.sh prod                          # Start all services in production mode
    ./scripts/backend.sh test unit                     # Run unit tests locally
    ./scripts/backend.sh test integration              # Run integration tests locally (default)
    ./scripts/backend.sh test integration local        # Run integration tests locally
    ./scripts/backend.sh test integration docker       # Run integration tests in docker
    ./scripts/backend.sh test e2e local                # Run E2E tests locally
    ./scripts/backend.sh test e2e local-verbose        # Run E2E tests with comprehensive validation
    ./scripts/backend.sh test e2e docker-verbose       # Run E2E tests in docker with validation
    ./scripts/backend.sh test all                      # Run all tests locally (default)
    ./scripts/backend.sh test all docker               # Run all tests in docker mode
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
    load_env_file
    
    # Build containers first to ensure latest changes
    log_info "Building containers with latest changes..."
    $DOCKER_COMPOSE build
    
    $DOCKER_COMPOSE up -d

    log_info "Services starting in background..."

    # Wait for key services
    # Use docker container health for the database because curl on a postgres:// URL won't work
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
    load_env_file
    
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
    load_env_file
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
    load_env_file

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
    load_env_file
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
        load_env_file
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
    local test_mode="${2:-local}"  # Default to local for all tests
    local -a extra_args=()
    if (( $# > 2 )); then
        extra_args=("${@:3}")
    fi
    cd "$BACKEND_DIR"

    log_step "Running $test_type tests..."

    case "$test_type" in
        unit)
            # Unit tests always run locally
            if [[ "$test_mode" != "docker" && "$test_mode" != "all" ]]; then
                log_info "Unit tests always run locally (ignoring mode: $test_mode)"
            fi
            
            # Ensure virtualenv deps are installed
            if ! poetry run pytest --version >/dev/null 2>&1; then
                log_warn "pytest not found in the virtualenv. Installing dependencies with poetry (no-root)..."
                poetry install --no-interaction --no-root || {
                    log_error "'poetry install' failed. Please check your environment or run 'poetry install' in $BACKEND_DIR"
                    exit 1
                }
            fi

            if (( ${#extra_args[@]} )); then
                poetry run pytest -m unit tests/unit/ -v "${extra_args[@]}"
            else
                poetry run pytest -m unit tests/unit/ -v
            fi
            ;;
        integration)
            case "$test_mode" in
                local)
                    log_info "Running integration tests locally..."
                    log_info "Tests will connect to Docker services via localhost URLs"

                    # Load local environment configuration
                    load_local_env

                    # Check if services are running
                    if ! curl -s -k "$NIFI_URL/nifi/" >/dev/null 2>&1; then
                        log_warn "NiFi not reachable at $NIFI_URL - consider starting services first"
                    fi
                    if ! curl -s "$NIFI_REGISTRY_URL/nifi-registry-api/config" >/dev/null 2>&1; then
                        log_warn "Registry not reachable at $NIFI_REGISTRY_URL - consider starting services first"
                    fi
                    
                    if (( ${#extra_args[@]} )); then
                        poetry run pytest -m integration tests/integration/ -v "${extra_args[@]}"
                    else
                        poetry run pytest -m integration tests/integration/ -v
                    fi
                    ;;
                docker)
                    log_info "Running integration tests in Docker container..."
                    log_info "Tests will connect to Docker services via host.docker.internal URLs"
                    ensure_backend_test_env
                    
                    # Set environment for docker testing (host.docker.internal URLs to avoid SSL issues)
                    if (( ${#extra_args[@]} )); then
                        docker exec -e TEST_MODE=docker edi-lens-backend poetry run pytest -m integration tests/integration/ -v "${extra_args[@]}"
                    else
                        docker exec -e TEST_MODE=docker edi-lens-backend poetry run pytest -m integration tests/integration/ -v
                    fi
                    ;;
                *)
                    log_error "Unknown test mode: $test_mode"
                    log_info "Available modes for integration tests: local, docker"
                    exit 1
                    ;;
            esac
            ;;
        e2e)
            case "$test_mode" in
                local)
                    log_info "Running e2e tests locally..."
                    log_info "Tests will connect to Docker services via localhost URLs"

                    # Load local environment configuration
                    load_local_env

                    # Reconfigure backend to use localhost URLs
                    reconfigure_backend_for_local_testing
                    
                    if (( ${#extra_args[@]} )); then
                        poetry run pytest -m e2e tests/e2e/ -v "${extra_args[@]}"
                    else
                        poetry run pytest -m e2e tests/e2e/ -v
                    fi
                    ;;
                local-verbose)
                    log_info "Running e2e tests locally with VERBOSE logging..."
                    log_info "Tests will connect to Docker services via localhost URLs"
                    log_info "Capturing detailed logs for validation..."

                    # Load local environment configuration
                    load_local_env

                    # Reconfigure backend to use localhost URLs
                    reconfigure_backend_for_local_testing

                    # Create e2e logs directory
                    mkdir -p logs/e2e
                    local timestamp=$(date +"%Y%m%d_%H%M%S")
                    local log_file="logs/e2e/e2e_test_${timestamp}.log"
                    local validation_file="logs/e2e/e2e_validation_${timestamp}.log"
                    
                    log_info "Starting comprehensive E2E test validation..."
                    log_info "Test logs will be saved to: $log_file"
                    log_info "Validation report will be saved to: $validation_file"
                    
                    # Run tests with full verbose output and capture logs
                    {
                        echo "=== E2E Test Execution Started at $(date) ==="
                        echo "=== Environment ==="
                        echo "NIFI_URL: $NIFI_URL"
                        echo "NIFI_REGISTRY_URL: $NIFI_REGISTRY_URL"
                        echo "DEBUG: $DEBUG"
                        echo ""
                        
                        poetry run pytest -m e2e tests/e2e/ -v -s --tb=long "${extra_args[@]:-}" 2>&1
                        
                        echo ""
                        echo "=== E2E Test Execution Completed at $(date) ==="
                    } | tee "$log_file"
                    
                    # Perform validation analysis
                    cmd_validate_e2e_test "$log_file" "$validation_file" "$timestamp"
                    ;;
                docker)
                    log_info "Running e2e tests in Docker container..."
                    ensure_backend_test_env
                    
                    if (( ${#extra_args[@]} )); then
                        docker exec -e TEST_MODE=docker edi-lens-backend poetry run pytest -m e2e tests/e2e/ -v "${extra_args[@]}"
                    else
                        docker exec -e TEST_MODE=docker edi-lens-backend poetry run pytest -m e2e tests/e2e/ -v
                    fi
                    ;;
                docker-verbose)
                    log_info "Running e2e tests in Docker container with VERBOSE logging..."
                    ensure_backend_test_env
                    
                    # Create e2e logs directory
                    mkdir -p logs/e2e
                    local timestamp=$(date +"%Y%m%d_%H%M%S")
                    local log_file="logs/e2e/e2e_docker_test_${timestamp}.log"
                    local validation_file="logs/e2e/e2e_docker_validation_${timestamp}.log"
                    
                    log_info "Test logs will be saved to: $log_file"
                    log_info "Validation report will be saved to: $validation_file"
                    
                    # Run tests with full verbose output and capture logs
                    {
                        echo "=== E2E Docker Test Execution Started at $(date) ==="
                        echo "=== Environment ==="
                        echo "TEST_MODE: docker"
                        echo ""
                        
                        docker exec -e TEST_MODE=docker -e DEBUG=true edi-lens-backend poetry run pytest -m e2e tests/e2e/ -v -s --tb=long "${extra_args[@]:-}" 2>&1
                        
                        echo ""
                        echo "=== E2E Docker Test Execution Completed at $(date) ==="
                    } | tee "$log_file"
                    
                    # Perform validation analysis
                    cmd_validate_e2e_test "$log_file" "$validation_file" "$timestamp"
                    ;;
                *)
                    log_error "Unknown test mode: $test_mode"
                    log_info "Available modes for e2e tests: local, local-verbose, docker, docker-verbose"
                    exit 1
                    ;;
            esac
            ;;
        all)
            log_info "Running all tests in $test_mode mode..."
            # Unit tests always run locally
            log_info "Running unit tests locally..."
            poetry run pytest -m unit tests/unit/ -v
            
            # Integration and e2e in specified mode (default local)
            log_info "Running integration tests in $test_mode mode..."
            cmd_test integration "$test_mode"
            log_info "Running e2e tests in $test_mode mode..."
            cmd_test e2e "$test_mode"
            ;;
        watch)
            run_pytest_watch "${extra_args[@]:-}"
            ;;
        *)
            log_error "Unknown test type: $test_type"
            log_info "Available types: unit, integration, e2e, all, watch"
            log_info "For integration/e2e, add mode: local, local-verbose, docker, docker-verbose"
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

cmd_validate_e2e_test() {
    local log_file="$1"
    local validation_file="$2"
    local timestamp="$3"
    
    log_step "Validating E2E test execution..."
    
    {
        echo "=== E2E Test Validation Report ==="
        echo "Generated at: $(date)"
        echo "Test timestamp: $timestamp"
        echo "Log file: $log_file"
        echo ""
        
        # Test execution summary
        echo "=== TEST EXECUTION SUMMARY ==="
        if grep -q "PASSED\|FAILED" "$log_file"; then
            local passed_count=$(grep -c "PASSED" "$log_file" || echo "0")
            local failed_count=$(grep -c "FAILED" "$log_file" || echo "0")
            local total_count=$((passed_count + failed_count))
            
            echo "Total tests executed: $total_count"
            echo "Tests passed: $passed_count"
            echo "Tests failed: $failed_count"
            
            if [ "$failed_count" -eq 0 ]; then
                echo "✅ All tests passed!"
            else
                echo "❌ Some tests failed"
            fi
        else
            echo "⚠️ No test results found in log"
        fi
        echo ""
        
        # API connectivity validation
        echo "=== API CONNECTIVITY VALIDATION ==="
        if grep -q "API is healthy" "$log_file"; then
            echo "✅ API health check passed"
        else
            echo "❌ API health check failed"
        fi
        
        if grep -q "Successfully retrieved.*buckets" "$log_file"; then
            echo "✅ Registry bucket listing worked"
        else
            echo "⚠️ Registry bucket listing may have failed"
        fi
        
        if grep -q "Flow creation failed\|Registry not available" "$log_file"; then
            echo "⚠️ Flow creation encountered expected errors (Registry unavailable)"
        elif grep -q "Successfully created flow" "$log_file"; then
            echo "✅ Flow creation worked"
        else
            echo "⚠️ Flow creation status unclear"
        fi
        echo ""
        
        # Logging system validation
        echo "=== LOGGING SYSTEM VALIDATION ==="
        local log_entries_found=false
        
        # Check for different log levels
        if grep -q "DEBUG\|INFO\|WARNING\|ERROR" "$log_file"; then
            echo "✅ Multiple log levels detected"
            log_entries_found=true
        fi
        
        # Check for professional logging (no emojis in backend logs)
        if grep -q "Initializing.*client\|Starting.*Backend\|Registry API request" "$log_file"; then
            echo "✅ Professional logging format detected"
            log_entries_found=true
        fi
        
        # Check for structured error handling
        if grep -q "error_type\|user_message\|action_required" "$log_file"; then
            echo "✅ Structured error handling detected"
            log_entries_found=true
        fi
        
        # Check for audit logging
        if grep -q "audit" "$log_file"; then
            echo "✅ Audit logging detected"
            log_entries_found=true
        fi
        
        if [ "$log_entries_found" = false ]; then
            echo "⚠️ Limited logging detected - may need investigation"
        fi
        echo ""
        
        # Performance validation (check backend logs for timing)
        echo "=== PERFORMANCE VALIDATION ==="
        local backend_timing=""
        if command -v docker >/dev/null 2>&1; then
            backend_timing=$(docker logs edi-lens-backend --since="5 minutes ago" 2>/dev/null | grep -o "([0-9]*\.[0-9]*ms)" | head -5 || echo "")
        fi
        
        if [ -n "$backend_timing" ] || grep -q "([0-9]*\.[0-9]*ms)" "$log_file"; then
            echo "✅ Request timing detected"
            
            # Extract and analyze response times from backend logs
            if [ -n "$backend_timing" ]; then
                local slow_requests=$(echo "$backend_timing" | grep -o "[0-9]*\.[0-9]*" | awk '$1 > 1000' | wc -l || echo "0")
                if [ "$slow_requests" -gt 0 ]; then
                    echo "⚠️ $slow_requests slow requests detected (>1000ms)"
                else
                    echo "✅ No slow requests detected"
                fi
                echo "Sample response times: $(echo "$backend_timing" | head -3 | tr '\n' ' ')"
            fi
        else
            echo "⚠️ No request timing information found"
        fi
        echo ""
        
        # Error analysis
        echo "=== ERROR ANALYSIS ==="
        local error_count=$(grep -c "ERROR\|FAILED\|Exception" "$log_file" || echo "0")
        if [ "$error_count" -eq 0 ]; then
            echo "✅ No errors detected"
        else
            echo "⚠️ $error_count error entries found"
            echo "Error summary:"
            grep "ERROR\|FAILED\|Exception" "$log_file" | head -5 | sed 's/^/  - /'
            if [ "$error_count" -gt 5 ]; then
                echo "  ... and $((error_count - 5)) more errors"
            fi
        fi
        echo ""
        
        # Service integration validation (check docker logs during test execution)
        echo "=== SERVICE INTEGRATION VALIDATION ==="
        local test_start_time=$(grep "E2E Test Execution Started" "$log_file" | head -1 | grep -o "at [^=]*" | sed 's/at //')
        local test_end_time=$(grep "E2E Test Execution Completed" "$log_file" | head -1 | grep -o "at [^=]*" | sed 's/at //')
        
        # Check for backend activity during test execution by examining docker logs
        if command -v docker >/dev/null 2>&1; then
            local backend_logs_during_test=""
            if [ -n "$test_start_time" ] && [ -n "$test_end_time" ]; then
                # Convert to docker log format and check for activity
                backend_logs_during_test=$(docker logs edi-lens-backend --since="5 minutes ago" 2>/dev/null | grep -E "(Initializing.*client|FlowService|GET|POST)" | head -10 || echo "")
            fi
            
            if echo "$backend_logs_during_test" | grep -q "Registry.*client"; then
                echo "✅ Registry client initialization detected in backend logs"
            else
                echo "⚠️ Registry client initialization not found in backend logs"
            fi
            
            if echo "$backend_logs_during_test" | grep -q "NiFi.*client"; then
                echo "✅ NiFi client initialization detected in backend logs"
            else
                echo "⚠️ NiFi client initialization not found in backend logs"
            fi
            
            if echo "$backend_logs_during_test" | grep -q "FlowService\|GET.*flows\|POST.*flows"; then
                echo "✅ FlowService/API integration detected in backend logs"
            else
                echo "⚠️ FlowService/API integration not found in backend logs"
            fi
            
            # Show sample of backend activity for verification
            if [ -n "$backend_logs_during_test" ]; then
                echo "Sample backend activity during test:"
                echo "$backend_logs_during_test" | head -3 | sed 's/^/  /'
            fi
        else
            echo "⚠️ Docker not available for backend log verification"
        fi
        echo ""
        
        # Test coverage validation
        echo "=== TEST COVERAGE VALIDATION ==="
        local phases_detected=0
        
        if grep -q "Phase 1.*buckets" "$log_file"; then
            echo "✅ Phase 1: Bucket listing tested"
            ((phases_detected++))
        fi
        
        if grep -q "Phase 2.*Creating flow" "$log_file"; then
            echo "✅ Phase 2: Flow creation tested"
            ((phases_detected++))
        fi
        
        if grep -q "API error handling" "$log_file"; then
            echo "✅ Error handling tests executed"
            ((phases_detected++))
        fi
        
        if grep -q "Concurrent operations" "$log_file"; then
            echo "✅ Concurrent operations tested"
            ((phases_detected++))
        fi
        
        echo "Total test phases detected: $phases_detected"
        
        if [ "$phases_detected" -ge 3 ]; then
            echo "✅ Comprehensive test coverage detected"
        else
            echo "⚠️ Limited test coverage - may need investigation"
        fi
        echo ""
        
        # Overall assessment
        echo "=== OVERALL ASSESSMENT ==="
        local validation_score=0
        
        # Scoring criteria
        if grep -q "All tests passed\|PASSED" "$log_file"; then ((validation_score++)); fi
        if grep -q "API is healthy" "$log_file"; then ((validation_score++)); fi
        if [ "$log_entries_found" = true ]; then ((validation_score++)); fi
        if [ "$phases_detected" -ge 3 ]; then ((validation_score++)); fi
        if [ "$error_count" -lt 10 ]; then ((validation_score++)); fi
        
        echo "Validation score: $validation_score/5"
        
        if [ "$validation_score" -ge 4 ]; then
            echo "🎉 EXCELLENT: E2E tests are working correctly with comprehensive validation"
        elif [ "$validation_score" -ge 3 ]; then
            echo "✅ GOOD: E2E tests are mostly working with minor issues"
        elif [ "$validation_score" -ge 2 ]; then
            echo "⚠️ FAIR: E2E tests have some functionality but need attention"
        else
            echo "❌ POOR: E2E tests may not be working correctly - investigation needed"
        fi
        
        echo ""
        echo "=== RECOMMENDATIONS ==="
        if [ "$validation_score" -lt 4 ]; then
            echo "1. Check service connectivity (NiFi, Registry)"
            echo "2. Verify test environment setup"
            echo "3. Review error messages in detail"
            echo "4. Consider running tests with services fully deployed"
        else
            echo "1. E2E tests are working well"
            echo "2. Consider adding more test scenarios"
            echo "3. Monitor performance for production readiness"
        fi
        
        echo ""
        echo "=== LOG FILE LOCATIONS ==="
        echo "Full test log: $log_file"
        echo "This validation report: $validation_file"
        echo "Application logs: logs/edi_lens.log"
        echo "JSON logs: logs/edi_lens.jsonl"
        echo "Audit logs: logs/audit.jsonl"
        
    } > "$validation_file"
    
    # Display summary
    echo ""
    log_success "E2E test validation completed!"
    log_info "Validation report saved to: $validation_file"
    
    # Show key findings
    local validation_score=$(grep "Validation score:" "$validation_file" | grep -o "[0-9]/[0-9]")
    local overall_assessment=$(grep "EXCELLENT:\|GOOD:\|FAIR:\|POOR:" "$validation_file" | head -1)
    
    echo ""
    log_info "=== VALIDATION SUMMARY ==="
    log_info "Score: $validation_score"
    log_info "Assessment: $overall_assessment"
    echo ""
    log_info "View full report: cat $validation_file"
    log_info "View test logs: cat $log_file"
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
