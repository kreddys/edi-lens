#!/bin/bash

# A script to manage common development tasks for the EDI Lens application.
set -e

# --- Configuration ---
BACKEND_SERVICE_NAME="backend"
DB_SERVICE_NAME="db"
KEYCLOAK_SERVICE_NAME="keycloak"

# --- Helper Functions ---
info() { echo "[INFO] $1"; }
success() { echo "[SUCCESS] $1"; }
warn() { echo "[WARN] $1"; }
error() { echo "[ERROR] $1" >&2; exit 1; }

# --- Dynamic Command & File Selection ---
# Check for docker compose vs docker-compose
if docker compose version >/dev/null 2>&1; then
    DC_COMMAND="docker compose"
else
    DC_COMMAND="docker-compose"
fi

# Detect environment and set appropriate files
ENV_FILE_LOCAL="$(dirname "$0")/../.env.local"

if [ -f "$ENV_FILE_LOCAL" ] && [ "$CI" != "true" ]; then
    DC_FILES="-f docker-compose.yml -f docker-compose.dev.yml"
    ENV_FILE_TO_LOAD="$ENV_FILE_LOCAL"
else
    DC_FILES="-f docker-compose.prod.yml"
    ENV_FILE_TO_LOAD="$(dirname "$0")/../.env"
fi

# Load base environment file
if [ -f "$ENV_FILE_TO_LOAD" ]; then
    info "Loading environment variables from $ENV_FILE_TO_LOAD..."
    set -a
    source "$ENV_FILE_TO_LOAD"
    set +a
else
    warn "$ENV_FILE_TO_LOAD file not found. Some commands may fail."
fi

# --- Construct and Export Dynamic Variables ---
if [ "$REMOTE_HOST" = "localhost" ]; then
  # Local Development Settings
  export KEYCLOAK_BROWSER_URL="http://${REMOTE_HOST}:8080"
  export KC_SPI_FRAME_ANCESTORS="'self' http://${REMOTE_HOST}:3001"
  export VITE_API_URL="http://${REMOTE_HOST}:8000/api/v1"
else
  # Production/Staging Settings
  export KEYCLOAK_BROWSER_URL="https://auth.${REMOTE_HOST}"
  export KC_SPI_FRAME_ANCESTORS="'self' https://${REMOTE_HOST}"
  export VITE_API_URL="https://api.${REMOTE_HOST}/api/v1"
fi

export VITE_KEYCLOAK_URL="${KEYCLOAK_BROWSER_URL}"
export VITE_KEYCLOAK_REALM="${KEYCLOAK_REALM}"
export VITE_KEYCLOAK_CLIENT_ID="${KEYCLOAK_UI_CLIENT_ID}"

check_docker() {
    if ! docker info > /dev/null 2>&1; then
        error "Docker does not seem to be running. Please start Docker and try again."
    fi
}

# --- Command Functions ---
setup_keycloak() {
    info "Running Keycloak setup script..."
    warn "This requires all services to be running and healthy."
    ${DC_COMMAND} ${DC_FILES} up -d --wait db keycloak
    info "Executing setup script inside the backend container..."
    ${DC_COMMAND} ${DC_FILES} run --rm "$BACKEND_SERVICE_NAME" python3 /home/appuser/app/scripts/setup_keycloak_realm.py
    success "Keycloak setup script completed successfully."
}

# --- Main Logic ---
if [ -z "$1" ]; then
    error "Usage: ./scripts/run_app.sh [dev|down|clean|logs|...]"
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
        ${DC_COMMAND} -f docker-compose.yml -f docker-compose.dev.yml down
        ;;
    "clean")
        ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
        POSTGRES_DATA_DIR="$ROOT_DIR/postgres-data"
        read -p "⚠️  This will delete local database data at 'postgres-data' folder and related Docker volumes. Are you sure? [y/N] " confirm
        case "$confirm" in
            [yY][eE][sS]|[yY])
                info "Stopping services and removing Docker volumes..."
                ${DC_COMMAND} -f docker-compose.yml -f docker-compose.dev.yml down -v
                if [ -d "$POSTGRES_DATA_DIR" ]; then
                    rm -rf "$POSTGRES_DATA_DIR"
                    success "Successfully deleted postgres-data folder."
                fi
                info "Rebuilding all services..."
                ${DC_COMMAND} -f docker-compose.yml -f docker-compose.dev.yml build
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
        ${DC_COMMAND} ${DC_FILES} run --rm "$BACKEND_SERVICE_NAME" alembic revision --autogenerate -m "$1"
        success "Migration file created. Please check it for correctness."
        ;;
    "migrate:run")
        info "Applying migrations to the database..."
        ${DC_COMMAND} ${DC_FILES} run --rm "$BACKEND_SERVICE_NAME" alembic upgrade head
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
        info "Seeding the database with initial test data..."
        ${DC_COMMAND} ${DC_FILES} run --rm "$BACKEND_SERVICE_NAME" python -m scripts.seed "$@"
        success "Database seeding complete."
        ;;
    *)
        error "Unknown command: $COMMAND"
        ;;
esac