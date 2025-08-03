#!/bin/bash
# ==============================================================================
# EDI LENS - APPLICATION RUNNER SCRIPT (v17 - Profile-Based Task Orchestration)
# ==============================================================================
# Manages all environments from the project root.
# Uses a base compose file and orchestrates one-off setup tasks using profiles.
# Enforces isolation via Docker Compose project names.

set -e

# --- Configuration & Helpers ---
PROJECT_ROOT=$(cd "$(dirname "$0")" && pwd)
cd "$PROJECT_ROOT"
info() { echo -e "\033[34m[INFO] $1\033[0m"; }
success() { echo -e "\033[32m[SUCCESS] $1\033[0m"; }
warn() { echo -e "\033[33m[WARN] $1\033[0m"; }
error() { echo -e "\033[31m[ERROR] $1\033[0m" >&2; exit 1; }
check_docker() { if ! docker info >/dev/null 2>&1; then error "Docker is not running."; fi; }
if docker compose version >/dev/null 2>&1; then DC_COMMAND="docker compose"; else DC_COMMAND="docker-compose"; fi

# ==============================================================================
# SCRIPT ENTRYPOINT & DISPATCHER
# ==============================================================================

if [ -z "$1" ] || [[ "$1" == "help" ]] || [[ "$1" == "--help" ]]; then
    echo "EDI Lens Application Runner"
    echo "---------------------------"
    echo "USAGE: ./run.sh [environment:action] [options...]"
    echo ""
    echo "ENVIRONMENTS:"
    echo "  dev       Your local workspace for development and all automated testing."
    echo "  stg       Staging env using production images for local verification."
    echo "  prod      Production environment."
    echo ""
    echo "COMMON ACTIONS (e.g., dev:start, stg:logs):"
    echo "  start, stop, clean, build, logs, migrate:make \"msg\", migrate:run, setup:keycloak, setup:seed"
    echo ""
    echo "SFTP ACTIONS (dev environment only) - SECURE:"
    echo "  dev:sftp:process --auth-token TOKEN --tenant TENANT --list-partners"
    echo "  dev:sftp:process --auth-token TOKEN --tenant TENANT --partner NAME --process-files"
    echo "  dev:sftp:process --auth-token TOKEN --tenant TENANT --process-all"
    echo ""
    echo "LEGACY SFTP ACTIONS (DEPRECATED - USE SECURE VERSION):"
    echo "  dev:sftp:legacy --tenant TENANT --partner PARTNER     Process files (NO AUTH - DEV ONLY)"
    echo ""
    echo "TESTING ACTIONS (dev environment only):"
    echo "  dev:test unit [args...]         Run local unit tests (no Docker needed)."
    echo "  dev:test integration [args...]  Run integration tests against the dev stack."
    echo "  dev:test e2e [args...]          Run end-to-end tests against the dev stack."
    exit 0
fi

FULL_COMMAND=$1; shift
ACTION=${FULL_COMMAND#*:}
ENV_CONTEXT=${FULL_COMMAND%%:*}

if [ "$ENV_CONTEXT" == "$ACTION" ]; then error "Invalid command format: '$FULL_COMMAND'. Use 'env:action'."; fi

# --- Set environment-specific variables ---
case "$ENV_CONTEXT" in
    dev)
        PROJECT_NAME="edi-lens-dev"
        ENV_FILE=".env.dev"
        DC_FILES="-f docker/docker-compose.yml"
        BACKEND_SERVICE="backend"
        ;;
    stg)
        PROJECT_NAME="edi-lens-stg"
        ENV_FILE=".env.stg"
        DC_FILES="-f docker/docker-compose.yml -f docker/docker-compose.stg.yml"
        BACKEND_SERVICE="backend"
        ;;
    prod)
        PROJECT_NAME="edi-lens-prod"
        ENV_FILE=".env.prod"
        DC_FILES="-f docker/docker-compose.yml -f docker/docker-compose.prod.yml"
        BACKEND_SERVICE="backend"
        ;;
    *)
        error "Unknown environment: '$ENV_CONTEXT'. Must be one of: dev, stg, prod."
        ;;
esac
info "Configuring for [$ENV_CONTEXT] environment (Project: $PROJECT_NAME)..."

check_docker
if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_FILE.example" ]; then
        warn "Creating '$ENV_FILE' from example."
        cp "$ENV_FILE.example" "$ENV_FILE"
    else
        error "Environment file '$ENV_FILE' is required."
    fi
fi

DC_EXEC="${DC_COMMAND} -p ${PROJECT_NAME} ${DC_FILES} --env-file ${ENV_FILE}"

# --- THIS IS THE UPDATED HELPER FUNCTION ---
# Runs one-off setup tasks defined by the 'setup' profile.
ensure_infra() {
    info "Ensuring one-off infrastructure tasks are complete..."
    # 'docker compose run' will automatically start any 'depends_on' services (like minio).
    # The --rm flag is critical: it ensures the container is removed after it exits.
    # We explicitly run the service by name. If it has a profile, 'run' will still execute it.
    $DC_EXEC run --rm create-minio-bucket
    info "Infrastructure tasks are up to date."
}
# --- END OF UPDATE ---

# ==============================================================================
# CENTRAL COMMAND LOGIC
# ==============================================================================

case "$ACTION" in
    start)
        # Call the setup function before starting the main services
        ensure_infra
        $DC_EXEC up -d --build --remove-orphans --wait
        ;;
    stop)
        $DC_EXEC stop
        ;;
    clean)
        read -p "⚠️  This will DELETE ALL DATA for [$ENV_CONTEXT]. Are you sure? [y/N] " confirm
        if [[ "$confirm" =~ ^[yY](es)?$ ]]; then $DC_EXEC down --volumes; fi
        ;;
    build)
        $DC_EXEC build "$@"
        ;;
    logs)
        $DC_EXEC logs -f "$@"
        ;;
    migrate:make|migrate:run|setup:keycloak|setup:seed)
        if [ "$ACTION" == "migrate:make" ] && [ -z "$1" ]; then error "Migration message is required."; fi
        
        # Ensure infrastructure is ready before running commands that might depend on it
        ensure_infra
        info "Ensuring backend service is running for command..."
        $DC_EXEC up -d --wait "$BACKEND_SERVICE"
        
        info "Executing command inside the '$BACKEND_SERVICE' container..."
        if [ "$ACTION" == "migrate:make" ]; then
            $DC_EXEC exec "$BACKEND_SERVICE" alembic -c alembic.ini revision --autogenerate -m "$1"
        elif [ "$ACTION" == "migrate:run" ]; then
            $DC_EXEC exec "$BACKEND_SERVICE" alembic -c alembic.ini upgrade head
        elif [ "$ACTION" == "setup:keycloak" ]; then
            $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.setup_keycloak_realm
        elif [ "$ACTION" == "setup:seed" ]; then
            $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.seed "$@"
        fi
        ;;
    sftp:process)
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'sftp:process' action is only for the 'dev' environment."; fi
        if [ -z "$1" ]; then error "SFTP process requires arguments. Use --help for usage."; fi
        
        # Ensure infrastructure is ready
        ensure_infra
        info "Ensuring backend service is running for secure SFTP processing..."
        $DC_EXEC up -d --wait "$BACKEND_SERVICE"
        
        info "Running SECURE multi-tenant SFTP file processor..."
        warn "This processor requires valid JWT authentication tokens"
        $DC_EXEC exec "$BACKEND_SERVICE" python scripts/secure_sftp_processor.py "$@"
        ;;
    sftp:legacy)
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'sftp:legacy' action is only for the 'dev' environment."; fi
        if [ -z "$1" ]; then error "Legacy SFTP process requires arguments."; fi
        
        warn "⚠️  USING LEGACY SFTP PROCESSOR - NO AUTHENTICATION!"
        warn "⚠️  THIS IS FOR DEVELOPMENT ONLY - NOT SECURE!"
        read -p "Continue with insecure legacy processor? [y/N] " confirm
        if [[ ! "$confirm" =~ ^[yY](es)?$ ]]; then
            info "Operation cancelled"
            exit 0
        fi
        
        # Ensure infrastructure is ready
        ensure_infra
        info "Ensuring backend service is running for legacy SFTP processing..."
        $DC_EXEC up -d --wait "$BACKEND_SERVICE"
        
        warn "Running LEGACY (INSECURE) SFTP file processor..."
        $DC_EXEC exec "$BACKEND_SERVICE" python scripts/manual_sftp_processor_v2.py "$@"
        ;;
    test)
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'test' action is only for the 'dev' environment."; fi
        TEST_TYPE=$1; shift
        case "$TEST_TYPE" in
            unit)
                info "Running local unit tests (no Docker needed)..."
                info "Loading .env.dev for the local test session..."
                set -a; source "$ENV_FILE"; set +a                
                (cd backend && poetry run pytest -m "unit" "$@")
                ;;
            integration|e2e)
                # Ensure infrastructure is ready before running tests
                ensure_infra
                info "Ensuring dev stack is running for '$TEST_TYPE' tests..."
                $DC_EXEC up -d --build --wait backend
                if [[ "$TEST_TYPE" == "e2e" ]]; then
                    info "Configuring Keycloak for E2E tests..."
                    sleep 5
                    $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.setup_keycloak_realm
                fi
                $DC_EXEC exec "$BACKEND_SERVICE" pytest -m "$TEST_TYPE" "$@"
                ;;
            *) error "Unknown test type: '$TEST_TYPE'. Must be 'unit', 'integration', or 'e2e'." ;;
        esac
        ;;
    *)
        error "Unknown action: '$ACTION' for environment '$ENV_CONTEXT'."
        ;;
esac

success "Action '$ACTION' for environment '$ENV_CONTEXT' completed."