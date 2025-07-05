#!/bin/bash

# A script to manage common development tasks for the EDI Lens application.
set -e

BACKEND_SERVICE_NAME="backend"
DB_SERVICE_NAME="db"
KEYCLOAK_SERVICE_NAME="keycloak"

info() { echo "[INFO] $1"; }
success() { echo "[SUCCESS] $1"; }
warn() { echo "[WARN] $1"; }
error() { echo "[ERROR] $1" >&2; exit 1; }

check_docker() {
    if ! docker info > /dev/null 2>&1; then
        error "Docker does not seem to be running. Please start Docker and try again."
    fi
}

stop_services() {
    info "Stopping all services..."
    docker-compose down
}

setup_keycloak() {
    info "Running Keycloak setup script..."
    warn "This requires all services to be running and healthy."
    docker-compose up -d --wait
    info "Executing setup script inside the backend container..."
    docker-compose exec "$BACKEND_SERVICE_NAME" python3 /home/appuser/app/scripts/setup_keycloak_realm.py
    success "Keycloak setup script completed successfully."
}

manage_test_db() {
    local command=$1
    info "Running database command: $command"
    docker-compose exec "$BACKEND_SERVICE_NAME" python -m tests.manage_test_db "$command"
}

run_backend_tests() {
    info "(1/3) Dropping old test database (if it exists)..."
    manage_test_db "drop"
    info "(2/3) Creating new test database..."
    manage_test_db "create"
    info "(3/3) Executing pytest for unit tests (tests not marked 'integration')..."
    docker-compose exec "$BACKEND_SERVICE_NAME" pytest -m "not integration"
}

run_backend_integration_tests() {
    info "Executing pytest for integration tests (tests marked 'integration')..."
    docker-compose exec "$BACKEND_SERVICE_NAME" pytest -m "integration"
}

# --- Main Logic ---
if [ -z "$1" ]; then
    error "Usage: ./scripts/run_app.sh [up|down|clean|logs|test:backend|test:integration|setup:keycloak]"
fi
COMMAND=$1

# Load .env from project root
if [ -f "$(dirname "$0")/../.env" ]; then
    info "Loading environment variables from .env file..."
    export $(cat "$(dirname "$0")/../.env" | grep -v '#' | xargs)
else
    warn ".env file not found in project root. Using default environment variables."
fi

check_docker

case "$COMMAND" in
    "up")
        info "Starting all application services..."
        docker-compose up -d --build
        setup_keycloak
        #info "Application is up and running. Tailing logs..."
        #docker-compose logs -f
        ;;
    "down")
        stop_services
        ;;
    "clean")
        ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
        POSTGRES_DATA_DIR="$ROOT_DIR/postgres-data"

        read -p "⚠️  This will delete local database data at 'postgres-data' folder and related Docker volumes. Are you sure? [y/N] " confirm
        case "$confirm" in
            [yY][eE][sS]|[yY])
                info "Stopping services and removing Docker volumes..."
                docker-compose down -v

                if [ -d "$POSTGRES_DATA_DIR" ]; then
                    info "Found postgres-data folder at: $POSTGRES_DATA_DIR"
                    info "Attempting to delete postgres-data folder..."
                    rm -rf "$POSTGRES_DATA_DIR"

                    if [ ! -d "$POSTGRES_DATA_DIR" ]; then
                        success "Successfully deleted postgres-data folder."
                    else
                        warn "Failed to delete postgres-data folder at $POSTGRES_DATA_DIR."
                    fi
                else
                    warn "postgres-data folder not found at $POSTGRES_DATA_DIR."
                fi

                info "Rebuilding all services with no cache..."
                docker-compose build --no-cache

                info "Starting services..."
                docker-compose up -d

                setup_keycloak

                #info "Clean build and start complete. Tailing logs..."
                #docker-compose logs -f
                ;;
            *)
                warn "Clean operation cancelled by user."
                ;;
        esac
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
