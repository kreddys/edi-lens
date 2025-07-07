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
    # Override the default command to run the manage_test_db script
    docker-compose run --rm "$BACKEND_SERVICE_NAME" python -m tests.manage_test_db "$command"
}

run_unit_tests() {
    info "Running pure unit tests locally (no external services)..."
    if ! command -v poetry &> /dev/null; then
        error "poetry could not be found. Please install poetry and ensure it's in your PATH."
    fi

    (cd backend && poetry run pytest -m "unit")
    success "Unit tests completed."
}

run_integration_tests() {
    info "Preparing for integration tests..."
    info "(1/4) Starting all services..."
    docker-compose up -d --wait
    
    info "(2/4) Setting up Keycloak realm, roles, and users..."
    setup_keycloak

    info "(3/4) Creating/re-creating test database..."
    manage_test_db "drop"
    manage_test_db "create"

    info "(4/4) Executing integration tests inside the backend container..."
    docker-compose run --rm "$BACKEND_SERVICE_NAME" pytest -m "integration"

    success "Integration tests completed."
}


# --- Main Logic ---
if [ -z "$1" ]; then
    error "Usage: ./scripts/run_app.sh [up|dev|down|clean|logs|migrate:make \"message\"|migrate:run|...]"
fi
COMMAND=$1
shift # Shift arguments so $1 is now the migration message if present

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
        info "Starting all application services with live-reload..."
        # This will now start the uvicorn server with --reload by default
        docker-compose up -d --build
        ;;
    "dev")
        info "Starting all services in DEVELOPMENT mode (with backend live-reload)..."
        # We explicitly specify both compose files. The override file is last.
        docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
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

                info "Rebuilding all services..."
                docker-compose build
                success "Clean complete."
                ;;
            *)
                warn "Clean operation cancelled by user."
                ;;
        esac
    ;;
    "migrate:make")
        if [ -z "$1" ]; then
            error "Migration message is required. Usage: ./scripts/run_app.sh migrate:make \"your message\""
        fi
        info "Generating new migration: $1"
        info "Starting dependent services..."
        docker-compose up -d db keycloak
        sleep 5 # Give services time to stabilize
        info "Running alembic command..."
        # Use 'run --rm' to start a temporary container for the command
        docker-compose run --rm "$BACKEND_SERVICE_NAME" alembic revision --autogenerate -m "$1"
        success "Migration file created. Please check it for correctness."
        ;;
    "migrate:run")
        info "Applying migrations to the database..."
        info "Starting dependent services..."
        docker-compose up -d db
        sleep 5
        info "Running alembic upgrade..."
        docker-compose run --rm "$BACKEND_SERVICE_NAME" alembic upgrade head
        success "Migrations applied."
        ;;
    "logs")
        info "Tailing logs for all services..."
        docker-compose logs -f
        ;;
    "test:unit")
        run_unit_tests
        ;;
    "test:integration")
        run_integration_tests
        info "Stopping services after integration tests..."
        stop_services
        ;;
    "setup:keycloak")
        setup_keycloak
        ;;
    "seed")
        info "Seeding the database with initial data..."
        info "Any additional arguments will be passed to the script (e.g., --clean)."
        docker-compose run --rm "$BACKEND_SERVICE_NAME" python -m scripts.seed "$@"
        success "Database seeding complete."
        ;;
    *)
        error "Unknown command: $COMMAND"
        ;;
esac