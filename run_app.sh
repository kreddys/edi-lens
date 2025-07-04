#!/bin/bash

# ==============================================================================
# Utility Script for the EDI Lens Project
#
# Description:
# This script provides essential commands to manage the Docker-based
# development environment. It handles dynamic configuration generation
# and service orchestration.
# ==============================================================================

# --- Configuration ---
# Color definitions for better readability
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Helper Functions ---
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

# --- SCRIPT INITIALIZATION ---
# Source the .env file to make variables available for substitution in docker-compose
if [ -f .env ]; then
    info "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
else
    error ".env file not found. Please create one from .env.example."
fi

# --- Main Functions ---

# Prepares Keycloak config by running the Python script to inject secrets
prepare_kc_config() {
    info "Preparing Keycloak configuration from template..."
    if ! command -v "python3" &> /dev/null; then
        error "'python3' command not found. Please install it."
    fi
    python3 scripts/prepare_keycloak_config.py
    if [ $? -ne 0 ]; then
        error "Failed to prepare Keycloak configuration. Aborting."
    fi
}

# Displays the help message
usage() {
    echo "EDI Lens Project Management Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Available Commands:"
    echo "  start           Build images and start all services in the background. (Default)"
    echo "  start:clean     Permanently delete all volumes and data, then start all services."
    echo "  stop            Stop and remove all running services and networks."
    echo "  logs            Follow the logs of all running services."
    echo "  build           Force a rebuild of all service images without starting them."
    echo "  test:backend    Run unit tests with a temporary test database."
    echo "  test:integration Run integration tests against live services."
    echo "  -h, --help      Display this help message."
    echo ""
}

# Starts all services in detached mode
start_app() {
    prepare_kc_config
    info "Building images and starting all services..."
    docker-compose up --build -d
    success "All services are starting. Use './run_app.sh logs' or 'docker-compose ps' to check status."
}

# Stops and removes all services
stop_app() {
    info "Stopping and removing all services and the network..."
    docker-compose down
    success "All services have been stopped."
}

# Follows logs for all services
follow_logs() {
    info "Following logs for all services. Press Ctrl+C to exit."
    docker-compose logs -f
}

# Builds images for all services
build_images() {
    info "Building all service images..."
    docker-compose build
    success "Image build complete."
}

# Runs unit tests with a temporary database
run_backend_tests() {
    info "Preparing for backend unit tests..."
    prepare_kc_config

    info "Starting dependency services (db, keycloak)..."
    docker-compose up -d db keycloak

    info "(1/3) Dropping old test database (if it exists)..."
    docker-compose run --rm backend python -m tests.manage_test_db drop
    
    info "(2/3) Creating new test database..."
    docker-compose run --rm backend python -m tests.manage_test_db create
    if [ $? -ne 0 ]; then
        error "Failed to create the test database. Aborting tests."
    fi

    info "(3/3) Executing pytest for unit tests (tests not marked 'integration')..."
    # Use the service name 'backend', which docker-compose understands
    docker-compose run --rm --service-ports backend pytest -m "not integration"
    
    TEST_EXIT_CODE=$?
    info "Unit tests complete. Stopping dependency services..."
    docker-compose stop db keycloak
    exit $TEST_EXIT_CODE
}

# Runs integration tests against the live stack
run_integration_tests() {
    info "Preparing to run INTEGRATION tests..."
    
    # 1. Start all services required for the integration test
    info "(1/3) Starting all services..."
    start_app
    
    # Give Docker a moment to start creating the containers
    info "Waiting for containers to initialize..."
    sleep 5

    # 2. Wait for the backend to become healthy before running tests
    info "(2/3) Waiting for the backend service to be healthy..."
    
    TIMEOUT=120 # 2 minutes
    INTERVAL=5
    ELAPSED=0

    # This loop is now robust and does not use a hardcoded container name
    while true; do
        # Get the container ID using the SERVICE name ('backend')
        BACKEND_CONTAINER_ID=$(docker-compose ps -q backend)
        
        # Check if the container object exists yet
        if [ -z "$BACKEND_CONTAINER_ID" ]; then
            STATUS="creating"
        else
            # If it exists, get its health status using its ID
            STATUS=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}starting{{end}}' "$BACKEND_CONTAINER_ID" 2>/dev/null)
        fi

        if [ "$STATUS" == "healthy" ]; then
            success "Backend service is healthy."
            break # Exit the loop
        fi

        if [ $ELAPSED -ge $TIMEOUT ]; then
            error "Timeout waiting for backend service to become healthy. Check 'docker-compose logs backend'."
        fi
        
        info "Backend is not healthy yet (Status: $STATUS). Waiting ${INTERVAL}s..."
        sleep $INTERVAL
        ELAPSED=$((ELAPSED + INTERVAL))
    done

    # 3. Run only the tests marked with 'integration'
    info "(3/3) Executing pytest for integration tests..."
    # Use the SERVICE name 'backend' to execute the command. This is correct.
    docker-compose exec backend pytest -m integration
    
    TEST_EXIT_CODE=$?

    info "Integration tests complete. Stopping all services."
    stop_app
    
    exit $TEST_EXIT_CODE
}

# --- Script Execution ---
if ! command -v "docker" &> /dev/null; then
    error "'docker' command not found. Please install it to continue."
fi
if ! command -v "docker-compose" &> /dev/null; then
    error "'docker-compose' command not found. Please install it to continue."
fi

COMMAND=$1
case "$COMMAND" in
    start) start_app ;;
    start:clean) start_clean_app ;;
    stop) stop_app ;;
    logs) follow_logs ;;
    build) build_images ;;
    test:backend) run_backend_tests ;;
    test:integration) run_integration_tests ;;
    -h|--help) usage ;;
    "")
        info "No command specified. Defaulting to 'start'."
        start_app
        ;;
    *)
        error "Invalid command: '$COMMAND'\nRun './run_app.sh --help' for available commands."
        ;;
esac