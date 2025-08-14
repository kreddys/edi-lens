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
    echo "  start, stop, clean, build, logs, migrate:make \"msg\", migrate:run, setup:keycloak, setup:sftpgo, setup:seed"
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
    echo "  dev:test unit [args...]         Run backend unit tests (no Docker needed)."
    echo "  dev:test integration [args...]  Run backend integration tests against the dev stack."
    echo "  dev:test e2e [args...]          Run backend end-to-end tests against the dev stack."
    echo "  dev:test ui [args...]           Run UI tests (Jest + React Testing Library)."
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
    check_docker
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

# ==============================================================================
# CENTRAL COMMAND LOGIC
# ==============================================================================

case "$ACTION" in
    start)
        check_docker
        # --- THIS IS THE NEW, ORCHESTRATED STARTUP SEQUENCE ---
        info "Ensuring one-off infrastructure tasks (MinIO bucket) are complete..."
        # We run this separately to ensure MinIO is ready.
        $DC_EXEC run --rm create-minio-bucket

        info "Starting core services (DBs, Keycloak, Backend)..."
        # Start only the core services first and wait for them to be healthy.
        # This prevents dependent services from starting too early.
        $DC_EXEC up -d --build --remove-orphans --wait db-keycloak db-app keycloak backend

        info "Running one-time Keycloak realm setup..."
        # Now that the backend is healthy, we can safely execute the setup script.
        $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.setup_keycloak_realm

        info "Starting all remaining services (SFTPGo, UI, Caddy)..."
        # Run 'up' again. Docker Compose is smart and will only start the services
        # that aren't already running. SFTPGo will now start correctly because the
        # backend is healthy and the realm exists.
        $DC_EXEC up -d --wait
        
        success "All services started and configured successfully."
        # --- END OF NEW STARTUP SEQUENCE ---
        ;;
    stop)
        check_docker
        $DC_EXEC stop
        ;;
    clean)
        check_docker
        read -p "⚠️  This will DELETE ALL DATA for [$ENV_CONTEXT]. Are you sure? [y/N] " confirm
        if [[ "$confirm" =~ ^[yY](es)?$ ]]; then $DC_EXEC down --volumes; fi
        ;;
    build)
        check_docker
        $DC_EXEC build "$@"
        ;;
    logs)
        check_docker
        $DC_EXEC logs -f "$@"
        ;;
    # --- setup:keycloak is now primarily for re-running the setup on an already running system ---
    migrate:make|migrate:run|setup:keycloak|setup:sftpgo|setup:seed)
        check_docker
        if [ "$ACTION" == "migrate:make" ] && [ -z "$1" ]; then error "Migration message is required."; fi
        
        info "Ensuring backend service is running for command..."
        $DC_EXEC up -d --wait "$BACKEND_SERVICE"
        
        info "Executing command inside the '$BACKEND_SERVICE' container..."
        if [ "$ACTION" == "migrate:make" ]; then
            $DC_EXEC exec "$BACKEND_SERVICE" alembic -c alembic.ini revision --autogenerate -m "$1"
        elif [ "$ACTION" == "migrate:run" ]; then
            $DC_EXEC exec "$BACKEND_SERVICE" alembic -c alembic.ini upgrade head
        elif [ "$ACTION" == "setup:keycloak" ]; then
            $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.setup_keycloak_realm
        elif [ "$ACTION" == "setup:sftpgo" ]; then
            info "Setting up SFTPGo event configuration for real-time processing..."
            $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.setup_sftpgo_events
        elif [ "$ACTION" == "setup:seed" ]; then
            $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.seed "$@"
        fi
        ;;
    sftp:process)
        check_docker
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'sftp:process' action is only for the 'dev' environment."; fi
        info "Ensuring backend service is running for SFTP processing..."
        $DC_EXEC up -d --wait "$BACKEND_SERVICE"
        info "Running SFTP file processor..."
        $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.manual_sftp_processor_v2 --run "$@"
        ;;
    test)
        if [ "$ENV_CONTEXT" != "dev" ]; then error "'test' action is only for the 'dev' environment."; fi
        TEST_TYPE=$1; shift
        case "$TEST_TYPE" in
            unit)
                info "Running backend unit tests (no Docker needed)..."
                info "Loading .env.dev for the local test session..."
                set -a; source "$ENV_FILE"; set +a                
                (cd backend && poetry run pytest -m "unit" "$@")
                ;;
            ui)
                check_docker
                info "Running UI tests in Docker with Jest and React Testing Library..."
                ensure_infra
                info "Ensuring dev stack is running for UI tests..."
                $DC_EXEC up -d --build --wait admin-ui
                
                info "Running Jest tests in admin-ui container..."
                $DC_EXEC exec admin-ui npm run test -- --watchAll=false --coverage "$@"
                ;;
            integration|e2e)
                check_docker
                # Ensure infrastructure is ready before running tests
                ensure_infra
                info "Ensuring dev stack is running for '$TEST_TYPE' tests..."
                $DC_EXEC up -d --wait backend
                if [[ "$TEST_TYPE" == "e2e" ]]; then
                    info "Configuring Keycloak for E2E tests..."
                    sleep 5
                    $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.setup_keycloak_realm
                    info "Configuring SFTPGo events for E2E tests..."
                    $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.setup_sftpgo_events
                fi
                $DC_EXEC exec "$BACKEND_SERVICE" pytest -m "$TEST_TYPE" "$@"
                ;;
            *) error "Unknown test type: '$TEST_TYPE'. Must be 'unit', 'ui', 'integration', or 'e2e'." ;;
        esac
        ;;
    *)
        error "Unknown action: '$ACTION' for environment '$ENV_CONTEXT'."
        ;;
esac

success "Action '$ACTION' for environment '$ENV_CONTEXT' completed."