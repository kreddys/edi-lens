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

if [ "$IS_LOCAL_ENV" = true ]; then
    DC_FILES="-f docker-compose.yml -f docker-compose.dev.yml"
    ENV_FILE_TO_LOAD="$(dirname "$0")/../.env.local"
else
    DC_FILES="-f docker-compose.prod.yml"
    ENV_FILE_TO_LOAD="$(dirname "$0")/../.env"
fi

if [ -f "$ENV_FILE_TO_LOAD" ]; then info "Loading env from $ENV_FILE_TO_LOAD..."; set -a; source "$ENV_FILE_TO_LOAD"; set +a; else warn "$ENV_FILE_TO_LOAD not found."; fi

if [ "$REMOTE_HOST" = "localhost" ]; then
  export KEYCLOAK_BROWSER_URL="http://${REMOTE_HOST}:8080"; export KC_SPI_FRAME_ANCESTORS="'self' http://${REMOTE_HOST}:3001"; export VITE_API_URL="http://${REMOTE_HOST}:8000/api/v1";
else
  export KEYCLOAK_BROWSER_URL="https://auth.${REMOTE_HOST}"; export KC_SPI_FRAME_ANCESTORS="'self' https://${REMOTE_HOST}"; export VITE_API_URL="https://api.${REMOTE_HOST}/api/v1";
fi
export VITE_KEYCLOAK_URL="${KEYCLOAK_BROWSER_URL}"; export VITE_KEYCLOAK_REALM="${KEYCLOAK_REALM}"; export VITE_KEYCLOAK_CLIENT_ID="${KEYCLOAK_UI_CLIENT_ID}";

check_docker() { if ! docker info >/dev/null 2>&1; then error "Docker not running."; fi; }

# --- Command Functions ---
# FILE: scripts/run_app.sh

run_in_backend() {
    local cmd_to_run=("$@")
    info "Executing in backend: ${cmd_to_run[*]}"

    if [ "$IS_LOCAL_ENV" = true ]; then
        # Local 'exec' is still the simplest method for the dev environment
        ${DC_COMMAND} ${DC_FILES} exec "$BACKEND_SERVICE_NAME" "${cmd_to_run[@]}"
    else
        # For prod, use 'docker compose run' which will now read the network
        # configuration from the docker-compose.run.yml file.
        export RUN_IMAGE="${DOCKERHUB_USERNAME}/edi-lens-backend:latest"
        
        # We pass BOTH sets of files. prod.yml defines the project context,
        # and run.yml adds our one-off service to that context.
        # The --entrypoint="" flag is still crucial.
        ${DC_COMMAND} ${DC_FILES} -f docker-compose.run.yml run --rm \
            --entrypoint="" \
            run-command "${cmd_to_run[@]}"
    fi
}

# --- Main Logic ---
if [ -z "$1" ]; then error "Usage: ./scripts/run_app.sh [dev|up|down|clean|setup:keycloak|setup:testdata...]"; fi
COMMAND=$1; shift; check_docker

case "$COMMAND" in
    "dev")
        info "Starting services in DEVELOPMENT mode..."
        ${DC_COMMAND} -f docker-compose.yml -f docker-compose.dev.yml up -d --build
        ;;
    "up")
        info "Starting services..."
        # If we're not local, assume production and pull latest images first
        if [ "$IS_LOCAL_ENV" = false ]; then
            info "Pulling latest images for production..."
            ${DC_COMMAND} ${DC_FILES} pull
        fi
        # Build if necessary and start detached
        ${DC_COMMAND} ${DC_FILES} up -d --build
        success "Application started successfully."
        ;;        
    "down")
        info "Stopping all services...";
        ${DC_COMMAND} ${DC_FILES} down --volumes
        ;;
    "clean")
        read -p "⚠️  This will delete all data and volumes, including the database. Are you sure? [y/N] " confirm
        if [[ "$confirm" =~ ^[yY](es)?$ ]]; then
            info "Stopping services and removing all defined Docker volumes..."
            
            # This command removes containers and named volumes (like prod's postgres_data)
            ${DC_COMMAND} ${DC_FILES} down --volumes

            # This command handles the local dev bind mount
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
        run_in_backend "alembic" "-c" "alembic.ini" "revision" "--autogenerate" "-m" "$1"
        success "Migration file created."
        ;;
    "migrate:run")
        info "Applying migrations to the database..."
        ${DC_COMMAND} ${DC_FILES} up -d --wait "$BACKEND_SERVICE_NAME"
        run_in_backend "alembic" "-c" "alembic.ini" "upgrade" "head"
        success "Migrations applied."
        ;;
    "setup:keycloak")
        info "Running Keycloak setup script..."
        warn "This requires dependent services to be running."
        ${DC_COMMAND} ${DC_FILES} up -d --wait db keycloak "$BACKEND_SERVICE_NAME"
        run_in_backend "python" "scripts/setup_keycloak_realm.py"
        success "Keycloak setup script completed successfully."
        ;;
    "setup:testdata")
        info "Seeding the database with initial test data..."
        ${DC_COMMAND} ${DC_FILES} up -d --wait "$BACKEND_SERVICE_NAME"
        run_in_backend "python" "scripts/seed.py" "$@"
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
    *)
        error "Unknown command: $COMMAND"
        ;;
esac