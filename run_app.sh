#!/bin/bash

# A script to manage common development tasks for the EDI Lens application.
# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# The name of your main backend service in docker-compose.yml
BACKEND_SERVICE_NAME="backend"
# The name of your main database service in docker-compose.yml
DB_SERVICE_NAME="db"
# The name of your main keycloak service in docker-compose.yml
KEYCLOAK_SERVICE_NAME="keycloak"

# --- Helper Functions ---
info() {
    echo "[INFO] $1"
}

success() {
    echo "[SUCCESS] $1"
}

warn() {
    echo "[WARN] $1"
}

error() {
    echo "[ERROR] $1" >&2
    exit 1
}

# Ensure Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        error "Docker does not seem to be running. Please start Docker and try again."
    fi
}

# Start dependency services (db, keycloak) in detached mode
start_dependencies() {
    info "Starting dependency services ($DB_SERVICE_NAME, $KEYCLOAK_SERVICE_NAME)..."
    docker-compose up -d "$DB_SERVICE_NAME" "$KEYCLOAK_SERVICE_NAME"
    info "Waiting for services to be healthy..."
    # You might need to add a wait-for-it script or a simple sleep here
    # For now, we rely on docker-compose healthchecks.
    sleep 10 # Give services a moment to initialize
}

# Stop all services
stop_services() {
    info "Stopping all services..."
    docker-compose down
}

# Run the Keycloak setup script
setup_keycloak() {
    info "Running Keycloak setup script. This will create roles, groups, and users."
    warn "This requires all services to be running. Starting them now if needed."
    docker-compose up -d --wait
    info "Executing setup script inside the backend container..."
    docker-compose exec "$BACKEND_SERVICE_NAME" python3 scripts/setup_keycloak_realm.py
    success "Keycloak setup script completed successfully."
}

# Manage the test database
manage_test_db() {
    local command=$1 # "create" or "drop"
    info "Running database command: $command"
    docker-compose exec "$BACKEND_SERVICE_NAME" python -m tests.manage_test_db "$command"
}

# Run backend tests
run_backend_tests() {
    info "(1/3) Dropping old test database (if it exists)..."
    manage_test_db "drop"

    info "(2/3) Creating new test database..."
    manage_test_db "create"

    info "(3/3) Executing pytest for unit tests (tests not marked 'integration')..."
    # --- THIS IS THE FIX ---
    # We call pytest directly. The container's PATH is already set up
    # to find the executable inside the virtual environment.
    docker-compose exec "$BACKEND_SERVICE_NAME" pytest -m "not integration"
}

# Run backend integration tests
run_backend_integration_tests() {
    info "Executing pytest for integration tests (tests marked 'integration')..."
    # --- THIS IS ALSO THE FIX ---
    # Call pytest directly here as well.
    docker-compose exec "$BACKEND_SERVICE_NAME" pytest -m "integration"
}


# --- Main Script Logic ---

# Check for command argument
if [ -z "$1" ]; then
    error "Usage: ./run_app.sh [up|down|logs|test:backend|test:integration|setup:keycloak]"
fi

COMMAND=$1

# Load environment variables
if [ -f .env ]; then
    info "Loading environment variables from .env file..."
    export $(cat .env | grep -v '#' | xargs)
else
    warn ".env file not found. Using default environment variables."
fi

check_docker

case "$COMMAND" in
    "up")
        info "Starting all application services..."
        docker-compose up -d --build
        info "Application is up and running."
        docker-compose logs -f
        ;;
    "down")
        stop_services
        ;;
    "logs")
        info "Tailing logs for all services..."
        docker-compose logs -f
        ;;
    "test:backend")
        info "Preparing for backend unit tests..."
        info "Starting dependency services (db, keycloak)..."
        # Start all services so the backend container is running
        docker-compose up -d --build
        # Wait for services to be healthy before proceeding
        docker-compose up --wait
        setup_keycloak
        run_backend_tests
        info "Unit tests complete. Stopping dependency services..."
        docker-compose down
        ;;
    "test:integration")
        info "Preparing for backend integration tests..."
        info "Starting all services for integration test run..."
        docker-compose up -d --build
        docker-compose up --wait
        setup_keycloak
        run_backend_integration_tests
        info "Integration tests complete. Stopping all services..."
        docker-compose down
        ;;
    "setup:keycloak")
        setup_keycloak
        ;;
    *)
        error "Unknown command: $COMMAND"
        ;;
esac