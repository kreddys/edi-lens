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

PROJECT_ROOT=$(dirname "$0")/..
DC_FILES="-f docker-compose.yml" # Default to the new single file for local dev

# Load environment variables from .env.local if it exists
if [ -f "$PROJECT_ROOT/.env.local" ]; then
    info "Found .env.local, using it for configuration."
    set -a; source "$PROJECT_ROOT/.env.local"; set +a
    
    # Conditionally add observability stack after sourcing the env file
    if [ "${ENABLE_OBSERVABILITY}" = "true" ]; then
      info "Observability is enabled. Including observability stack..."
      DC_FILES="$DC_FILES -f docker/docker-compose.observability.yml"
    fi
else
    warn "No .env.local file found. The local development environment may not be configured correctly."
fi

# Set frontend environment variables dynamically
if [ "$REMOTE_HOST" = "localhost" ]; then
  export KEYCLOAK_BROWSER_URL="http://${REMOTE_HOST}:8080"; 
  export KC_SPI_FRAME_ANCESTORS="'self' http://${REMOTE_HOST}:3000"; 
  export VITE_API_URL="http://${REMOTE_HOST}:3000/api/v1";
else
  export KEYCLOAK_BROWSER_URL="https://auth.${REMOTE_HOST}"; 
  export KC_SPI_FRAME_ANCESTORS="'self' https://${REMOTE_HOST}"; 
  export VITE_API_URL="https://api.${REMOTE_HOST}/api/v1";
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
if [ -z "$1" ]; then error "Usage: ./scripts/run_app.sh [dev|up|down|build|clean|run_in_backend|setup:keycloak|setup:testdata...]"; fi
COMMAND=$1; shift;

if [[ "$COMMAND" != "test:unit" && "$COMMAND" != "deploy:dev" ]]; then
    check_docker
fi

case "$COMMAND" in
    "dev" | "up")
        info "Starting services in DEVELOPMENT mode..."
        ${DC_COMMAND} ${DC_FILES} up -d --build
        ;;
    "build")
        ${DC_COMMAND} ${DC_FILES} build
        success "Images built successfully."
        ;;
    "build:db")
        info "Building multi-platform PostgreSQL RAG image..."
        if [ -z "$DOCKERHUB_USERNAME" ]; then error "DOCKERHUB_USERNAME is not set in your .env file."; fi
        
        docker buildx build \
          --platform linux/amd64,linux/arm64 \
          -t "${DOCKERHUB_USERNAME}/postgres-for-rag:latest" \
          --file ./docker/postgres/Dockerfile \
          --push \
          .
          
        success "Successfully built and pushed ${DOCKERHUB_USERNAME}/postgres-for-rag:latest"
        ;;
    "down")
        info "Stopping all services (containers only, volumes preserved)...";
        ${DC_COMMAND} ${DC_FILES} down
        ;;
    "clean")
        read -p "⚠️  This will delete all data and volumes, including the database. Are you sure? [y/N] " confirm
        if [[ "$confirm" =~ ^[yY](es)?$ ]]; then
            info "Stopping services and removing all defined Docker volumes..."
            if [ "${ENABLE_OBSERVABILITY}" = "true" ]; then
                info "Observability is enabled. OpenLIT data volumes will also be removed."
            fi
            ${DC_COMMAND} ${DC_FILES} down --volumes
            success "All services and volumes have been removed."
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
    "run_in_backend")
        if [ -z "$1" ]; then error "No command provided to run in backend."; fi
        run_in_backend "$@"
        ;;
    "setup:keycloak")
        info "Running Keycloak setup script..."
        warn "This requires dependent services to be running."
        ${DC_COMMAND} ${DC_FILES} up -d --wait db-keycloak keycloak "$BACKEND_SERVICE_NAME"
        run_in_backend python -m scripts.setup_keycloak_realm
        success "Keycloak setup script completed successfully."
        ;;
    "setup:testdata")
        info "Seeding the database with initial test data..."
        ${DC_COMMAND} ${DC_FILES} up -d --wait "$BACKEND_SERVICE_NAME"
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