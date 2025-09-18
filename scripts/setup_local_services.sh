
#!/usr/bin/env bash
# ==============================================================================
# EDI LENS - LOCAL SERVICES SETUP (non-Docker)
# ==============================================================================
# This script provisions local (host-based) equivalents of the services that are
# normally orchestrated via Docker Compose.  It downloads and configures the
# required third-party binaries, prepares per-service start/stop helpers, and
# adjusts environment files so that the backend and frontend can talk to the
# locally running infrastructure.
#
# The script is intentionally idempotent – rerunning it will refresh binaries and
# configuration while preserving data directories.  It targets modern Linux
# distributions with curl, tar, and system utilities available.  macOS users can
# run it under Homebrew with only minor adjustments (e.g., using gnu-tar).
# ==============================================================================
set -euo pipefail

# --- Helper output functions --------------------------------------------------
info()    { printf '[INFO] %s\n' "$1"; }
success() { printf '[SUCCESS] %s\n' "$1"; }
warn()    { printf '[WARN] %s\n' "$1"; }
error()   { printf '[ERROR] %s\n' "$1"; exit 1; }

# --- Usage and CLI helpers ----------------------------------------------------
usage() {
    cat <<'USAGE'
Usage: scripts/setup_local_services.sh [options]

Options:
  --workspace <path>    Override the target workspace directory (default: project/local-services)
  --env-source <path>   Path to the source env file (default: project/.env.dev, copied from example if missing)
  --components <list>   Comma separated list of components to provision (env,postgres,minio,keycloak,sftpgo,backend,
                        frontend,caddy,nifi,nifi-registry,monitoring)
  --env-only            Shorthand for --components env
  --validate            Run validation checks for the selected components after setup (or on an existing setup)
  -h, --help            Show this help message
USAGE
}

PROJECT_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)

resolve_path() {
    local input="$1"
    if [[ "$input" = /* ]]; then
        printf '%s' "$input"
    else
        printf '%s/%s' "$PROJECT_ROOT" "$input"
    fi
}

DEFAULT_LOCAL_STACK_DIR="$PROJECT_ROOT/local-services"
DEFAULT_ENV_SOURCE_FILE="$PROJECT_ROOT/.env.dev"

LOCAL_STACK_DIR="$DEFAULT_LOCAL_STACK_DIR"
ENV_SOURCE_FILE="$DEFAULT_ENV_SOURCE_FILE"
RUN_VALIDATION=0
COMPONENT_SELECTION=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspace)
            shift || error "--workspace requires a path argument"
            [[ -n "${1:-}" ]] || error "--workspace requires a path argument"
            LOCAL_STACK_DIR=$(resolve_path "$1")
            ;;
        --env-source)
            shift || error "--env-source requires a path argument"
            [[ -n "${1:-}" ]] || error "--env-source requires a path argument"
            ENV_SOURCE_FILE=$(resolve_path "$1")
            ;;
        --components)
            shift || error "--components requires a value"
            [[ -n "${1:-}" ]] || error "--components requires a value"
            IFS=',' read -r -a COMPONENT_SELECTION <<< "$1"
            ;;
        --env-only)
            COMPONENT_SELECTION=(env)
            ;;
        --validate)
            RUN_VALIDATION=1
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
    shift || true
 done

LOCAL_STACK_DIR=${LOCAL_STACK_DIR%/}
DOWNLOAD_CACHE="$LOCAL_STACK_DIR/downloads"
LOG_DIR="$LOCAL_STACK_DIR/logs"
LOCAL_ENV_FILE="$LOCAL_STACK_DIR/.env.local"

mkdir -p "$LOCAL_STACK_DIR" "$DOWNLOAD_CACHE" "$LOG_DIR"

ALL_COMPONENTS=(env postgres minio keycloak sftpgo backend frontend caddy nifi nifi-registry monitoring)

sanitize_components() {
    local cleaned=()
    for entry in "${COMPONENT_SELECTION[@]}"; do
        [[ -z "$entry" ]] && continue
        cleaned+=("${entry//[[:space:]]/}")
    done
    COMPONENT_SELECTION=("${cleaned[@]}")
}

should_run_component() {
    local name="$1"
    if [ ${#COMPONENT_SELECTION[@]} -eq 0 ]; then
        return 0
    fi
    for candidate in "${COMPONENT_SELECTION[@]}"; do
        if [[ "$candidate" == "$name" ]]; then
            return 0
        fi
    done
    return 1
}

if [ ${#COMPONENT_SELECTION[@]} -gt 0 ]; then
    sanitize_components
fi

# --- Command helpers ----------------------------------------------------------
require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        error "Required command '$cmd' is not available. Please install it and rerun the script."
    fi
}

curl_download() {
    require_cmd curl
    local url="$1"
    local dest="$2"
    if [ ! -f "$dest" ]; then
        info "Downloading $(basename "$dest")..."
        curl -L "$url" -o "$dest"
    else
        info "Using cached $(basename "$dest")"
    fi
}

extract_tarball() {
    require_cmd tar
    local archive="$1"
    local target_dir="$2"
    local strip_components="${3:-1}"
    if [ ! -d "$target_dir" ]; then
        info "Extracting $(basename "$archive")..."
        mkdir -p "$target_dir"
        tar -xf "$archive" -C "$target_dir" --strip-components="$strip_components"
    else
        info "Archive already extracted: $(basename "$archive")"
    fi
}

write_start_script() {
    local path="$1"; shift
    local body="$*"
    cat <<'SCRIPT_HEADER' > "$path"
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_HEADER
    printf '%s\n' "$body" >> "$path"
    chmod +x "$path"
}

# --- Validation helpers -----------------------------------------------------
VALIDATION_FAILURES=()

record_validation_failure() {
    local message="$1"
    VALIDATION_FAILURES+=("$message")
    warn "$message"
}

http_health_check() {
    local url="$1"
    local name="$2"
    local curl_opts="${3:-}"
    if ! command -v curl >/dev/null 2>&1; then
        record_validation_failure "curl command not available; cannot validate $name"
        return
    fi
    if curl -fsS --max-time 5 $curl_opts "$url" >/dev/null 2>&1; then
        success "$name responded at $url"
    else
        record_validation_failure "$name did not respond at $url"
    fi
}

validate_env() {
    if [ -f "$LOCAL_ENV_FILE" ]; then
        success "Found local environment file at $LOCAL_ENV_FILE"
    else
        record_validation_failure "Environment file missing at $LOCAL_ENV_FILE"
    fi
}

validate_postgres() {
    if ! command -v pg_isready >/dev/null 2>&1; then
        record_validation_failure "pg_isready command not available; install PostgreSQL client utilities"
        return
    fi
    if pg_isready -h 127.0.0.1 -p ${POSTGRES_PORT:-5432} -U "${POSTGRES_USER:-edi_user}" >/dev/null 2>&1; then
        success "PostgreSQL responded on 127.0.0.1:${POSTGRES_PORT:-5432}"
    else
        record_validation_failure "PostgreSQL not accepting connections on 127.0.0.1:${POSTGRES_PORT:-5432}"
    fi
}

validate_minio() {
    http_health_check "http://127.0.0.1:9000/minio/health/live" "MinIO"
}

validate_keycloak() {
    http_health_check "http://127.0.0.1:8180/realms/master/.well-known/openid-configuration" "Keycloak"
}

validate_sftpgo() {
    http_health_check "http://127.0.0.1:8280/healthz" "SFTPGo"
}

validate_backend() {
    http_health_check "http://127.0.0.1:8000/api/v1/health" "Backend API"
}

validate_frontend() {
    http_health_check "http://127.0.0.1:3000" "Frontend"
}

validate_caddy() {
    http_health_check "http://127.0.0.1:3001/api/v1/health" "Caddy reverse proxy"
}

validate_nifi() {
    http_health_check "https://127.0.0.1:8443/nifi-api/system-diagnostics" "NiFi" "-k"
}

validate_nifi_registry() {
    http_health_check "http://127.0.0.1:18081/nifi-registry-api/health" "NiFi Registry"
}

validate_monitoring() {
    if [ -d "$LOCAL_STACK_DIR/monitoring" ]; then
        success "Monitoring assets present under $LOCAL_STACK_DIR/monitoring"
    else
        record_validation_failure "Monitoring assets missing under $LOCAL_STACK_DIR/monitoring"
    fi
}

run_validations() {
    info "Running validation checks for requested components"
    local component
    local ran=0
    for component in "${ALL_COMPONENTS[@]}"; do
        if should_run_component "$component"; then
            local func="validate_${component//-/_}"
            if declare -f "$func" >/dev/null 2>&1; then
                ran=1
                "$func"
            fi
        fi
    done
    if [ $ran -eq 0 ]; then
        warn "No matching validation routines executed. Use --components to target known services."
        return
    fi
    if [ ${#VALIDATION_FAILURES[@]} -gt 0 ]; then
        error "Validation failed for ${#VALIDATION_FAILURES[@]} component(s)."
    else
        success "All requested components passed validation checks."
    fi
}

# --- Environment management ---------------------------------------------------
ensure_env_file() {
    if [ -f "$ENV_SOURCE_FILE" ]; then
        return
    fi

    if [[ "$ENV_SOURCE_FILE" == "$DEFAULT_ENV_SOURCE_FILE" ]] && [ -f "${ENV_SOURCE_FILE}.example" ]; then
        local env_name
        env_name=$(basename "$ENV_SOURCE_FILE")
        warn "Environment file ${env_name} not found – creating from example."
        cp "${ENV_SOURCE_FILE}.example" "$ENV_SOURCE_FILE"
        warn "Remember to update secret values in $ENV_SOURCE_FILE."
    else
        error "Missing $ENV_SOURCE_FILE. Please create it before proceeding or pass --env-source."
    fi
}

load_env() {
    set -a
    # shellcheck disable=SC1090
    source "$ENV_SOURCE_FILE"
    set +a
}

generate_local_env_file() {
    info "Generating host-oriented environment file at $LOCAL_ENV_FILE"

    local postgres_host_local="127.0.0.1"
    local keycloak_internal_host="127.0.0.1"
    local keycloak_internal_port="8180"
    local sftpgo_internal_port="8280"

    cat > "$LOCAL_ENV_FILE" <<EOF
# -----------------------------------------------------------------------------
# AUTO-GENERATED BY scripts/setup_local_services.sh
# This file rewrites container-based hostnames for local (non-Docker) execution.
# Source it before running backend/frontend services:
#   set -a; source local-services/.env.local; set +a
# -----------------------------------------------------------------------------
REMOTE_HOST=localhost
POSTGRES_HOST=$postgres_host_local
POSTGRES_SERVER=$postgres_host_local
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_USER=${POSTGRES_USER:-edi_user}
POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-password}
POSTGRES_DB=${POSTGRES_DB:-edi_lens}
POSTGRES_SFTPGO_USER=${POSTGRES_SFTPGO_USER:-sftpgo_user}
POSTGRES_SFTPGO_PASSWORD=${POSTGRES_SFTPGO_PASSWORD:-password}
POSTGRES_SFTPGO_DB=${POSTGRES_SFTPGO_DB:-sftpgo}
POSTGRES_KC_USER=${POSTGRES_KC_USER:-keycloak_user}
POSTGRES_KC_PASSWORD=${POSTGRES_KC_PASSWORD:-password}
POSTGRES_KC_DB=${POSTGRES_KC_DB:-keycloak}
POSTGRES_NIFI_REGISTRY_DB=${POSTGRES_NIFI_REGISTRY_DB:-nifi_registry}
POSTGRES_NIFI_REGISTRY_USER=${POSTGRES_NIFI_REGISTRY_USER:-nifi_registry}
POSTGRES_NIFI_REGISTRY_PASSWORD=${POSTGRES_NIFI_REGISTRY_PASSWORD:-password}

KEYCLOAK_URL=http://$keycloak_internal_host:$keycloak_internal_port
KEYCLOAK_BROWSER_URL=http://localhost:8081
KEYCLOAK_REALM=${KEYCLOAK_REALM:-edi-lens}
KEYCLOAK_ADMIN=${KEYCLOAK_ADMIN:-admin}
KEYCLOAK_ADMIN_PASSWORD=${KEYCLOAK_ADMIN_PASSWORD:-admin}
KEYCLOAK_BACKEND_CLIENT_ID=${KEYCLOAK_BACKEND_CLIENT_ID:-edi-lens-backend}
KEYCLOAK_BACKEND_CLIENT_SECRET=${KEYCLOAK_BACKEND_CLIENT_SECRET:-secret}
KEYCLOAK_UI_CLIENT_ID=${KEYCLOAK_UI_CLIENT_ID:-edi-lens-ui}
KEYCLOAK_NIFI_CLIENT_ID=${KEYCLOAK_NIFI_CLIENT_ID:-nifi-service}
KEYCLOAK_NIFI_CLIENT_SECRET=${KEYCLOAK_NIFI_CLIENT_SECRET:-nifi-service-secret}
KEYCLOAK_SFTPGO_CLIENT_ID=${KEYCLOAK_SFTPGO_CLIENT_ID:-sftpgo}
KEYCLOAK_SFTPGO_CLIENT_SECRET=${KEYCLOAK_SFTPGO_CLIENT_SECRET:-sftpgo-secret}

SFTPGO_ADMIN_USER=${SFTPGO_ADMIN_USER:-admin}
SFTPGO_ADMIN_PASSWORD=${SFTPGO_ADMIN_PASSWORD:-admin123}
SFTPGO_API_URL=http://127.0.0.1:$sftpgo_internal_port/api/v2
BACKEND_WEBHOOK_URL=http://127.0.0.1:8000/api/v1/sftp/hooks/upload

STORAGE_ACCESS_KEY=${STORAGE_ACCESS_KEY:-minioadmin}
STORAGE_SECRET_KEY=${STORAGE_SECRET_KEY:-minioadmin}
STORAGE_ENDPOINT_URL=http://127.0.0.1:9000
STORAGE_BUCKET=${STORAGE_BUCKET:-edi-lens}
STORAGE_REGION=${STORAGE_REGION:-us-east-1}

VITE_API_URL=http://localhost:3001/api/v1
VITE_KEYCLOAK_URL=http://localhost:8081
VITE_KEYCLOAK_REALM=${KEYCLOAK_REALM:-edi-lens}
VITE_KEYCLOAK_CLIENT_ID=${KEYCLOAK_UI_CLIENT_ID:-edi-lens-ui}

NIFI_URL=http://localhost:8080
NIFI_REGISTRY_URL=http://localhost:18080
NIFI_ADMIN_USER=${NIFI_ADMIN_USER:-admin}
NIFI_ADMIN_PASSWORD=${NIFI_ADMIN_PASSWORD:-admin123}
NIFI_SENSITIVE_PROPS_KEY=${NIFI_SENSITIVE_PROPS_KEY:-12345678901234567890123456789012}
NIFI_JVM_HEAP_INIT=${NIFI_JVM_HEAP_INIT:-1g}
NIFI_JVM_HEAP_MAX=${NIFI_JVM_HEAP_MAX:-2g}
NIFI_WEB_PROXY_HOST=localhost:8080
NIFI_USERNAME=${NIFI_USERNAME:-${NIFI_ADMIN_USER:-admin}}
NIFI_PASSWORD=${NIFI_PASSWORD:-${NIFI_ADMIN_PASSWORD:-admin123}}

# Monitoring endpoints via Caddy
GRAFANA_PUBLIC_URL=http://localhost:3030
PROMETHEUS_PUBLIC_URL=http://localhost:9090
LOKI_PUBLIC_URL=http://localhost:3100
EOF
}

# --- PostgreSQL ---------------------------------------------------------------
setup_postgres() {
    info "Configuring local PostgreSQL cluster"
    require_cmd initdb
    require_cmd pg_ctl
    require_cmd psql

    local pg_dir="$LOCAL_STACK_DIR/postgres"
    local data_dir="$pg_dir/data"
    local log_file="$LOG_DIR/postgres.log"
    local port="${POSTGRES_PORT:-5432}"

    mkdir -p "$pg_dir"

    if [ ! -d "$data_dir/base" ]; then
        info "Initializing PostgreSQL data directory"
        local pwfile
        pwfile=$(mktemp)
        chmod 600 "$pwfile"
        printf '%s' "${POSTGRES_PASSWORD:-password}" > "$pwfile"
        initdb -D "$data_dir" -U "${POSTGRES_USER:-edi_user}" -A scram-sha-256 --pwfile "$pwfile"
        rm -f "$pwfile"

        # Harden pg_hba.conf for password auth on loopback
        cat >> "$data_dir/pg_hba.conf" <<EOF
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256
EOF
        # Listen on loopback only
        cat >> "$data_dir/postgresql.conf" <<EOF
listen_addresses = '127.0.0.1'
port = $port
EOF
    fi

    if ! pg_ctl status -D "$data_dir" >/dev/null 2>&1; then
        info "Starting PostgreSQL"
        pg_ctl -D "$data_dir" -l "$log_file" start
        sleep 3
    else
        info "PostgreSQL already running"
    fi

    local psql_conn=(psql "postgresql://${POSTGRES_USER:-edi_user}:${POSTGRES_PASSWORD:-password}@127.0.0.1:$port/postgres")

    info "Ensuring core extensions and databases exist"

    if [ "${POSTGRES_DB:-edi_lens}" != "postgres" ]; then
        "${psql_conn[@]}" <<SQL
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${POSTGRES_DB:-edi_lens}') THEN
        EXECUTE 'CREATE DATABASE "${POSTGRES_DB:-edi_lens}" OWNER "${POSTGRES_USER:-edi_user}"';
    END IF;
END$$;
SQL
    fi

    "${psql_conn[@]}" <<'SQL'
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
        EXECUTE 'CREATE EXTENSION IF NOT EXISTS vector';
    ELSE
        RAISE NOTICE 'pgvector extension not available – skipping';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'age') THEN
        EXECUTE 'CREATE EXTENSION IF NOT EXISTS age';
    ELSE
        RAISE NOTICE 'Apache AGE extension not available – skipping';
    END IF;
END$$;
SQL

    local db_exists
    db_exists="$("${psql_conn[@]}" -tAc "SELECT 1 FROM pg_database WHERE datname='${POSTGRES_DB:-edi_lens}'" | tr -d '[:space:]')" || db_exists=""
    if [ "$db_exists" = "1" ]; then
        "${psql_conn[@]}" <<SQL
ALTER DATABASE "${POSTGRES_DB:-edi_lens}" SET search_path = ag_catalog, "\$user", public;
SQL
    fi

    "${psql_conn[@]}" <<SQL
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${POSTGRES_KC_DB:-keycloak}') THEN
        EXECUTE 'CREATE DATABASE "${POSTGRES_KC_DB:-keycloak}"';
    END IF;
END$$;
SQL
    "${psql_conn[@]}" <<SQL
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_KC_USER:-keycloak_user}') THEN
        EXECUTE 'CREATE USER "${POSTGRES_KC_USER:-keycloak_user}" WITH PASSWORD ''${POSTGRES_KC_PASSWORD:-password}''';
    END IF;
END$$;
SQL
    psql "postgresql://${POSTGRES_USER:-edi_user}:${POSTGRES_PASSWORD:-password}@127.0.0.1:$port/${POSTGRES_KC_DB:-keycloak}" <<SQL
GRANT ALL PRIVILEGES ON DATABASE "${POSTGRES_KC_DB:-keycloak}" TO "${POSTGRES_KC_USER:-keycloak_user}";
GRANT USAGE, CREATE ON SCHEMA public TO "${POSTGRES_KC_USER:-keycloak_user}";
SQL

    "${psql_conn[@]}" <<SQL
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${POSTGRES_SFTPGO_DB:-sftpgo}') THEN
        EXECUTE 'CREATE DATABASE "${POSTGRES_SFTPGO_DB:-sftpgo}"';
    END IF;
END$$;
SQL
    "${psql_conn[@]}" <<SQL
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_SFTPGO_USER:-sftpgo_user}') THEN
        EXECUTE 'CREATE USER "${POSTGRES_SFTPGO_USER:-sftpgo_user}" WITH PASSWORD ''${POSTGRES_SFTPGO_PASSWORD:-password}''';
    END IF;
END$$;
SQL
    psql "postgresql://${POSTGRES_USER:-edi_user}:${POSTGRES_PASSWORD:-password}@127.0.0.1:$port/${POSTGRES_SFTPGO_DB:-sftpgo}" <<SQL
GRANT ALL PRIVILEGES ON DATABASE "${POSTGRES_SFTPGO_DB:-sftpgo}" TO "${POSTGRES_SFTPGO_USER:-sftpgo_user}";
GRANT USAGE, CREATE ON SCHEMA public TO "${POSTGRES_SFTPGO_USER:-sftpgo_user}";
SQL

    "${psql_conn[@]}" <<SQL
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${POSTGRES_NIFI_REGISTRY_DB:-nifi_registry}') THEN
        EXECUTE 'CREATE DATABASE "${POSTGRES_NIFI_REGISTRY_DB:-nifi_registry}"';
    END IF;
END$$;
SQL
    "${psql_conn[@]}" <<SQL
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='${POSTGRES_NIFI_REGISTRY_USER:-nifi_registry}') THEN
        EXECUTE 'CREATE USER "${POSTGRES_NIFI_REGISTRY_USER:-nifi_registry}" WITH PASSWORD ''${POSTGRES_NIFI_REGISTRY_PASSWORD:-password}''';
    END IF;
END$$;
SQL
    psql "postgresql://${POSTGRES_USER:-edi_user}:${POSTGRES_PASSWORD:-password}@127.0.0.1:$port/${POSTGRES_NIFI_REGISTRY_DB:-nifi_registry}" <<SQL
GRANT ALL PRIVILEGES ON DATABASE "${POSTGRES_NIFI_REGISTRY_DB:-nifi_registry}" TO "${POSTGRES_NIFI_REGISTRY_USER:-nifi_registry}";
GRANT USAGE, CREATE ON SCHEMA public TO "${POSTGRES_NIFI_REGISTRY_USER:-nifi_registry}";
SQL

    success "PostgreSQL configured at 127.0.0.1:$port"
}

setup_minio() {
    info "Preparing MinIO binary and data directory"
    local minio_dir="$LOCAL_STACK_DIR/minio"
    local bin_dir="$LOCAL_STACK_DIR/bin"
    local minio_bin="$bin_dir/minio"
    local mc_bin="$bin_dir/mc"
    mkdir -p "$minio_dir/data" "$bin_dir"

    curl_download "https://dl.min.io/server/minio/release/linux-amd64/minio" "$minio_bin"
    chmod +x "$minio_bin"

    curl_download "https://dl.min.io/client/mc/release/linux-amd64/mc" "$mc_bin"
    chmod +x "$mc_bin"

    write_start_script "$minio_dir/start.sh" "MINIO_ROOT=$minio_dir
BIN_DIR="$bin_dir"
DATA_DIR="$minio_dir/data"
set -a
source "$LOCAL_ENV_FILE"
set +a
export MINIO_ROOT_USER="$STORAGE_ACCESS_KEY"
export MINIO_ROOT_PASSWORD="$STORAGE_SECRET_KEY"
exec "$minio_bin" server "$DATA_DIR" --console-address ":9001" --address ":9000"
"

    write_start_script "$minio_dir/create_bucket.sh" "BIN_DIR="$bin_dir"
set -a
source "$LOCAL_ENV_FILE"
set +a
MINIO_ENDPOINT=${STORAGE_ENDPOINT_URL:-http://127.0.0.1:9000}
BUCKET=${STORAGE_BUCKET:-edi-lens}
ACCESS=${STORAGE_ACCESS_KEY:-minioadmin}
SECRET=${STORAGE_SECRET_KEY:-minioadmin}
"$mc_bin" alias set local-minio "$MINIO_ENDPOINT" "$ACCESS" "$SECRET"
"$mc_bin" mb --ignore-existing local-minio/"$BUCKET"
"$mc_bin" anonymous set public local-minio/"$BUCKET" || true
"

    success "MinIO setup complete (start via $minio_dir/start.sh)"
}

setup_keycloak() {
    info "Installing Keycloak distribution"
    local version="${KEYCLOAK_VERSION:-25.0.2}"
    local archive="$DOWNLOAD_CACHE/keycloak-$version.tar.gz"
    local install_dir="$LOCAL_STACK_DIR/keycloak"
    local kc_home="$install_dir/keycloak-$version"

    mkdir -p "$install_dir"
    curl_download "https://github.com/keycloak/keycloak/releases/download/$version/keycloak-$version.tar.gz" "$archive"
    extract_tarball "$archive" "$install_dir" 1

    write_start_script "$install_dir/start.sh" "ROOT=\$(cd "$(dirname "$0")" && pwd)
KC_HOME="$kc_home"
set -a
source "$LOCAL_ENV_FILE"
set +a
export KEYCLOAK_ADMIN
export KEYCLOAK_ADMIN_PASSWORD
exec "$KC_HOME/bin/kc.sh" start-dev \
  --http-port=8180 \
  --hostname="$REMOTE_HOST" \
  --db=postgres \
  --db-url-host=127.0.0.1 \
  --db-url-port=${POSTGRES_PORT:-5432} \
  --db-username="$POSTGRES_KC_USER" \
  --db-password="$POSTGRES_KC_PASSWORD" \
  --db-url-database="$POSTGRES_KC_DB" \
  --proxy=edge \
  --hostname-strict=false
"

    success "Keycloak available via start script at $install_dir/start.sh"
}

setup_sftpgo() {
    info "Installing SFTPGo"
    local version="2.6.0"
    local archive="$DOWNLOAD_CACHE/sftpgo_${version}_linux_amd64.tar.xz"
    local install_dir="$LOCAL_STACK_DIR/sftpgo"
    local bin_dir="$install_dir/sftpgo"

    mkdir -p "$install_dir"
    curl_download "https://github.com/drakkan/sftpgo/releases/download/v${version}/sftpgo_${version}_linux_amd64.tar.xz" "$archive"
    if [ ! -d "$bin_dir" ]; then
        info "Extracting SFTPGo archive"
        tar -xf "$archive" -C "$install_dir"
    fi

    mkdir -p "$install_dir/data" "$install_dir/state"

    write_start_script "$install_dir/start.sh" "BASE=\$(cd "$(dirname "$0")" && pwd)
BIN="$bin_dir/sftpgo"
set -a
source "$LOCAL_ENV_FILE"
set +a
export SFTPGO_HOME_DIR="$BASE/data"
export SFTPGO_CONFIG_DIR="$BASE/state"
export SFTPGO_DEFAULT_ADMIN_USERNAME="$SFTPGO_ADMIN_USER"
export SFTPGO_DEFAULT_ADMIN_PASSWORD="$SFTPGO_ADMIN_PASSWORD"
export SFTPGO_LOG__LEVEL=info
export SFTPGO_DATA_PROVIDER__DRIVER=postgresql
export SFTPGO_DATA_PROVIDER__NAME="$POSTGRES_SFTPGO_DB"
export SFTPGO_DATA_PROVIDER__HOST=127.0.0.1
export SFTPGO_DATA_PROVIDER__PORT=${POSTGRES_PORT:-5432}
export SFTPGO_DATA_PROVIDER__USERNAME="$POSTGRES_SFTPGO_USER"
export SFTPGO_DATA_PROVIDER__PASSWORD="$POSTGRES_SFTPGO_PASSWORD"
export SFTPGO_DATA_PROVIDER__SSLMODE=0
export SFTPGO_HTTPD__BINDINGS__0__ADDRESS=0.0.0.0
export SFTPGO_HTTPD__BINDINGS__0__PORT=8280
export SFTPGO_HTTPD__BINDINGS__0__OIDC__CLIENT_ID="$KEYCLOAK_SFTPGO_CLIENT_ID"
export SFTPGO_HTTPD__BINDINGS__0__OIDC__CLIENT_SECRET="$KEYCLOAK_SFTPGO_CLIENT_SECRET"
export SFTPGO_HTTPD__BINDINGS__0__OIDC__CONFIG_URL="$KEYCLOAK_URL/realms/$KEYCLOAK_REALM"
export SFTPGO_HTTPD__BINDINGS__0__OIDC__REDIRECT_BASE_URL=http://localhost:8082
export SFTPGO_HTTPD__BINDINGS__0__OIDC__INSECURE_SKIP_SIGNATURE_CHECK=false
export SFTPGO_HTTPD__BINDINGS__0__OIDC__SCOPES=openid,profile,email,groups
export SFTPGO_HTTPD__BINDINGS__0__OIDC__USERNAME_FIELD=preferred_username
export SFTPGO_HTTPD__BINDINGS__0__OIDC__ROLE_FIELD=groups
export SFTPGO_HTTPD__BINDINGS__0__OIDC__AUTO_CREATE_USER=true
exec "$BIN" serve
"

    success "SFTPGo configured with start script at $install_dir/start.sh"
}

setup_backend() {
    info "Setting up Python virtual environment for backend"
    require_cmd python3

    local backend_dir="$PROJECT_ROOT/backend"
    local venv_dir="$LOCAL_STACK_DIR/backend-venv"

    python3 -m venv "$venv_dir"
    source "$venv_dir/bin/activate"
    pip install --upgrade pip
    pip install "poetry==1.8.3"
    (cd "$backend_dir" && poetry install)
    deactivate

    local start_path="$backend_dir/start-local.sh"
    write_start_script "$start_path" "PROJECT_ROOT=\$(cd "$(dirname "$0")/.." && pwd)
VENV="$venv_dir"
set -a
source "$LOCAL_ENV_FILE"
set +a
source "$VENV/bin/activate"
cd "$PROJECT_ROOT/backend"
exec poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src --reload-dir alembic
"

    success "Backend virtualenv ready (start via backend/start-local.sh)"
}

setup_frontend() {
    info "Installing frontend dependencies"
    require_cmd npm

    (cd "$PROJECT_ROOT/frontend" && npm install)

    local start_path="$PROJECT_ROOT/frontend/start-local.sh"
    write_start_script "$start_path" "PROJECT_ROOT=\$(cd "$(dirname "$0")/.." && pwd)
set -a
source "$LOCAL_ENV_FILE"
set +a
cd "$PROJECT_ROOT/frontend"
exec npm run dev -- --host 0.0.0.0 --port 3000
"

    success "Frontend ready (start via frontend/start-local.sh)"
}

setup_caddy() {
    info "Preparing Caddy reverse proxy"
    local bin_dir="$LOCAL_STACK_DIR/bin"
    local caddy_bin="$bin_dir/caddy"
    local caddy_dir="$LOCAL_STACK_DIR/caddy"
    local caddyfile="$caddy_dir/Caddyfile"

    mkdir -p "$bin_dir" "$caddy_dir"
    curl_download "https://github.com/caddyserver/caddy/releases/download/v2.8.4/caddy_2.8.4_linux_amd64.tar.gz" "$DOWNLOAD_CACHE/caddy_2.8.4_linux_amd64.tar.gz"
    if [ ! -f "$caddy_bin" ]; then
        info "Extracting Caddy binary"
        tar -xf "$DOWNLOAD_CACHE/caddy_2.8.4_linux_amd64.tar.gz" -C "$bin_dir" caddy
        chmod +x "$caddy_bin"
    fi

    cat > "$caddyfile" <<'CADDY'
{
    auto_https off
}

:3001 {
    handle /api/* {
        reverse_proxy 127.0.0.1:8000
    }

    handle /metrics {
        reverse_proxy 127.0.0.1:8000
    }

    handle /openapi.json {
        reverse_proxy 127.0.0.1:8000
    }

    handle /docs* {
        reverse_proxy 127.0.0.1:8000
    }

    handle /redoc* {
        reverse_proxy 127.0.0.1:8000
    }

    handle {
        reverse_proxy 127.0.0.1:3000
    }
}

:8081 {
    reverse_proxy 127.0.0.1:8180 {
        header_up X-Forwarded-Host localhost:8081
        header_up X-Forwarded-Proto http
        header_up X-Forwarded-Port 8081
    }
}

:8082 {
    reverse_proxy 127.0.0.1:8280
}

:8080 {
    reverse_proxy https://127.0.0.1:8443 {
        transport http {
            tls_insecure_skip_verify
        }
        header_up Host {upstream_hostport}
        header_up X-ProxyScheme "http"
        header_up X-ProxyHost "localhost:8080"
        header_up X-ProxyPort "8080"
        header_up X-ProxyContextPath ""
        header_up X-Forwarded-Host "localhost:8080"
        header_up X-Forwarded-Proto "http"
        header_up X-Forwarded-Port "8080"
        header_up X-Forwarded-For {remote_host}
        header_up X-Real-IP {remote_host}
    }
    header {
        Access-Control-Allow-Origin "*"
        Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS"
        Access-Control-Allow-Headers "Origin, Content-Type, Accept, Authorization, X-Requested-With"
    }
    @options method OPTIONS
    respond @options 204
}

:18080 {
    reverse_proxy 127.0.0.1:18081
}

:3030 {
    reverse_proxy 127.0.0.1:3030
}

:9090 {
    reverse_proxy 127.0.0.1:9090
}

:3100 {
    reverse_proxy 127.0.0.1:3100
}
CADDY

    write_start_script "$caddy_dir/start.sh" "BIN_DIR="$bin_dir"
CADDYFILE="$caddyfile"
exec "$caddy_bin" run --config "$caddyfile"
"

    success "Caddy configuration ready (start via $caddy_dir/start.sh)"
}

setup_nifi() {
    info "Installing Apache NiFi"
    local version="2.5.0"
    local archive="$DOWNLOAD_CACHE/nifi-$version-bin.tar.gz"
    local install_dir="$LOCAL_STACK_DIR/nifi"
    local nifi_home="$install_dir/nifi-$version"

    mkdir -p "$install_dir"
    curl_download "https://downloads.apache.org/nifi/$version/nifi-$version-bin.tar.gz" "$archive"
    extract_tarball "$archive" "$install_dir" 1

    require_cmd rsync

    local py_ext_dir="$nifi_home/python_extensions/edi-processors"
    mkdir -p "$py_ext_dir"
    for file in "$PROJECT_ROOT"/nifi-edi-processors/*.py; do
        cp "$file" "$py_ext_dir/"
    done
    rsync -a "$PROJECT_ROOT/nifi-edi-processors/schemas" "$py_ext_dir"/
    cp "$PROJECT_ROOT/docker/nifi-processors/login-identity-providers.xml" "$nifi_home/conf/login-identity-providers.xml"

    write_start_script "$install_dir/start.sh" "NIFI_HOME="$nifi_home"
set -a
source "$LOCAL_ENV_FILE"
set +a
if [ \${#NIFI_SENSITIVE_PROPS_KEY} -ne 32 ]; then
    echo "NIFI_SENSITIVE_PROPS_KEY must be 32 characters. Update local-services/.env.local."
    exit 1
fi
export NIFI_WEB_HTTPS_HOST=0.0.0.0
export NIFI_WEB_HTTPS_PORT=8443
export NIFI_WEB_PROXY_HOST="$NIFI_WEB_PROXY_HOST"
export NIFI_WEB_PROXY_CONTEXT_PATH=
export NIFI_SECURITY_USER_LOGIN_IDENTITY_PROVIDER=single-user-provider
export NIFI_SECURITY_USER_AUTHORIZER=single-user-authorizer
export NIFI_JVM_HEAP_INIT="$NIFI_JVM_HEAP_INIT"
export NIFI_JVM_HEAP_MAX="$NIFI_JVM_HEAP_MAX"
export NIFI_SENSITIVE_PROPS_KEY
export NIFI_USERNAME
export NIFI_PASSWORD
export PYTHONPATH="$nifi_home/python_extensions:$nifi_home/python_extensions/edi-processors:$PYTHONPATH"
"$nifi_home/bin/nifi.sh" set-single-user-credentials "$NIFI_USERNAME" "$NIFI_PASSWORD"
exec "$nifi_home/bin/nifi.sh" run
"

    success "NiFi ready (start via $install_dir/start.sh)"
}

setup_nifi_registry() {
    info "Installing Apache NiFi Registry"
    local version="2.5.0"
    local archive="$DOWNLOAD_CACHE/nifi-registry-$version-bin.tar.gz"
    local install_dir="$LOCAL_STACK_DIR/nifi-registry"
    local registry_home="$install_dir/nifi-registry-$version"

    mkdir -p "$install_dir"
    curl_download "https://downloads.apache.org/nifi/nifi-registry/$version/nifi-registry-$version-bin.tar.gz" "$archive"
    extract_tarball "$archive" "$install_dir" 1

    cp "$PROJECT_ROOT/docker/nifi-registry/postgresql-42.7.4.jar" "$registry_home/lib/"

    write_start_script "$install_dir/start.sh" "REGISTRY_HOME="$registry_home"
set -a
source "$LOCAL_ENV_FILE"
set +a
export NIFI_REGISTRY_DB_URL="jdbc:postgresql://127.0.0.1:${POSTGRES_PORT:-5432}/$POSTGRES_NIFI_REGISTRY_DB"
export NIFI_REGISTRY_DB_USER="$POSTGRES_NIFI_REGISTRY_USER"
export NIFI_REGISTRY_DB_PASS="$POSTGRES_NIFI_REGISTRY_PASSWORD"
export NIFI_REGISTRY_WEB_HTTP_HOST=0.0.0.0
export NIFI_REGISTRY_WEB_HTTP_PORT=18081
exec "$registry_home/bin/nifi-registry.sh" run
"

    success "NiFi Registry ready (start via $install_dir/start.sh)"
}

setup_monitoring_configs() {
    info "Preparing monitoring configuration (Grafana, Prometheus, Loki, Promtail)"
    require_cmd rsync
    local monitoring_dir="$LOCAL_STACK_DIR/monitoring"
    mkdir -p "$monitoring_dir"
    rsync -a "$PROJECT_ROOT/docker/monitoring/" "$monitoring_dir/"
    success "Monitoring configuration copied to $monitoring_dir (manual startup required)"
}

print_summary() {
    cat <<'SUMMARY'
-------------------------------------------------------------------------------
Local service setup complete.

Start order suggestion (each in its own terminal):
  1. PostgreSQL (already running via pg_ctl; restart with pg_ctl commands)
  2. local-services/minio/start.sh
  3. local-services/keycloak/start.sh
  4. local-services/sftpgo/start.sh
  5. local-services/nifi-registry/start.sh
  6. local-services/nifi/start.sh
  7. backend/start-local.sh
  8. frontend/start-local.sh
  9. local-services/caddy/start.sh

Optional:
  - Run local-services/minio/create_bucket.sh once MinIO is up to provision the
    bucket used by the backend.
  - Monitoring assets are available under local-services/monitoring/.

Remember to stop services using their respective helper scripts or the
application-native commands.
-------------------------------------------------------------------------------
SUMMARY
}

ensure_env_file
load_env

any_component_run=0
services_prepared=0

if should_run_component env; then
    generate_local_env_file
    any_component_run=1
fi

if should_run_component postgres; then
    setup_postgres
    any_component_run=1
    services_prepared=1
fi
if should_run_component minio; then
    setup_minio
    any_component_run=1
    services_prepared=1
fi
if should_run_component keycloak; then
    setup_keycloak
    any_component_run=1
    services_prepared=1
fi
if should_run_component sftpgo; then
    setup_sftpgo
    any_component_run=1
    services_prepared=1
fi
if should_run_component backend; then
    setup_backend
    any_component_run=1
    services_prepared=1
fi
if should_run_component frontend; then
    setup_frontend
    any_component_run=1
    services_prepared=1
fi
if should_run_component caddy; then
    setup_caddy
    any_component_run=1
    services_prepared=1
fi
if should_run_component nifi; then
    setup_nifi
    any_component_run=1
    services_prepared=1
fi
if should_run_component nifi-registry; then
    setup_nifi_registry
    any_component_run=1
    services_prepared=1
fi
if should_run_component monitoring; then
    setup_monitoring_configs
    any_component_run=1
    services_prepared=1
fi

if [ $RUN_VALIDATION -eq 1 ]; then
    run_validations
fi

if [ $services_prepared -eq 1 ]; then
    print_summary
    success "All requested components prepared."
elif [ $any_component_run -eq 1 ]; then
    success "Requested component preparation completed."
elif [ $RUN_VALIDATION -eq 1 ]; then
    success "Validation completed."
else
    warn "No components selected for setup. Pass --components to target services."
fi
