#!/bin/bash
# ==============================================================================
# EDI LENS - APPLICATION RUNNER SCRIPT
# ==============================================================================
# This script manages all common development and testing tasks for the application.
# It is environment-aware and distinguishes between 'dev' and 'test' contexts.

set -e

# --- Configuration ---
PROJECT_ROOT=$(dirname "$0")/..
COMPOSE_DIR="docker"
BACKEND_SERVICE_NAME="backend"
BACKEND_TEST_SERVICE_NAME="backend-test-runner"

# --- Helper Functions ---
info() { echo -e "\033[34m[INFO] $1\033[0m"; }
success() { echo -e "\033[32m[SUCCESS] $1\033[0m"; }
warn() { echo -e "\033[33m[WARN] $1\033[0m"; }
error() { echo -e "\033[31m[ERROR] $1\033[0m" >&2; exit 1; }
check_docker() { if ! docker info >/dev/null 2>&1; then error "Docker is not running. Please start it and try again."; fi; }

# --- Environment Setup ---
cd "$PROJECT_ROOT"

if docker compose version >/dev/null 2>&1; then DC_COMMAND="docker compose"; else DC_COMMAND="docker-compose"; fi

# --- Help Command ---
if [ -z "$1" ] || [[ "$1" == "help" ]] || [[ "$1" == "--help" ]]; then
    echo "EDI Lens Application Runner"
    echo "---------------------------"
    echo "A script to manage the Docker-based development and testing environments."
    echo ""
    echo "USAGE: ./scripts/run_app.sh [command] [options...]"
    echo ""
    echo "DEVELOPMENT COMMANDS (uses .env.dev):"
    echo "  dev                   Start all development services with hot-reloading and tail logs."
    echo "  up                    Alias for 'dev'."
    echo "  down                  Stop all development services without deleting data."
    echo "  clean                 Stop services and DELETE ALL DEV DATA (databases, volumes)."
    echo "  build [service...]    Build or rebuild service images (e.g., 'build backend')."
    echo "  logs [service...]     Tail logs for running dev services (e.g., 'logs admin-ui')."
    echo "  migrate:make \"msg\"  Create a new Alembic database migration file."
    echo "  migrate:run           Apply all pending migrations to the development database."
    echo "  setup:keycloak        (Re)Configure the dev Keycloak instance with realms, clients, and users."
    echo "  setup:testdata        Seed the development database with sample trading partner data."
    echo ""
    echo "TESTING COMMANDS (uses .env.test):"
    echo "  test:start            Build and start the persistent test environment. (Slower, run once)"
    echo "  test:run [args...]    Run tests against the running test environment. (Fast, run multiple times)"
    echo "                        Example: './scripts/run_app.sh test:run -m integration'"
    echo "  test:stop             Stop and completely destroy the persistent test environment and its data."
    echo "  test:reset-db         Quickly drop and recreate the test databases without restarting all containers."
    echo "  test [args...]        (CI Mode) Single command to start, run tests, and automatically destroy. (Slow)"
    echo ""
    echo "  help                  Show this help message."
    echo ""
    exit 0
fi
COMMAND=$1; shift

if [[ "$COMMAND" == test* ]]; then
    ENV_CONTEXT="test"
    ENV_FILE=".env.test"
else
    ENV_CONTEXT="dev"
    ENV_FILE=".env.dev"
fi
info "Selected Environment: $ENV_CONTEXT"

if [ ! -f "$ENV_FILE" ]; then
    warn "Environment file '$ENV_FILE' not found. Trying to copy from '$ENV_FILE.example'."
    if [ -f "$ENV_FILE.example" ]; then
        cp "$ENV_FILE.example" "$ENV_FILE"
        info "Created '$ENV_FILE'. Please review and fill in any secrets."
    else
        error "Could not find '$ENV_FILE' or '$ENV_FILE.example'. Please create one."
    fi
fi

DC_FLAGS="--project-directory . --env-file ${ENV_FILE}"
DC_BASE_FILE="-f ${COMPOSE_DIR}/docker-compose.base.yml"
DC_TEST_FILE="-f ${COMPOSE_DIR}/docker-compose.test.yml"
DC_OBSERVABILITY_FILE="-f ${COMPOSE_DIR}/docker-compose.observability.yml"
DC_FILES=""

if [ "$ENV_CONTEXT" == "test" ]; then
    DC_FILES="${DC_BASE_FILE} ${DC_TEST_FILE}"
else
    DC_FILES="${DC_BASE_FILE}"
fi

set -a; source "$ENV_FILE"; set +a

if [ "${ENABLE_OBSERVABILITY}" = "true" ]; then
  info "Observability is enabled. Including observability stack..."
  DC_FILES="${DC_FILES} ${DC_OBSERVABILITY_FILE}"
fi

run_in_backend() {
    local cmd_to_run=("$@")
    if [ "$ENV_CONTEXT" == "test" ]; then
        info "Executing in test-runner: ${cmd_to_run[*]}"
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} exec "$BACKEND_TEST_SERVICE_NAME" "${cmd_to_run[@]}"
    else
        info "Executing in backend (dev): ${cmd_to_run[*]}"
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} exec "$BACKEND_SERVICE_NAME" "${cmd_to_run[@]}"
    fi
}

check_docker

case "$COMMAND" in
    "dev" | "up")
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'$COMMAND' is only for the 'dev' environment."; fi
        info "Starting development services..."
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} up -d --build --remove-orphans
        success "Development environment is up and running."
        info "Tailing logs... (Press Ctrl+C to stop)"
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} logs -f
        ;;
    "build")
        info "Building images for the '$ENV_CONTEXT' environment..."
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} build --no-cache "$@"
        ;;
    "down")
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'$COMMAND' is only for the 'dev' environment."; fi
        info "Stopping all development services..."
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} down
        ;;
    "clean")
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'$COMMAND' is only for the 'dev' environment."; fi
        read -p "⚠️  This will permanently delete all DEV data and volumes. Are you sure? [y/N] " confirm
        if [[ "$confirm" =~ ^[yY](es)?$ ]]; then
            info "Stopping services and removing all DEV Docker volumes..."
            ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} down --volumes
            success "Development environment has been cleaned."
        else
            warn "Clean operation cancelled."
        fi
        ;;
    "migrate:make")
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'$COMMAND' is only for the 'dev' environment."; fi
        if [ -z "$1" ]; then error "Migration message is required."; fi
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} up -d "$BACKEND_SERVICE_NAME"
        run_in_backend alembic -c alembic.ini revision --autogenerate -m "$1"
        ;;
    "migrate:run")
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'$COMMAND' is only for the 'dev' environment."; fi
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} up -d db-app "$BACKEND_SERVICE_NAME"
        run_in_backend alembic -c alembic.ini upgrade head
        ;;
    "setup:keycloak")
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'$COMMAND' is only for the 'dev' environment."; fi
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} up -d --wait db-keycloak keycloak "$BACKEND_SERVICE_NAME"
        run_in_backend python -m scripts.setup_keycloak_realm
        ;;
    "setup:testdata")
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'$COMMAND' is only for the 'dev' environment."; fi
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} up -d --wait "$BACKEND_SERVICE_NAME"
        run_in_backend python -m scripts.seed "$@"
        ;;
    "logs")
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'$COMMAND' is only for the 'dev' environment."; fi
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} logs -f "$@"
        ;;

    # --- THIS IS THE FIX ---
    "test:start")
        if [ "$ENV_CONTEXT" != "test" ]; then error "This command is for the 'test' environment."; fi
        info "Building and starting PERSISTENT test environment..."
        # Explicitly start ONLY the test runner service. Docker Compose will start its dependencies.
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} up -d --build --remove-orphans --wait "$BACKEND_TEST_SERVICE_NAME"
        success "Test environment is up. Use 'test:run' to execute tests."
        ;;
    "test:run")
        if [ "$ENV_CONTEXT" != "test" ]; then error "This command is for the 'test' environment."; fi
        info "Executing tests against the running test environment..."
        run_in_backend pytest "$@"
        success "Test execution finished."
        ;;
    "test:stop")
        if [ "$ENV_CONTEXT" != "test" ]; then error "This command is for the 'test' environment."; fi
        info "Stopping and destroying PERSISTENT test environment..."
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} down --volumes
        success "Test environment destroyed."
        ;;
    "test:reset-db")
        if [ "$ENV_CONTEXT" != "test" ]; then error "This command is for the 'test' environment."; fi
        info "Resetting test databases..."
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} stop db-app-test db-keycloak-test
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} rm -fsv db-app-test db-keycloak-test
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} up -d --wait db-app-test db-keycloak-test
        success "Test databases have been reset."
        ;;
    "test")
        if [ "$ENV_CONTEXT" != "test" ]; then error "Internal script error."; fi
        info "Running in CI Mode: Starting EPHEMERAL test environment..."
        cleanup() {
            info "CI run finished. Tearing down test environment..."
            ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} down --volumes
        }
        trap cleanup EXIT
        # Explicitly start ONLY the test runner service and its dependencies.
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} up -d --build --remove-orphans --wait "$BACKEND_TEST_SERVICE_NAME"
        info "Executing pytest..."
        run_in_backend pytest "$@"
        success "All tests passed."
        ;;
    # --- END OF FIX ---

    *)
        error "Unknown command: '$COMMAND'. Run './scripts/run_app.sh help' for details."
        ;;
esac