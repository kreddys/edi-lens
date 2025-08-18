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
timestamp() { echo -e "\033[36m[$(date '+%H:%M:%S')] $1\033[0m"; }
timing_info() { echo -e "\033[35m[TIMING $(date '+%H:%M:%S')] $1\033[0m"; }
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
    echo "  start, stop, clean, build, logs, migrate:make \"msg\", migrate:run, setup:keycloak, setup:sftpgo, setup:seed, setup:templates"
    echo "  db:exec \"command\"           Execute SQL command in database (dev only)"
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
    echo "  dev:test ui [args...]           Run UI tests (Jest + React Testing Library). Logs saved to tmp/ui-test-logs-*/"
    echo "  dev:test ui:workflows           Run workflow component tests specifically. Logs saved to tmp/ui-workflow-test-logs-*/"
    echo "  dev:test ui:integration         Run UI-backend integration tests. Logs saved to tmp/ui-integration-test-logs-*/"
    echo "  dev:test ui:legacy              Run legacy UI component tests. Logs saved to tmp/ui-legacy-test-logs-*/"
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
        DB_SERVICE="db-app"
        ;;
    stg)
        PROJECT_NAME="edi-lens-stg"
        ENV_FILE=".env.stg"
        DC_FILES="-f docker/docker-compose.yml -f docker/docker-compose.stg.yml"
        BACKEND_SERVICE="backend"
        DB_SERVICE="db-app"
        ;;
    prod)
        PROJECT_NAME="edi-lens-prod"
        ENV_FILE=".env.prod"
        DC_FILES="-f docker/docker-compose.yml -f docker/docker-compose.prod.yml"
        BACKEND_SERVICE="backend"
        DB_SERVICE="db-app"
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
    $DC_EXEC run --rm nifi-registry-init
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
        START_TIME=$(date +%s)
        timing_info "🚀 Starting EDI Lens development environment..."
        
        # --- INFRASTRUCTURE SETUP ---
        timing_info "Step 1/4: Infrastructure setup (MinIO, NiFi Registry permissions)"
        INFRA_START=$(date +%s)
        info "Ensuring one-off infrastructure tasks (MinIO bucket, NiFi Registry permissions) are complete..."
        # Run infrastructure tasks - using sequential execution for reliability
        info "Setting up MinIO bucket..."
        $DC_EXEC run --rm create-minio-bucket
        info "Fixing NiFi Registry permissions..."
        $DC_EXEC run --rm nifi-registry-init
        
        INFRA_END=$(date +%s)
        timing_info "✅ Infrastructure setup completed in $((INFRA_END - INFRA_START)) seconds"

        # --- CORE SERVICES ---
        timing_info "Step 2/4: Core services startup (DBs, Keycloak, Backend)"
        CORE_START=$(date +%s)
        
        # Start databases first
        info "Starting database..."
        DB_START=$(date +%s)
        $DC_EXEC up -d --build --remove-orphans --wait db
        DB_END=$(date +%s)
        timing_info "🗄️  Database ready in $((DB_END - DB_START)) seconds"
        
        # Then start Keycloak and Backend
        info "Starting Keycloak and Backend..."
        APP_START=$(date +%s)
        $DC_EXEC up -d --wait keycloak backend
        APP_END=$(date +%s)
        timing_info "🔐 Keycloak and Backend ready in $((APP_END - APP_START)) seconds"
        
        CORE_END=$(date +%s)
        timing_info "✅ Core services healthy in $((CORE_END - CORE_START)) seconds"

        # --- KEYCLOAK SETUP ---
        timing_info "Step 3/4: Keycloak realm configuration"
        KC_START=$(date +%s)
        info "Running one-time Keycloak realm setup..."
        # Now that the backend is healthy, we can safely execute the setup script.
        $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.setup_keycloak_realm
        KC_END=$(date +%s)
        timing_info "✅ Keycloak setup completed in $((KC_END - KC_START)) seconds"

        # --- TEMPLATE SEEDING ---
        timing_info "Step 3.5/4: Seeding built-in workflow templates"
        SEED_START=$(date +%s)
        info "Seeding built-in workflow templates..."
        # Seed built-in templates
        $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.seed_templates built-in
        SEED_END=$(date +%s)
        timing_info "✅ Template seeding completed in $((SEED_END - SEED_START)) seconds"

        # --- REMAINING SERVICES ---
        timing_info "Step 4/4: Starting remaining services (SFTPGo, UI, Caddy, NiFi)"
        REMAINING_START=$(date +%s)
        
        # Start lightweight services first
        info "Starting UI, SFTPGo, and Caddy..."
        LIGHT_START=$(date +%s)
        $DC_EXEC up -d --wait frontend sftpgo caddy
        LIGHT_END=$(date +%s)
        timing_info "🚀 Lightweight services ready in $((LIGHT_END - LIGHT_START)) seconds"
        
        # Start NiFi services (heaviest) last
        info "Starting NiFi Registry and NiFi (this may take longer)..."
        NIFI_START=$(date +%s)
        $DC_EXEC up -d --wait nifi-registry nifi
        NIFI_END=$(date +%s)
        timing_info "🔄 NiFi services ready in $((NIFI_END - NIFI_START)) seconds"
        
        REMAINING_END=$(date +%s)
        timing_info "✅ All services healthy in $((REMAINING_END - REMAINING_START)) seconds"
        
        END_TIME=$(date +%s)
        TOTAL_TIME=$((END_TIME - START_TIME))
        success "🎉 All services started and configured successfully!"
        timing_info "📊 TOTAL STARTUP TIME: ${TOTAL_TIME} seconds"
        timing_info "📋 Breakdown: Infra(${INFRA_END-INFRA_START}s) + Core(${CORE_END-CORE_START}s) + Keycloak(${KC_END-KC_START}s) + Remaining(${REMAINING_END-REMAINING_START}s)"
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
    logs:recent)
        check_docker
        $DC_EXEC logs --tail 50 "$@"
        ;;
    # --- setup:keycloak is now primarily for re-running the setup on an already running system ---
    migrate:make|migrate:run|setup:keycloak|setup:sftpgo|setup:seed|setup:templates|db:exec)
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
        elif [ "$ACTION" == "setup:templates" ]; then
            info "Seeding built-in workflow templates..."
            $DC_EXEC exec "$BACKEND_SERVICE" python -m scripts.seed_templates built-in
        elif [ "$ACTION" == "db:exec" ]; then
            if [ "$ENV_CONTEXT" != "dev" ]; then error "'db:exec' action is only for the 'dev' environment."; fi
            if [ -z "$1" ]; then error "SQL command is required for db:exec."; fi
            info "Executing SQL command in database..."
            # Load environment variables safely to get database config
            set -a  # automatically export all variables
            source "$ENV_FILE"
            set +a  # turn off automatic export
            $DC_EXEC exec "$DB_SERVICE" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "$1"
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
                
                # Create temp directory for detailed logs within project
                UI_LOG_DIR="$PROJECT_ROOT/tmp/ui-test-logs-$(date +%Y%m%d-%H%M%S)"
                mkdir -p "$UI_LOG_DIR"
                info "Detailed logs will be saved to: $UI_LOG_DIR"
                
                # Redirect verbose output to log files for cleaner console output
                $DC_EXEC up -d --build --wait frontend 2>"$UI_LOG_DIR/docker-build.log" >"$UI_LOG_DIR/docker-output.log"
                
                info "Running Jest tests in frontend container..."
                $DC_EXEC exec frontend npm run test -- --watchAll=false --coverage "$@" 2>"$UI_LOG_DIR/test-errors.log" | tee "$UI_LOG_DIR/test-output.log"
                test_exit_code=$?
                
                # Check if Jest reported coverage threshold failures
                if grep -q "coverage threshold.*not met" "$UI_LOG_DIR/test-errors.log"; then
                    echo -e "\033[31m[ERROR] UI tests failed: Coverage thresholds not met. Check logs in: $UI_LOG_DIR\033[0m" >&2
                    echo -e "\033[34m[INFO] Coverage threshold failures detected in test-errors.log\033[0m"
                    echo -e "\033[34m[INFO] Key log files:\033[0m"
                    echo -e "\033[34m[INFO]   - Test output: $UI_LOG_DIR/test-output.log\033[0m"
                    echo -e "\033[34m[INFO]   - Test errors: $UI_LOG_DIR/test-errors.log\033[0m" 
                    echo -e "\033[34m[INFO]   - Docker build: $UI_LOG_DIR/docker-build.log\033[0m"
                    exit 1
                elif [ $test_exit_code -ne 0 ]; then
                    echo -e "\033[31m[ERROR] UI tests failed with exit code $test_exit_code. Check logs in: $UI_LOG_DIR\033[0m" >&2
                    echo -e "\033[34m[INFO] Key log files:\033[0m"
                    echo -e "\033[34m[INFO]   - Test output: $UI_LOG_DIR/test-output.log\033[0m"
                    echo -e "\033[34m[INFO]   - Test errors: $UI_LOG_DIR/test-errors.log\033[0m" 
                    echo -e "\033[34m[INFO]   - Docker build: $UI_LOG_DIR/docker-build.log\033[0m"
                    exit $test_exit_code
                else
                    success "UI tests completed successfully!"
                    info "Test logs saved to: $UI_LOG_DIR"
                fi
                ;;
            ui:workflows)
                check_docker
                info "Running NiFi Workflow component tests..."
                ensure_infra
                info "Ensuring dev stack is running for workflow tests..."
                
                # Create temp directory for detailed logs within project
                UI_LOG_DIR="$PROJECT_ROOT/tmp/ui-workflow-test-logs-$(date +%Y%m%d-%H%M%S)"
                mkdir -p "$UI_LOG_DIR"
                info "Detailed logs will be saved to: $UI_LOG_DIR"
                
                $DC_EXEC up -d --build --wait frontend 2>"$UI_LOG_DIR/docker-build.log" >"$UI_LOG_DIR/docker-output.log"
                
                info "Running workflow component tests..."
                if $DC_EXEC exec frontend npm run test -- --watchAll=false --testNamePattern="Workflow" --coverage "$@" 2>"$UI_LOG_DIR/test-errors.log" | tee "$UI_LOG_DIR/test-output.log"; then
                    success "Workflow tests completed successfully!"
                    info "Test logs saved to: $UI_LOG_DIR"
                else
                    error_code=$?
                    echo -e "\033[31m[ERROR] Workflow tests failed with exit code $error_code. Check logs in: $UI_LOG_DIR\033[0m" >&2
                    echo -e "\033[34m[INFO] Check logs in: $UI_LOG_DIR\033[0m"
                    exit $error_code
                fi
                ;;
            ui:integration)
                check_docker
                info "Running UI-Backend integration tests..."
                ensure_infra
                info "Ensuring full dev stack is running for integration tests..."
                
                # Create temp directory for detailed logs within project
                UI_LOG_DIR="$PROJECT_ROOT/tmp/ui-integration-test-logs-$(date +%Y%m%d-%H%M%S)"
                mkdir -p "$UI_LOG_DIR"
                info "Detailed logs will be saved to: $UI_LOG_DIR"
                
                $DC_EXEC up -d --wait backend frontend 2>"$UI_LOG_DIR/docker-build.log" >"$UI_LOG_DIR/docker-output.log"
                
                info "Running NiFi workflow integration tests..."
                if $DC_EXEC exec frontend npm run test -- --watchAll=false --testNamePattern="NiFi.*Integration" --coverage "$@" 2>"$UI_LOG_DIR/test-errors.log" | tee "$UI_LOG_DIR/test-output.log"; then
                    success "UI integration tests completed successfully!"
                    info "Test logs saved to: $UI_LOG_DIR"
                else
                    error_code=$?
                    echo -e "\033[31m[ERROR] UI integration tests failed with exit code $error_code. Check logs in: $UI_LOG_DIR\033[0m" >&2
                    echo -e "\033[34m[INFO] Check logs in: $UI_LOG_DIR\033[0m"
                    exit $error_code
                fi
                ;;
            ui:legacy)
                check_docker
                info "Running legacy UI component tests..."
                ensure_infra
                info "Ensuring dev stack is running for legacy tests..."
                
                # Create temp directory for detailed logs within project
                UI_LOG_DIR="$PROJECT_ROOT/tmp/ui-legacy-test-logs-$(date +%Y%m%d-%H%M%S)"
                mkdir -p "$UI_LOG_DIR"
                info "Detailed logs will be saved to: $UI_LOG_DIR"
                
                $DC_EXEC up -d --build --wait frontend 2>"$UI_LOG_DIR/docker-build.log" >"$UI_LOG_DIR/docker-output.log"
                
                info "Running legacy component tests..."
                if $DC_EXEC exec frontend npm run test -- --watchAll=false --testNamePattern="Legacy UI" --coverage "$@" 2>"$UI_LOG_DIR/test-errors.log" | tee "$UI_LOG_DIR/test-output.log"; then
                    success "Legacy UI tests completed successfully!"
                    info "Test logs saved to: $UI_LOG_DIR"
                else
                    error_code=$?
                    echo -e "\033[31m[ERROR] Legacy UI tests failed with exit code $error_code. Check logs in: $UI_LOG_DIR\033[0m" >&2
                    echo -e "\033[34m[INFO] Check logs in: $UI_LOG_DIR\033[0m"
                    exit $error_code
                fi
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