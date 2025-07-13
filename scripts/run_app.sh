#!/bin/bash

# A script to manage common development tasks for the EDI Lens application.
set -e

# --- Configuration ---
BACKEND_SERVICE_NAME="backend"
NETWORK_NAME="edi-lens_edi_network" # From docker-compose network definition

# --- Helper Functions ---
info() { echo "[INFO] $1"; }
success() { echo "[SUCCESS] $1"; }
warn() { echo "[WARN] $1"; }
error() { echo "[ERROR] $1" >&2; exit 1; }

# --- Dynamic Environment Setup ---
if docker compose version >/dev/null 2>&1; then DC_COMMAND="docker compose"; else DC_COMMAND="docker-compose"; fi

IS_LOCAL_ENV=false
if [ -f "$(dirname "$0")/../.env.local" ]; then IS_LOCAL_ENV=true; fi

# --- THIS IS THE FIX ---
# Updated to remove the reference to the base file.
if [ "$IS_LOCAL_ENV" = true ]; then
    DC_FILES="-f docker-compose.local.yml"
    ENV_FILE_TO_LOAD="$(dirname "$0")/../.env.local"
else
    DC_FILES="-f docker-compose.dev-server.yml"
    ENV_FILE_TO_LOAD="$(dirname "$0")/../.env"
fi

if [ -f "$ENV_FILE_TO_LOAD" ]; then info "Loading env from $ENV_FILE_TO_LOAD..."; set -a; source "$ENV_FILE_TO_LOAD"; set +a; else warn "$ENV_FILE_TO_LOAD not found."; fi

if [ "$REMOTE_HOST" = "localhost" ]; then
  export KEYCLOAK_BROWSER_URL="http://${REMOTE_HOST}:8080"; export KC_SPI_FRAME_ANCESTORS="'self' http://${REMOTE_HOST}:3001 http://${REMOTE_HOST}:3000"; export VITE_API_URL="http://${REMOTE_HOST}:8000/api/v1";
else
  export KEYCLOAK_BROWSER_URL="https://auth.${REMOTE_HOST}"; export KC_SPI_FRAME_ANCESTORS="'self' https://${REMOTE_HOST}"; export VITE_API_URL="https://api.${REMOTE_HOST}/api/v1";
fi
export VITE_KEYCLOAK_URL="${KEYCLOAK_BROWSER_URL}"; export VITE_KEYCLOAK_REALM="${KEYCLOAK_REALM}"; export VITE_KEYCLOAK_CLIENT_ID="${KEYCLOAK_UI_CLIENT_ID}";

check_docker() { if ! docker info >/dev/null 2>&1; then error "Docker not running."; fi; }

# --- Command Functions ---
run_in_backend() {
    local cmd_to_run=("$@")
    info "Executing in backend: ${cmd_to_run[*]}"
    ${DC_COMMAND} ${DC_FILES} exec "$BACKEND_SERVICE_NAME" "${cmd_to_run[@]}"
}

# --- Main Logic ---
if [ -z "$1" ]; then error "Usage: ./scripts/run_app.sh [dev|up|down|build|clean|setup:keycloak|setup:testdata...]"; fi
COMMAND=$1; shift;

# Defer the Docker check, as some commands might not need it.
if [[ "$COMMAND" != "test:unit" && "$COMMAND" != "deploy:dev" ]]; then
    check_docker
fi

NO_CACHE_FLAG=""
# Check if the second argument is --no-cache
if [[ "$2" == "--no-cache" ]]; then
  NO_CACHE_FLAG="--no-cache"
fi

case "$COMMAND" in
    "dev")
        info "Starting services in DEVELOPMENT mode..."
        ${DC_COMMAND} ${DC_FILES} up -d --build
        ;;
    "up")
        info "Starting services..."
        if [ "$IS_LOCAL_ENV" = false ]; then
            info "Pulling latest images for production..."
            ${DC_COMMAND} ${DC_FILES} pull
        fi
        ${DC_COMMAND} ${DC_FILES} up -d --build
        success "Application started successfully."
        ;;        
    "build")
        if [ -n "$NO_CACHE_FLAG" ]; then
            info "Building images with no cache..."
        else
            info "Building images..."
        fi
        ${DC_COMMAND} ${DC_FILES} build ${NO_CACHE_FLAG}
        success "Images built successfully."
        ;;        
    "down")
        info "Stopping all services (containers only, volumes preserved)...";
        ${DC_COMMAND} ${DC_FILES} down
        ;;
    "clean")
        read -p "⚠️  This will delete all data and volumes, including the database. Are you sure? [y/N] " confirm
        if [[ "$confirm" =~ ^[yY](es)?$ ]]; then
            info "Stopping services and removing all defined Docker volumes..."
            ${DC_COMMAND} ${DC_FILES} down --volumes
            if [ -d "./postgres-data" ]; then
                info "Removing local bind-mount directory './postgres-data'..."
                rm -rf "./postgres-data"
            fi
            success "All services, volumes, and local data directories have been removed."
        else
            warn "Clean operation cancelled."
        fi
        ;;
    "migrate:make")
        if [ -z "$1" ]; then error "Migration message is required."; fi
        info "Generating new migration: $1"
        ${DC_COMMAND} ${DC_FILES} up -d --wait "$BACKEND_SERVICE_NAME"
        run_in_backend alembic -c alembic.ini revision --autogenerate -m "$1"
        success "Migration file created."
        ;;
    "migrate:run")
        info "Applying migrations to the database..."
        ${DC_COMMAND} ${DC_FILES} up -d --wait "$BACKEND_SERVICE_NAME"
        run_in_backend alembic -c alembic.ini upgrade head
        success "Migrations applied."
        ;;
    "setup:keycloak")
        info "Running Keycloak setup script..."
        warn "This requires dependent services to be running."
        ${DC_COMMAND} ${DC_FILES} up -d --wait db keycloak "$BACKEND_SERVICE_NAME"
        # This adds the project root to Python's path, allowing it to find the 'src' module.
        run_in_backend python -m scripts.setup_keycloak_realm
        success "Keycloak setup script completed successfully."
        ;;
    "setup:testdata")
        info "Seeding the database with initial test data..."
        ${DC_COMMAND} ${DC_FILES} up -d --wait "$BACKEND_SERVICE_NAME"
        # This adds the project root to Python's path, allowing it to find the 'src' module.
        run_in_backend python -m scripts.seed "$@"
        success "Database seeding complete."
        ;;
    "deploy:dev")
        info "Manually triggering the 'Deploy to Dev Droplet' GitHub Action..."
        if ! command -v gh &> /dev/null; then error "GitHub CLI ('gh') is not installed."; fi
        gh workflow run deploy-dev.yml --ref dev
        success "Workflow triggered."
        ;;
    "logs")
        info "Tailing logs...";
        ${DC_COMMAND} ${DC_FILES} logs -f "$@"
        ;;
    "test:create-db")
        info "Creating the test database..."
        ${DC_COMMAND} ${DC_FILES} up -d --wait "$BACKEND_SERVICE_NAME"
        run_in_backend python -m tests.manage_test_db create
        success "Test database created."
        ;;
    "test:drop-db")
        info "Dropping the test database..."
        ${DC_COMMAND} ${DC_FILES} up -d --wait "$BACKEND_SERVICE_NAME"
        run_in_backend python -m tests.manage_test_db drop
        success "Test database dropped."
        ;;
    "test:unit")
        info "Running unit tests locally (no Docker)..."
        if ! command -v poetry &> /dev/null; then
            error "Poetry is not installed or not in your PATH. Please install it to run unit tests locally."
        fi
        if [ ! -f "backend/pyproject.toml" ]; then
            error "This script must be run from the project root directory."
        fi
        (cd backend && poetry run pytest -m "unit" "$@")
        success "Unit tests completed."
        ;;
    "test:integration")
        info "Running integration tests inside Docker..."
        
        cleanup() {
            info "Integration tests finished. Dropping test database..."
            run_in_backend python -m tests.manage_test_db drop >/dev/null 2>&1
        }
        trap cleanup EXIT
        
        info "Creating test database for integration run..."
        ${DC_COMMAND} ${DC_FILES} up -d --wait "$BACKEND_SERVICE_NAME"
        run_in_backend python -m tests.manage_test_db create
        
        info "Running pytest for integration tests..."
        run_in_backend pytest -m "integration" "$@"
        
        success "Integration tests completed."
        ;;
    *)
        error "Unknown command: $COMMAND"
        ;;
esac