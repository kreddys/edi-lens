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

ENV_FILE_LOCAL="$(dirname "$0")/../.env.local"
IS_LOCAL_ENV=false
if [ -f "$ENV_FILE_LOCAL" ] && [ "$CI" != "true" ]; then
    IS_LOCAL_ENV=true
    DC_FILES_UP="-f docker-compose.yml -f docker-compose.dev.yml"
    ENV_FILE_TO_LOAD="$ENV_FILE_LOCAL"
else
    DC_FILES_UP="-f docker-compose.prod.yml"
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
run_in_backend() {
    local cmd_to_run=("$@")
    info "Executing in backend: ${cmd_to_run[*]}"
    if [ "$IS_LOCAL_ENV" = true ]; then
        ${DC_COMMAND} ${DC_FILES_UP} exec "$BACKEND_SERVICE_NAME" "${cmd_to_run[@]}"
    else
        export RUN_IMAGE="${DOCKERHUB_USERNAME}/edi-lens-backend:latest"
        ${DC_COMMAND} -f docker-compose.prod.yml -f docker-compose.run.yml run --rm run-command "${cmd_to_run[@]}"
    fi
}

# --- Main Logic ---
if [ -z "$1" ]; then error "Usage: ./scripts/run_app.sh [dev|down|clean|setup:keycloak|...]"; fi
COMMAND=$1; shift; check_docker

case "$COMMAND" in
    "dev")
        info "Starting services in DEVELOPMENT mode..."
        ${DC_COMMAND} -f docker-compose.yml -f docker-compose.dev.yml up -d --build
        ;;
    "down")
        info "Stopping all local development services..."
        ${DC_COMMAND} -f docker-compose.yml -f docker-compose.dev.yml down -v
        ;;
    "clean")
        read -p "⚠️  This will delete local database data and volumes. Are you sure? [y/N] " confirm
        if [[ "$confirm" =~ ^[yY](es)?$ ]]; then
            info "Stopping services and removing Docker volumes..."
            ${DC_COMMAND} -f docker-compose.yml -f docker-compose.dev.yml down -v
            if [ -d "./postgres-data" ]; then rm -rf "./postgres-data"; success "Deleted postgres-data folder."; fi
        else warn "Clean operation cancelled."; fi
        ;;
    "migrate:make")
        if [ -z "$1" ]; then error "Migration message is required."; fi
        info "Generating new migration: $1"
        ${DC_COMMAND} ${DC_FILES_UP} up -d --wait "$BACKEND_SERVICE_NAME"
        if [ "$IS_LOCAL_ENV" = true ]; then
            run_in_backend "alembic" "-c" "alembic.ini" "revision" "--autogenerate" "-m" "$1"
        else
            run_in_backend "alembic" "-c" "backend/alembic.ini" "revision" "--autogenerate" "-m" "$1"
        fi
        success "Migration file created."
        ;;
    "migrate:run")
        info "Applying migrations to the database..."
        ${DC_COMMAND} ${DC_FILES_UP} up -d --wait "$BACKEND_SERVICE_NAME"
        if [ "$IS_LOCAL_ENV" = true ]; then
            run_in_backend "alembic" "-c" "alembic.ini" "upgrade" "head"
        else
            run_in_backend "alembic" "-c" "backend/alembic.ini" "upgrade" "head"
        fi
        success "Migrations applied."
        ;;
    "deploy:dev")
        info "Manually triggering the 'Deploy to Dev Droplet' GitHub Action..."
        if ! command -v gh &> /dev/null; then error "GitHub CLI ('gh') is not installed."; fi
        gh workflow run deploy-dev.yml --ref dev
        success "Workflow triggered."
        ;;
    "setup:keycloak")
        info "Running Keycloak setup script..."
        warn "This requires dependent services to be running."
        ${DC_COMMAND} ${DC_FILES_UP} up -d --wait db keycloak backend
        if [ "$IS_LOCAL_ENV" = true ]; then
            run_in_backend "python" "scripts/setup_keycloak_realm.py"
        else
            run_in_backend "python" "backend/scripts/setup_keycloak_realm.py"
        fi
        success "Keycloak setup script completed successfully."
        ;;
    "setup:testdata")
        info "Seeding the database with initial test data..."
        ${DC_COMMAND} ${DC_FILES_UP} up -d --wait backend
        if [ "$IS_LOCAL_ENV" = true ]; then
            run_in_backend "python" "scripts/seed.py" "$@"
        else
            run_in_backend "python" "backend/scripts/seed.py" "$@"
        fi
        success "Database seeding complete."
        ;;
    "logs")
        info "Tailing logs..."
        ${DC_COMMAND} ${DC_FILES_UP} logs -f "$@"
        ;;
    *)
        error "Unknown command: $COMMAND"
        ;;
esac