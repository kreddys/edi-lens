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
        error "'python3' command not found. Please install it to run the config script."
    fi
    # Run the Python script to generate the final realm-export.json
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
    echo "  start         Build images and start all services in the background. (Default)"
    echo "  start:clean   Permanently delete all volumes and data, then start all services."
    echo "  stop          Stop and remove all running services and networks."
    echo "  logs          Follow the logs of all running services."
    echo "  build         Force a rebuild of all service images without starting them."
    echo "  test:backend  Re-creates the test database and runs all backend tests."
    echo "  -h, --help    Display this help message."
    echo ""
}

# Starts all services in detached mode
start_app() {
    prepare_kc_config # Run the config prep script before starting services
    info "Building images and starting all services (db, backend, keycloak, frontend)..."
    docker-compose up --build -d
    success "All services are starting in the background. Use './run_app.sh logs' or 'docker-compose ps' to check status."
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

# Runs backend tests with a fresh database
run_backend_tests() {
    info "Preparing for backend tests..."
    prepare_kc_config # Also run before tests, in case config is needed

    info "Starting dependency services (db, keycloak)..."
    docker-compose up -d db keycloak

    info "(1/3) Dropping old test database (if it exists)..."
    docker-compose run --rm backend python -m tests.manage_test_db drop
    
    info "(2/3) Creating new test database..."
    docker-compose run --rm backend python -m tests.manage_test_db create
    if [ $? -ne 0 ]; then
        error "Failed to create the test database. Aborting tests."
    fi

    info "(3/3) Executing pytest..."
    docker-compose run --rm --service-ports backend pytest
    
    # Store the exit code of the tests
    TEST_EXIT_CODE=$?

    info "Tests complete. Stopping dependency services..."
    docker-compose stop db keycloak

    # Exit with the same code as pytest
    exit $TEST_EXIT_CODE
}

# Deletes all data and starts fresh
start_clean_app() {
    warn "This will permanently delete the main database and all other service volumes."
    read -p "Are you sure you want to continue? (y/N): " -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "Proceeding with clean start..."
        # Stop any running containers and remove all associated volumes
        docker-compose down -v
        # The postgres-data directory is host-mounted, so it must be removed manually
        if [ -d "./postgres-data" ]; then
            info "Deleting local database directory './postgres-data'..."
            rm -rf ./postgres-data
            success "Local database directory cleaned."
        fi
        # The start_app function will handle the rest, including config prep
        start_app
    else
        info "Clean start operation cancelled."
        exit 0
    fi
}

# --- Script Execution ---
# Check that Docker and docker-compose are installed
if ! command -v "docker" &> /dev/null; then
    error "'docker' command not found. Please install it to continue."
fi
if ! command -v "docker-compose" &> /dev/null; then
    error "'docker-compose' command not found. Please install it to continue."
fi

# Main command dispatcher
COMMAND=$1
case "$COMMAND" in
    start) start_app ;;
    start:clean) start_clean_app ;;
    stop) stop_app ;;
    logs) follow_logs ;;
    build) build_images ;;
    test:backend) run_backend_tests ;;
    -h|--help) usage ;;
    "")
        info "No command specified. Defaulting to 'start'."
        start_app
        ;;
    *)
        error "Invalid command: '$COMMAND'\nRun './run_app.sh --help' for available commands."
        ;;
esac