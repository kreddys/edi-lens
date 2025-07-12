#!/bin/bash

# A script to manage common development tasks for the EDI Lens application.
set -e

# --- Configuration ---
BACKEND_SERVICE_NAME="backend"
# The network name from your compose files, with project name prefix
# To find your exact network name, run `docker network ls`
NETWORK_NAME="edi-lens_edi_network"

# --- Helper Functions ---
info() { echo "[INFO] $1"; }
success() { echo "[SUCCESS] $1"; }
warn() { echo "[WARN] $1"; }
error() { echo "[ERROR] $1" >&2; exit 1; }

# --- Dynamic Command & File Selection ---
# 1. Check for docker compose vs docker-compose
if docker compose version >/dev/null 2>&1; then
    DC_COMMAND="docker compose"
else
    DC_COMMAND="docker-compose"
fi

# 2. Detect environment and set appropriate files
# This logic is for determining which files to use when this script is run
ENV_FILE_LOCAL="$(dirname "$0")/../.env.local"

if [ -f "$ENV_FILE_LOCAL" ] && [ "$CI" != "true" ]; then
    # We are in a local development environment
    DC_FILES_UP="-f docker-compose.yml -f docker-compose.dev.yml"
    DC_FILES_RUN="-f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.run.yml"
    ENV_FILE_TO_LOAD="$ENV_FILE_LOCAL"
else
    # We are in a remote (prod/dev) environment
    DC_FILES_UP="-f docker-compose.prod.yml"
    DC_FILES_RUN="-f docker-compose.prod.yml -f docker-compose.run.yml"
    ENV_FILE_TO_LOAD="$(dirname "$0")/../.env"
fi

# 3. Load base environment file
if [ -f "$ENV_FILE_TO_LOAD" ]; then
    info "Loading environment variables from $ENV_FILE_TO_LOAD..."
    set -a
    source "$ENV_FILE_TO_LOAD"
    set +a
else
    warn "$ENV_FILE_TO_LOAD file not found. Some commands may fail."
fi

# 4. Construct and Export Dynamic Variables based on the loaded environment
if [ "$REMOTE_HOST" = "localhost" ]; then
  export KEYCLOAK_BROWSER_URL="http://${REMOTE_HOST}:8080"
  export KC_SPI_FRAME_ANCESTORS="'self' http://${REMOTE_HOST}:3001"
  export VITE_API_URL="http://${REMOTE_HOST}:8000/api/v1"
else
  export KEYCLOAK_BROWSER_URL="https://auth.${REMOTE_HOST}"
  export KC_SPI_FRAME_ANCESTORS="'self' https://${REMOTE_HOST}"
  export VITE_API_URL="https://api.${REMOTE_HOST}/api/v1"
fi

# Export variables needed by the Vite build process and frontend
export VITE_KEYCLOAK_URL="${KEYCLOAK_BROWSER_URL}"
export VITE_KEYCLOAK_REALM="${KEYCLOAK_REALM}"
export VITE_KEYCLOAK_CLIENT_ID="${KEYCLOAK_UI_CLIENT_ID}"

# --- Command Functions ---
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        error "Docker does not seem to be running. Please start Docker and try again."
    fi
}

# NEW function for running commands reliably
run_in_backend() {
    local cmd_to_run=("$@")
    info "Executing command in backend container: ${cmd_to_run[*]}"

    # Define the image to use for the run-command service
    export RUN_IMAGE="${DOCKERHUB_USERNAME}/edi-lens-backend:latest"
    
    # Use the docker-compose.run.yml file to start a temporary container on the correct network
    ${DC_COMMAND} ${DC_FILES_RUN} run --rm run-command "${cmd_to_run[@]}"
}

setup_keycloak() {
    info "Running Keycloak setup script..."
    warn "This requires all services to be running and healthy."
    ${DC_COMMAND} ${DC_FILES_UP} up -d --wait db keycloak
    # Note the path is relative to the project root now, because of the volume mount in docker-compose.run.yml
    run_in_backend "python" "backend/scripts/setup_keycloak_realm.py"
    success "Keycloak setup script completed successfully."
}

setup_testdata() {
    info "Seeding the database with initial test data..."
    # The "$@" passes any extra args like --clean
    run_in_backend "python" "backend/scripts/seed.py" "$@"
    success "Database seeding complete."
}

# --- Main Logic ---
if [ -z "$1" ]; then
    error "Usage: ./scripts/run_app.sh [dev|down|clean|setup:keycloak|...]"
fi
COMMAND=$1
shift 

check_docker

case "$COMMAND" in
    "dev")
        info "Starting all services in DEVELOPMENT mode (with live-reload)..."
        ${DC_COMMAND} -f docker-compose.yml -f docker-compose.dev.yml up -d --build
        ;;
    "down")
        info "Stopping all services..."
        ${DC_COMMAND} -f docker-compose.yml -f docker-compose.dev.yml down -v
        ;;
    "clean")
        ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
        POSTGRES_DATA_DIR="$ROOT_DIR/postgres-data"

        read -p "⚠️  This will delete local database data and volumes. Are you sure? [y/N] " confirm
        case "$confirm" in
            [yY][eE][sS]|[yY])
                info "Stopping services and removing Docker volumes..."
                ${DC_COMMAND} -f docker-compose.yml -f docker-compose.dev.yml down -v
                if [ -d "$POSTGRES_DATA_DIR" ]; then
                    rm -rf "$POSTGRES_DATA_DIR"
                    success "Successfully deleted postgres-data folder."
                fi
                ;;
            *)
                warn "Clean operation cancelled by user."
                ;;
        esac
    ;;
    "migrate:make")
        if [ -z "$1" ]; then
            error "Migration message is required."
        fi
        info "Generating new migration: $1"
        run_in_backend "alembic" "-c" "backend/alembic.ini" "revision" "--autogenerate" "-m" "$1"
        success "Migration file created. Please check it for correctness."
        ;;
    "migrate:run")
        info "Applying migrations to the database..."
        run_in_backend "alembic" "-c" "backend/alembic.ini" "upgrade" "head"
        success "Migrations applied."
        ;;
    "deploy:dev")
        info "Manually triggering the 'Deploy to Dev Droplet' GitHub Action..."
        if ! command -v gh &> /dev/null; then
            error "GitHub CLI ('gh') is not installed. Please install it to use this command."
        fi
        gh workflow run deploy-dev.yml --ref dev
        success "Workflow triggered. Check the 'Actions' tab in your GitHub repository for progress."
        ;;
    "setup:keycloak")
        setup_keycloak
        ;;
    "setup:testdata")
        setup_testdata "$@"
        ;;
    "logs")
        info "Tailing logs..."
        ${DC_COMMAND} ${DC_FILES_UP} logs -f "$@"
        ;;
    *)
        error "Unknown command: $COMMAND"
        ;;
esac