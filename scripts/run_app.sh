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
# 1. Check for docker compose vs docker-compose
if docker compose version >/dev/null 2>&1; then
    DC_COMMAND="docker compose"
else
    DC_COMMAND="docker-compose"
fi

# 2. Detect environment and set appropriate compose files and env file to load
# This determines if we are in a local dev setup or a remote/prod setup
ENV_FILE_LOCAL="$(dirname "$0")/../.env.local"

if [ -f "$ENV_FILE_LOCAL" ]; then
    DC_FILES="-f docker-compose.yml -f docker-compose.dev.yml"
    ENV_FILE_TO_LOAD="$ENV_FILE_LOCAL"
else
    DC_FILES="-f docker-compose.prod.yml"
    ENV_FILE_TO_LOAD="$(dirname "$0")/../.env"
fi

# 3. Load base environment file
if [ -f "$ENV_FILE_TO_LOAD" ]; then
    info "Loading environment variables from $ENV_FILE_TO_LOAD..."
    # Use set -a to automatically export all variables sourced from the file
    set -a
    source "$ENV_FILE_TO_LOAD"
    set +a
else
    # Only show a warning if it's a local dev setup, as prod should always have the file
    if [ -f "$ENV_FILE_LOCAL" ]; then
        warn ".env.local file not found. Some commands may fail. Please create it from .env.local.example."
    fi
fi

# 4. Construct and Export Dynamic Variables based on the loaded environment
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

setup_keycloak() {
    info "Running Keycloak setup script..."
    warn "This requires all services to be running and healthy."
    ${DC_COMMAND} ${DC_FILES} up -d --wait db keycloak
    info "Executing setup script inside the backend container..."
    ${DC_COMMAND} ${DC_FILES} run --rm "$BACKEND_SERVICE_NAME" python3 /home/appuser/app/scripts/setup_keycloak_realm.py
    success "Keycloak setup script completed successfully."
}

manage_test_db() {
    local command=$1
    info "Running database command: $command"
    ${DC_COMMAND} ${DC_FILES} run --rm "$BACKEND_SERVICE_NAME" python -m tests.manage_test_db "$command"
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
    ${DC_COMMAND} ${DC_FILES} up -d --wait
    
    info "(2/4) Setting up Keycloak realm, roles, and users..."
    setup_keycloak

    info "(3/4) Creating/re-creating test database..."
    manage_test_db "drop"
    manage_test_db "create"

    info "(4/4) Executing integration tests inside the backend container..."
    ${DC_COMMAND} ${DC_FILES} run --rm "$BACKEND_SERVICE_NAME" pytest -m "integration"

    success "Integration tests completed."
}

# --- Main Logic ---
if [ -z "$1" ]; then
    error "Usage: ./scripts/run_app.sh [dev|down|clean|logs|restart <service>|...]"
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
    "restart")
        if [ -z "$1" ]; then
            error "Service name is required. Usage: ./scripts/run_app.sh restart <service_name>"
        fi
        info "Restarting service: $1..."
        ${DC_COMMAND} ${DC_FILES} restart "$1"
        success "Service $1 restarted."
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
        info "Starting dependent services..."
        ${DC_COMMAND} ${DC_FILES} up -d db keycloak
        sleep 5 
        info "Running alembic command..."
        ${DC_COMMAND} ${DC_FILES} run --rm "$BACKEND_SERVICE_NAME" alembic revision --autogenerate -m "$1"
        success "Migration file created. Please check it for correctness."
        ;;
    "migrate:run")
        info "Applying migrations to the database..."
        info "Starting dependent services..."
        ${DC_COMMAND} ${DC_FILES} up -d db
        sleep 5
        info "Running alembic upgrade..."
        ${DC_COMMAND} ${DC_FILES} run --rm "$BACKEND_SERVICE_NAME" alembic upgrade head
        success "Migrations applied."
        ;;
    "logs")
        info "Tailing logs for all services..."
        ${DC_COMMAND} ${DC_FILES} logs -f
        ;;
    "test:unit")
        run_unit_tests
        ;;
    "test:integration")
        run_integration_tests
        info "Stopping services after integration tests..."
        ${DC_COMMAND} ${DC_FILES} down
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
        info "Any additional arguments will be passed to the script (e.g., --clean)."
        ${DC_COMMAND} ${DC_FILES} run --rm "$BACKEND_SERVICE_NAME" python -m scripts.seed "$@"
        success "Database seeding complete."
        ;;
    *)
        error "Unknown command: $COMMAND"
        ;;
esac