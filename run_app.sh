#!/bin/bash

# ==============================================================================
# Simplified Utility Script for the EDI Lens Project
#
# Description:
# This script provides essential commands to manage the Docker-based
# development environment.
# ==============================================================================

# --- Configuration ---
# Color definitions for better readability
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m' # Added back for warnings
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Helper Functions ---
# Prints an informational message
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

# Prints a success message
success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Prints a warning message
warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Prints an error message and exits
error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

# --- Main Functions ---

# Displays the help message
usage() {
    echo "Simplified EDI Lens Project Management Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Available Commands:"
    echo "  start         Build images and start all services in the background. (Default)"
    echo "  start:clean   Permanently delete the database data, then start all services."
    echo "  stop          Stop and remove all running services."
    echo "  build         Force a rebuild of all service images without starting them."
    echo "  test:backend  Re-creates the test database and runs all backend tests."
    echo "  -h, --help    Display this help message."
    echo ""
}

# Starts all services in detached mode
start_app() {
    info "Building images and starting all services (db, backend, keycloak, etc.)..."
    docker-compose up --build -d --remove-orphans
    success "All services are starting in the background. Use 'docker-compose ps' to check status."
}

# Stops and removes all services
stop_app() {
    info "Stopping and removing all services..."
    docker-compose down -v --remove-orphans
    success "All services have been stopped."
}

# Builds images for all services
build_images() {
    info "Building all service images..."
    docker-compose build --no-cache
    success "Image build complete."
}

# Runs backend tests with a fresh database
run_backend_tests() {
    info "Preparing a fresh test database..."
    info "(1/3) Dropping old test database (if it exists)..."
    docker-compose run --rm backend python -m tests.manage_test_db drop
    info "(2/3) Creating new test database..."
    docker-compose run --rm backend python -m tests.manage_test_db create
    if [ $? -ne 0 ]; then
        error "Failed to create the test database. Aborting tests."
    fi
    info "(3/3) Executing pytest..."
    docker-compose run --rm backend pytest
}

# <<< NEW FUNCTION >>>
# Deletes the dev database and starts fresh
start_clean_app() {
    warn "This will permanently delete the main development database in './postgres-data'."
    read -p "Are you sure you want to continue? (y/N): " -r
    echo # Move to a new line

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "Proceeding with clean start..."
        # 1. Stop any running containers
        stop_app
        # 2. Delete the local data directory
        info "Deleting database directory './postgres-data'..."
        rm -rf ./postgres-data
        success "Database cleaned."
        # 3. Start everything up again, which will re-create the directory
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
    start)
        start_app
        ;;
    start:clean) # <<< NEW CASE
        start_clean_app
        ;;
    stop)
        stop_app
        ;;
    build)
        build_images
        ;;
    test:backend)
        run_backend_tests
        ;;
    -h|--help)
        usage
        ;;
    "") # No command given, default action is to start the app
        info "No command specified. Defaulting to 'start'."
        start_app
        ;;
    *) # Invalid command
        error "Invalid command: '$COMMAND'\nRun './run_app.sh --help' for available commands."
        ;;
esac