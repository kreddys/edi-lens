#!/bin/bash
# ==============================================================================
# EDI LENS - APPLICATION RUNNER SCRIPT (v5)
# ==============================================================================
# Manages all Docker-based environments using an explicit "environment:action"
# command structure (e.g., 'dev:start', 'test:integration').

set -e

# --- Configuration & Helpers ---
PROJECT_ROOT=$(dirname "$0")/..; cd "$PROJECT_ROOT"
COMPOSE_DIR="docker"
info() { echo -e "\033[34m[INFO] $1\033[0m"; }
success() { echo -e "\033[32m[SUCCESS] $1\033[0m"; }
warn() { echo -e "\033[33m[WARN] $1\033[0m"; }
error() { echo -e "\033[31m[ERROR] $1\033[0m" >&2; exit 1; }
check_docker() { if ! docker info >/dev/null 2>&1; then error "Docker is not running."; fi; }
if docker compose version >/dev/null 2>&1; then DC_COMMAND="docker compose"; else DC_COMMAND="docker-compose"; fi

# --- Help Command ---
if [ -z "$1" ] || [[ "$1" == "help" ]] || [[ "$1" == "--help" ]]; then
    echo "EDI Lens Application Runner"
    echo "---------------------------"
    echo "A script to manage the Docker-based development and testing environments."
    echo ""
    echo "USAGE: ./scripts/run_app.sh [environment:action] [options...]"
    echo ""
    echo "=============================================================================="
    echo " ENVIRONMENT-SPECIFIC COMMANDS"
    echo "=============================================================================="
    echo ""
    echo "--- DEVELOPMENT (dev, uses .env.dev) ---"
    echo "  dev:start             Start all dev services with hot-reloading."
    echo "  dev:stop              Stop all dev services (preserves data)."
    echo "  dev:clean             Stop services and DELETE ALL DEV DATA."
    echo "  dev:build [svc...]    Build images for the dev environment."
    echo ""
    echo "--- TESTING (test, uses .env.test) ---"
    echo "  test:start            Start the complete, isolated test stack."
    echo "  test:stop             Stop the test stack (preserves data)."
    echo "  test:clean            Stop and DELETE ALL TEST DATA."
    echo "  test:integration [args...]"
    echo "                        Run in-process integration tests against the test stack."
    echo "  test:e2e [args...]    Run E2E tests against the running test stack."
    echo ""
    echo "=============================================================================="
    echo " SHARED COMMANDS (can be run with 'dev' or 'test' prefix)"
    echo "=============================================================================="
    echo "  Examples: dev:logs, test:migrate:run"
    echo ""
    echo "  <env>:logs [svc...]      Tail logs for the specified environment's services."
    echo "  <env>:migrate:make \"msg\"  Create a new database migration file."
    echo "  <env>:migrate:run        Apply migrations to the database."
    echo "  <env>:setup:keycloak     Configure the Keycloak realm, clients, and users."
    echo "  <env>:setup:testdata     Seed the database with sample trading partners."
    echo "  <env>:schema:review      Analyze and validate the primary 837p schema file."
    echo ""
    echo "=============================================================================="
    echo " SPECIAL COMMANDS (No environment prefix needed)"
    echo "=============================================================================="
    echo "  test:unit [args...]   Run local unit tests (no Docker needed)."
    echo ""
    exit 0
fi

# --- Command & Environment Parsing ---
FULL_COMMAND=$1; shift

# Handle special non-Docker commands first
if [[ "$FULL_COMMAND" == "test:unit" ]]; then
    info "Running local unit tests (no Docker)..."
    
    TEST_ENV_FILE=".env.test"
    if [ ! -f "$TEST_ENV_FILE" ]; then
        if [ -f "$TEST_ENV_FILE.example" ]; then
            warn "Creating .env.test from example for unit test run."
            cp "$TEST_ENV_FILE.example" "$TEST_ENV_FILE"
        else
            error "Could not find '$TEST_ENV_FILE' or its .example file. Cannot run unit tests."
        fi
    fi
    info "Loading .env.test for local unit test session..."
    set -a; source "$TEST_ENV_FILE"; set +a
    
    (cd backend && poetry run pytest -m "unit" "$@")
    
    success "Unit tests finished."
    exit 0
fi

check_docker

ACTION=${FULL_COMMAND#*:}
ENV_CONTEXT=${FULL_COMMAND%%:*}

if [ "$ENV_CONTEXT" == "$ACTION" ]; then
    error "Invalid command format: '$FULL_COMMAND'. Must be 'environment:action' (e.g., 'dev:start')."
fi

# Set environment-specific variables
if [[ "$ENV_CONTEXT" == "test" ]]; then
    ENV_FILE=".env.test"
    BACKEND_SERVICE="backend-test"
    DC_FILES="-f ${COMPOSE_DIR}/docker-compose.test.yml"
else
    ENV_FILE=".env.dev"
    BACKEND_SERVICE="backend"
    DC_FILES="-f ${COMPOSE_DIR}/docker-compose.dev.yml"
fi
info "Selected Environment: $ENV_CONTEXT"

if [ ! -f "$ENV_FILE" ]; then cp "$ENV_FILE.example" "$ENV_FILE"; fi
DC_FLAGS="--project-directory . --env-file ${ENV_FILE}"

# --- Main Command Logic ---
case "$ACTION" in
    "start")
        info "Starting $ENV_CONTEXT services..."
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} up -d --build --remove-orphans --wait
        success "$ENV_CONTEXT environment is up and running."
        ;;
    "logs")
        info "Tailing logs for $ENV_CONTEXT services: $@"
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} logs -f "$@"
        ;;
    "stop")
        info "Stopping $ENV_CONTEXT services..."
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} stop
        ;;
    "clean")
        read -p "⚠️  This will delete all $ENV_CONTEXT data. Are you sure? [y/N] " confirm
        if [[ "$confirm" =~ ^[yY](es)?$ ]]; then ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} down --volumes; fi
        ;;
    "build")
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} build "$@"
        ;;
    "schema:review" | "migrate:make" | "migrate:run" | "setup:keycloak" | "setup:testdata")
        # These commands are now available for BOTH dev and test environments.
        if [ "$ACTION" == "migrate:make" ] && [ -z "$1" ]; then
            error "Migration message is required. Usage: [dev|test]:migrate:make \"your message\""
        fi

        info "Executing '$ACTION' on the $ENV_CONTEXT environment..."
        # Ensure the backend service and its dependencies are running
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} up -d --wait "$BACKEND_SERVICE"

        CMD_TO_RUN=""
        if [ "$ACTION" == "migrate:make" ]; then
            CMD_TO_RUN="alembic -c alembic.ini revision --autogenerate -m \"$1\""
        elif [ "$ACTION" == "migrate:run" ]; then
            CMD_TO_RUN="alembic -c alembic.ini upgrade head"
        elif [ "$ACTION" == "setup:keycloak" ]; then
            CMD_TO_RUN="python -m scripts.setup_keycloak_realm"
        elif [ "$ACTION" == "setup:testdata" ]; then
            CMD_TO_RUN="python -m scripts.seed $@"
        elif [ "$ACTION" == "schema:review" ]; then
            SCHEMA_FILE_PATH="data/edi_schemas_repo/837p_x222a1/manual-validation/schema.json"
            CMD_TO_RUN="python -m scripts.review_schema --schema-file ${SCHEMA_FILE_PATH}"
        fi

        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} exec "$BACKEND_SERVICE" $CMD_TO_RUN
        success "'$ACTION' completed successfully for the '$ENV_CONTEXT' environment."
        ;;
    "integration")
        if [ "$ENV_CONTEXT" != "test" ]; then error "'integration' command is only for the 'test' environment."; fi
        
        if [ -n "$*" ]; then
            info "Running specific integration test file(s): $*"
            TEST_TARGET="$*"
        else
            info "Running all IN-PROCESS integration tests (excluding 'llm' tests)..."
            TEST_TARGET="-m 'integration and not llm'"
        fi

        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} exec "$BACKEND_SERVICE" pytest ${TEST_TARGET}
        success "Integration test run finished."
        ;;
    "e2e")
        if [ "$ENV_CONTEXT" != "test" ]; then error "'e2e' command is only for the 'test' environment."; fi
        
        info "Setting up a clean environment for E2E tests..."
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} down --volumes --remove-orphans
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} up -d --build --wait
        success "Test environment containers are up."

        info "Configuring the test Keycloak instance..."
        sleep 5 
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} exec "$BACKEND_SERVICE" python -m scripts.setup_keycloak_realm
        success "Keycloak is configured."

        info "Verifying backend health before running tests..."
        BACKEND_HEALTH_URL="http://localhost:3001/api/v1/health"
        MAX_RETRIES=45
        RETRY_INTERVAL=5

        for i in $(seq 1 $MAX_RETRIES); do
            STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BACKEND_HEALTH_URL}")
            
            if [ "$STATUS_CODE" -eq 200 ]; then
                success "Backend is healthy and ready to accept requests."
                break
            fi

            if [ "$i" -eq "$MAX_RETRIES" ]; then
                error "Backend did not become healthy after ${i} attempts. Last status: ${STATUS_CODE}."
                ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} logs "$BACKEND_SERVICE"
                ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} down --volumes
                exit 1
            fi

            info "Backend not ready yet (status: ${STATUS_CODE}, attempt ${i}/${MAX_RETRIES}). Retrying..."
            sleep $RETRY_INTERVAL
        done

        info "Running E2E tests..."
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} exec "$BACKEND_SERVICE" pytest -m "e2e" "$@"
        
        info "Tearing down E2E test environment..."
        ${DC_COMMAND} ${DC_FLAGS} ${DC_FILES} down --volumes
        success "E2E tests finished."
        ;;
    *)
        error "Unknown action: '$ACTION' for environment '$ENV_CONTEXT'. Run with 'help' for available commands."
        ;;
esac

success "Command '$FULL_COMMAND' completed successfully."