#!/bin/bash

# ==============================================================================
# Utility Script for the EDI Lens Project
# ==============================================================================

# --- Configuration ---
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# --- Helper Functions ---
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

# --- SCRIPT INITIALIZATION ---
if [ -f .env ]; then
    info "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
else
    error ".env file not found. Please create one from .env.example."
fi

# --- Main Functions ---

prepare_kc_config() {
    info "Preparing Keycloak configuration from template..."
    if ! command -v "python3" &> /dev/null; then
        error "'python3' command not found. Please install it."
    fi
    python3 backend/scripts/prepare_keycloak_config.py
    if [ $? -ne 0 ]; then
        error "Failed to prepare Keycloak configuration. Aborting."
    fi
}

export_keycloak_realm() {
    info "Exporting realm from database..."

    # 1. Stop the main keycloak service to prevent port conflicts
    info "(1/3) Stopping main Keycloak service..."
    docker-compose stop keycloak

    # 2. Define paths
    local realm_name="edi-lens"
    local export_dir_on_host="./keycloak-export-temp"
    local export_file_on_host="${export_dir_on_host}/${realm_name}-realm.json"
    local local_target_file="./keycloak-config/realm-export.template.json"

    mkdir -p "${export_dir_on_host}"

    # 3. Run the export command in a temporary container
    info "(2/3) Running export command..."
    # We use --entrypoint to override the default 'start-dev' command from docker-compose.yml
    docker-compose run --rm \
      --entrypoint="/opt/keycloak/bin/kc.sh" \
      -v "$(pwd)/${export_dir_on_host}:/tmp/export" \
      keycloak \
      export --realm "${realm_name}" --users realm_file --dir /tmp/export

    if [ $? -ne 0 ]; then
        rm -rf "${export_dir_on_host}"
        error "Keycloak export command failed. Check the logs above."
    fi
    
    # 4. Move the file and clean up
    info "(3/3) Moving exported file to template location..."
    if [ -f "${export_file_on_host}" ]; then
        mv "${export_file_on_host}" "${local_target_file}"
        rm -rf "${export_dir_on_host}"
    else
        rm -rf "${export_dir_on_host}"
        error "Exported file was not found at '${export_file_on_host}'."
    fi

    success "Realm successfully exported to '${local_target_file}'."
    warn "IMPORTANT: Open the new template file and replace the client secret(s) with '##KEYCLOAK_CLIENT_SECRET##' before committing."
    info "You can now restart your services with './run_app.sh start'."
}


usage() {
    echo "EDI Lens Project Management Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Available Commands:"
    echo "  start              Build images and start all services in the background. (Default)"
    echo "  start:clean        Permanently delete all volumes and data, then start all services."
    echo "  stop               Stop and remove all running services and networks."
    echo "  logs               Follow the logs of all running services."
    echo "  build              Force a rebuild of all service images without starting them."
    echo "  test:backend       Run unit tests with a temporary test database."
    echo "  test:integration   Run integration tests against live services."
    echo "  kc:export          Export the live Keycloak realm configuration to the template file."
    echo "  -h, --help         Display this help message."
    echo ""
}

start_app() {
    prepare_kc_config
    info "Building images and starting all services..."
    docker-compose up --build -d
    success "All services are starting. Use './run_app.sh logs' to check status."
}

stop_app() {
    info "Stopping and removing all services and the network..."
    docker-compose down
    success "All services have been stopped."
}

follow_logs() {
    info "Following logs for all services. Press Ctrl+C to exit."
    docker-compose logs -f
}

build_images() {
    info "Building all service images..."
    docker-compose build
    success "Image build complete."
}

run_backend_tests() {
    # ... (function unchanged)
    info "Preparing for backend unit tests..."
    prepare_kc_config
    info "Starting dependency services (db, keycloak)..."
    docker-compose up -d db keycloak
    info "(1/3) Dropping old test database (if it exists)..."
    docker-compose run --rm backend python -m tests.manage_test_db drop
    info "(2/3) Creating new test database..."
    docker-compose run --rm backend python -m tests.manage_test_db create
    if [ $? -ne 0 ]; then
        error "Failed to create the test database. Aborting tests."
    fi
    info "(3/3) Executing pytest for unit tests (tests not marked 'integration')..."
    docker-compose run --rm --service-ports backend pytest -m "not integration"
    TEST_EXIT_CODE=$?
    info "Unit tests complete. Stopping dependency services..."
    docker-compose stop db keycloak
    exit $TEST_EXIT_CODE
}

run_integration_tests() {
    # ... (function unchanged)
    info "Preparing to run INTEGRATION tests..."
    info "(1/3) Starting all services..."
    start_app
    info "Waiting for containers to initialize..."
    sleep 5
    info "(2/3) Waiting for the backend service to be healthy..."
    TIMEOUT=120
    INTERVAL=5
    ELAPSED=0
    while true; do
        BACKEND_CONTAINER_ID=$(docker-compose ps -q backend)
        if [ -z "$BACKEND_CONTAINER_ID" ]; then
            STATUS="creating"
        else
            STATUS=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}starting{{end}}' "$BACKEND_CONTAINER_ID" 2>/dev/null)
        fi
        if [ "$STATUS" == "healthy" ]; then
            success "Backend service is healthy."
            break
        fi
        if [ $ELAPSED -ge $TIMEOUT ]; then
            error "Timeout waiting for backend service to become healthy. Check 'docker-compose logs backend'."
        fi
        info "Backend is not healthy yet (Status: $STATUS). Waiting ${INTERVAL}s..."
        sleep $INTERVAL
        ELAPSED=$((ELAPSED + INTERVAL))
    done
    info "(3/3) Executing pytest for integration tests..."
    docker-compose exec backend pytest -m integration
    TEST_EXIT_CODE=$?
    info "Integration tests complete. Stopping all services."
    stop_app
    exit $TEST_EXIT_CODE
}

start_clean_app() {
    # ... (function unchanged)
    warn "This will permanently delete the main database and all other service volumes."
    read -p "Are you sure you want to continue? (y/N): " -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        info "Proceeding with clean start..."
        docker-compose down -v
        if [ -d "./postgres-data" ]; then
            info "Deleting local database directory './postgres-data'..."
            rm -rf ./postgres-data
            success "Local database directory cleaned."
        fi
        start_app
    else
        info "Clean start operation cancelled."
        exit 0
    fi
}

# --- Script Execution ---
if ! command -v "docker" &> /dev/null; then
    error "'docker' command not found. Please install it to continue."
fi
if ! command -v "docker-compose" &> /dev/null; then
    error "'docker-compose' command not found. Please install it to continue."
fi

COMMAND=$1
case "$COMMAND" in
    start) start_app ;;
    start:clean) start_clean_app ;;
    stop) stop_app ;;
    logs) follow_logs ;;
    build) build_images ;;
    test:backend) run_backend_tests ;;
    test:integration) run_integration_tests ;;
    kc:export) export_keycloak_realm ;; # <-- ADD THIS LINE
    -h|--help) usage ;;
    "")
        info "No command specified. Defaulting to 'start'."
        start_app
        ;;
    *)
        error "Invalid command: '$COMMAND'\nRun './run_app.sh --help' for available commands."
        ;;
esac