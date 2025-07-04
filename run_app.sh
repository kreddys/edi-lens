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
YELLOW='\033[1;33m'
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
    echo "  init:kc-db    Create the dedicated database and user for Keycloak from .env values."
    echo "  -h, --help    Display this help message."
    echo ""
}

# Starts all services in detached mode
start_app() {
    info "Building images and starting all services (db, backend, keycloak, etc.)..."
    docker-compose up --build -d
    success "All services are starting in the background. Use 'docker-compose ps' to check status."
}

# Stops and removes all services
stop_app() {
    info "Stopping and removing all services..."
    docker-compose down
    success "All services have been stopped."
}

# Builds images for all services
build_images() {
    info "Building all service images..."
    docker-compose build
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

# Creates the keycloak database and user from .env values
init_keycloak_db() {
    info "Creating Keycloak database and user from .env settings..."
    warn "This requires the main 'db' service to be running. Starting it now if needed."
    
    # Load .env file to make sure we have the variables
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
    else
        error ".env file not found. Cannot proceed."
    fi

    # Check if all required variables are set
    if [ -z "${POSTGRES_USER}" ] || [ -z "${KC_DB_USERNAME}" ] || [ -z "${KC_DB_PASSWORD}" ] || [ -z "${KC_DB_URL_DATABASE}" ]; then
        error "One or more required variables (POSTGRES_USER, KC_DB_USERNAME, KC_DB_PASSWORD, KC_DB_URL_DATABASE) are not set in your .env file."
    fi

    # Ensure the db service is running
    docker-compose up -d db
    
    info "Waiting for PostgreSQL to be ready..."
    sleep 5 

    info "Executing SQL script to create database and user..."
    # This is the updated command that passes all three variables to psql
    docker-compose exec -T db psql -U ${POSTGRES_USER} -d postgres \
        -v KC_USERNAME_VAR="${KC_DB_USERNAME}" \
        -v KC_PASSWORD_VAR="${KC_DB_PASSWORD}" \
        -v KC_DB_NAME_VAR="${KC_DB_URL_DATABASE}" \
        < scripts/init-keycloak-db.sql
    
    if [ $? -eq 0 ]; then
        success "Keycloak database and user created successfully."
        info "You can now start all services with './run_app.sh start'."
    else
        error "Failed to create Keycloak database. Check the SQL script and .env file."
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
    start:clean)
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
    init:kc-db)
        init_keycloak_db
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