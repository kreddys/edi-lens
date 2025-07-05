#!/bin/bash

# A script to manage common development tasks for the EDI Lens application.
# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
BACKEND_SERVICE_NAME="backend"
DB_SERVICE_NAME="db"
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

check_docker() {
    if ! docker info > /dev/null 2>&1; then
        error "Docker does not seem to be running. Please start Docker and try again."
    fi
}

stop_services() {
    info "Stopping all services..."
    docker-compose down
}

# Run the Keycloak setup script
setup_keycloak() {
    info "Running Keycloak setup script..."
    warn "This requires all services to be running and healthy."
    # The --wait flag ensures services are healthy before proceeding
    docker-compose up -d --wait
    info "Executing setup script inside the backend container..."
    docker-compose exec "$BACKEND_SERVICE_NAME" python3 scripts/setup_keycloak_realm.py
    success "Keycloak setup script completed successfully."
}

# Manage the test database
manage_test_db() {
    local command=$1
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
    docker-compose exec "$BACKEND_SERVICE_NAME" pytest -m "not integration"
}

# Run backend integration tests
run_backend_integration_tests() {
    info "Executing pytest for integration tests (tests marked 'integration')..."
    docker-compose exec "$BACKEND_SERVICE_NAME" pytest -m "integration"
}

# --- Main Script Logic ---
if [ -z "$1" ]; then
    error "Usage: ./run_app.sh [up|down|logs|test:backend|test:integration|setup:keycloak]"
fi
COMMAND=$1

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
        
        # --- THIS IS THE FIX ---
        # Call the setup_keycloak function after the services are running.
        setup_keycloak

        info "Application is up and running. Tailing logs..."
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
        docker-compose up -d --build
        setup_keycloak
        run_backend_tests
        info "Unit tests complete. Stopping services..."
        docker-compose down
        ;;
    "test:integration")
        info "Preparing for backend integration tests..."
        docker-compose up -d --build
        setup_keycloak
        run_backend_integration_tests
        info "Integration tests complete. Stopping services..."
        docker-compose down
        ;;
    "setup:keycloak")
        setup_keycloak
        ;;
    *)
        error "Unknown command: $COMMAND"
        ;;
esac