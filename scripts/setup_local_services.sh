
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
  --install             Explicitly trigger the installation flow (default)
  --uninstall           Remove all artifacts produced by this script
  --reinstall           Remove all artifacts and then perform a fresh installation
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
ACTION="install"

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
        --install)
            ACTION="install"
            ;;
        --uninstall)
            ACTION="uninstall"
            ;;
        --reinstall)
            ACTION="reinstall"
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

POSTGRES_BIN_DIR=""

ensure_postgres_binaries_in_path() {
    local initdb_path
    initdb_path=$(command -v initdb 2>/dev/null || true)
    if [ -n "$initdb_path" ]; then
        POSTGRES_BIN_DIR=$(dirname "$initdb_path")
        return
    fi

    if command -v pg_config >/dev/null 2>&1; then
        local bindir
        bindir=$(pg_config --bindir 2>/dev/null || true)
        if [ -n "$bindir" ] && [ -d "$bindir" ]; then
            POSTGRES_BIN_DIR="$bindir"
            if [[ ":$PATH:" != *":$bindir:"* ]]; then
                PATH="$bindir:$PATH"
                export PATH
            fi
        fi
    fi
}

run_as_user() {
    local target_user="$1"
    shift
    local current_user
    current_user=$(id -un 2>/dev/null || whoami 2>/dev/null || printf 'unknown')

    if [ "$target_user" = "$current_user" ] || [ -z "$target_user" ]; then
        "$@"
        return
    fi

    if command -v sudo >/dev/null 2>&1; then
        sudo -E -u "$target_user" -- "$@"
    else
        su -s /bin/bash "$target_user" -c "$(printf '%q ' "$@")"
    fi
}

sql_escape_literal() {
    local input="${1-}"
    printf '%s' "${input//\'/''}"
}

generate_random_alnum() {
    local length="$1"
    local result=""

    if command -v python3 >/dev/null 2>&1; then
        result=$(python3 - "$length" <<'PY'
import secrets
import string
import sys

length = int(sys.argv[1])
alphabet = string.ascii_letters + string.digits
print(''.join(secrets.choice(alphabet) for _ in range(length)), end='')
PY
        ) || result=""
    fi

    if [ "${#result}" -ne "$length" ]; then
        require_cmd tr
        require_cmd head
        while [ "${#result}" -lt "$length" ]; do
            local needed=$((length - ${#result}))
            local chunk
            chunk=$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom 2>/dev/null | head -c "$needed" || true)
            result+="$chunk"
        done
        result=${result:0:$length}
    fi

    printf '%s' "$result"
}

curl_download() {
    require_cmd curl
    local url="$1"
    local dest="$2"
    if [ -f "$dest" ]; then
        info "Using cached $(basename "$dest")"
        return
    fi

    info "Downloading $(basename "$dest")..."
    local tmp
    tmp="${dest}.partial"
    rm -f "$tmp"
    if ! curl -fL --retry 3 --retry-delay 2 "$url" -o "$tmp"; then
        rm -f "$tmp"
        warn "Download failed for $url"
        return 1
    fi
    mv "$tmp" "$dest"
}

resolve_latest_release_tag() {
    local repo="$1"
    local prefix="$2"
    local fallback="$3"
    require_cmd python3
    python3 - "$repo" "$prefix" "$fallback" <<'PY'
import json
import sys
import urllib.request

repo, prefix, fallback = sys.argv[1:4]
url = f"https://api.github.com/repos/{repo}/tags?per_page=100"

try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        tags = json.load(resp)
    for entry in tags:
        name = entry.get("name", "")
        if prefix:
            if name.startswith(prefix):
                print(name)
                break
        else:
            print(name)
            break
    else:
        if fallback:
            print(fallback)
except Exception:
    if fallback:
        print(fallback)
PY
}

build_minio_from_source() {
    local dest="$1"
    local version="${2:-}"
    require_cmd git
    require_cmd go

    local tag="$version"
    if [ -z "$tag" ] || [ "$tag" = "latest" ]; then
        tag=$(resolve_latest_release_tag "minio/minio" "RELEASE." "RELEASE.2025-04-22T22-12-26Z")
    fi
    if [ -z "$tag" ] || [ "$tag" = "null" ]; then
        tag="RELEASE.2025-04-22T22-12-26Z"
    fi

    info "Building MinIO from source (tag $tag)"
    local tmp
    tmp=$(mktemp -d "$DOWNLOAD_CACHE/minio-src.XXXXXX")
    mkdir -p "$tmp"
    if ! git clone --depth 1 --branch "$tag" https://github.com/minio/minio.git "$tmp/minio" >/dev/null 2>&1; then
        rm -rf "$tmp"
        return 1
    fi

    mkdir -p "$(dirname "$dest")"
    local build_target="$dest.build"
    if ! (cd "$tmp/minio" && GO111MODULE=on CGO_ENABLED=0 go build -o "$build_target" .); then
        rm -rf "$tmp"
        rm -f "$build_target"
        return 1
    fi

    mv "$build_target" "$dest"
    rm -rf "$tmp"
    return 0
}

build_mc_from_source() {
    local dest="$1"
    local version="${2:-}"
    require_cmd git
    require_cmd go

    local tag="$version"
    if [ -z "$tag" ] || [ "$tag" = "latest" ]; then
        tag=$(resolve_latest_release_tag "minio/mc" "RELEASE." "RELEASE.2025-04-16T18-13-26Z")
    fi
    if [ -z "$tag" ] || [ "$tag" = "null" ]; then
        tag="RELEASE.2025-04-16T18-13-26Z"
    fi

    info "Building MinIO Client from source (tag $tag)"
    local tmp
    tmp=$(mktemp -d "$DOWNLOAD_CACHE/mc-src.XXXXXX")
    mkdir -p "$tmp"
    if ! git clone --depth 1 --branch "$tag" https://github.com/minio/mc.git "$tmp/mc" >/dev/null 2>&1; then
        rm -rf "$tmp"
        return 1
    fi

    mkdir -p "$(dirname "$dest")"
    local build_target="$dest.build"
    if ! (cd "$tmp/mc" && GO111MODULE=on CGO_ENABLED=0 go build -o "$build_target" .); then
        rm -rf "$tmp"
        rm -f "$build_target"
        return 1
    fi

    mv "$build_target" "$dest"
    rm -rf "$tmp"
    return 0
}

extract_tarball() {
    require_cmd tar
    local archive="$1"
    local target_dir="$2"
    local strip_components="${3:-1}"
    if [ ! -d "$target_dir" ] || [ -z "$(ls -A "$target_dir" 2>/dev/null)" ]; then
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
# AUTO-GENERATED BY scripts/setup_local_services.sh
set -euo pipefail
SCRIPT_HEADER
    if [ $# -gt 0 ]; then
        printf '%s\n' "$body" >> "$path"
    else
        cat >> "$path"
    fi
    chmod +x "$path"
}

is_generated_file() {
    local file="$1"
    [[ -f "$file" ]] && grep -q "AUTO-GENERATED BY scripts/setup_local_services.sh" "$file"
}

remove_generated_file() {
    local file="$1"
    if is_generated_file "$file"; then
        info "Removing generated helper $file"
        rm -f "$file"
    fi
}

ensure_workspace_directories() {
    mkdir -p "$LOCAL_STACK_DIR" "$DOWNLOAD_CACHE" "$LOG_DIR"
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
    local backend_host_local="127.0.0.1"
    local backend_schema_dir="$PROJECT_ROOT/backend/data/edi_schemas"
    local keycloak_internal_host="localhost"
    local keycloak_internal_port="8180"
    local sftpgo_internal_port="8280"

    local default_nifi_key="12345678901234567890123456789012"
    local existing_nifi_key=""
    if [ -f "$LOCAL_ENV_FILE" ]; then
        existing_nifi_key=$(grep -E '^NIFI_SENSITIVE_PROPS_KEY=' "$LOCAL_ENV_FILE" | tail -n1 | cut -d'=' -f2- || true)
    fi
    local nifi_sensitive_key="${existing_nifi_key:-${NIFI_SENSITIVE_PROPS_KEY:-$default_nifi_key}}"
    if [ "${#nifi_sensitive_key}" -ne 32 ]; then
        warn "NIFI_SENSITIVE_PROPS_KEY must be 32 characters; generating a random local value."
        nifi_sensitive_key=$(generate_random_alnum 32)
        if [ "${#nifi_sensitive_key}" -ne 32 ]; then
            error "Failed to generate a 32-character NIFI_SENSITIVE_PROPS_KEY"
        fi
    fi

    local nifi_admin_user="${NIFI_ADMIN_USER:-admin}"
    local existing_nifi_password=""
    if [ -f "$LOCAL_ENV_FILE" ]; then
        existing_nifi_password=$(grep -E '^NIFI_ADMIN_PASSWORD=' "$LOCAL_ENV_FILE" | tail -n1 | cut -d'=' -f2- || true)
        if [ -z "$existing_nifi_password" ]; then
            existing_nifi_password=$(grep -E '^NIFI_PASSWORD=' "$LOCAL_ENV_FILE" | tail -n1 | cut -d'=' -f2- || true)
        fi
    fi

    local nifi_password_source
    local nifi_password_label="NiFi password"
    if [ -n "${NIFI_PASSWORD:-}" ]; then
        nifi_password_source="$NIFI_PASSWORD"
        nifi_password_label="NIFI_PASSWORD"
    elif [ -n "${NIFI_ADMIN_PASSWORD:-}" ]; then
        nifi_password_source="$NIFI_ADMIN_PASSWORD"
        nifi_password_label="NIFI_ADMIN_PASSWORD"
    elif [ -n "$existing_nifi_password" ]; then
        nifi_password_source="$existing_nifi_password"
        nifi_password_label="existing NIFI password"
    else
        nifi_password_source="admin12345678"
    fi

    if [ "${#nifi_password_source}" -lt 12 ]; then
        warn "$nifi_password_label must be at least 12 characters; generating a random local value."
        nifi_password_source=$(generate_random_alnum 16)
        if [ "${#nifi_password_source}" -lt 12 ]; then
            error "Failed to generate a NiFi password of at least 12 characters"
        fi
    fi

    local nifi_admin_password="$nifi_password_source"
    local nifi_password="$nifi_password_source"
    local nifi_username="${NIFI_USERNAME:-$nifi_admin_user}"

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
BACKEND_HOST=$backend_host_local
EDI_SCHEMA_DIRECTORY=$backend_schema_dir

STORAGE_ACCESS_KEY=${STORAGE_ACCESS_KEY:-minioadmin}
STORAGE_SECRET_KEY=${STORAGE_SECRET_KEY:-minioadmin}
STORAGE_ENDPOINT_URL=http://127.0.0.1:9000
STORAGE_BUCKET=${STORAGE_BUCKET:-edi-lens}
STORAGE_REGION=${STORAGE_REGION:-us-east-1}

VITE_API_URL=http://localhost:3001/api/v1
VITE_KEYCLOAK_URL=http://localhost:8081
VITE_KEYCLOAK_REALM=${KEYCLOAK_REALM:-edi-lens}
VITE_KEYCLOAK_CLIENT_ID=${KEYCLOAK_UI_CLIENT_ID:-edi-lens-ui}

NIFI_URL=https://localhost:8443
NIFI_REGISTRY_URL=http://localhost:18080
NIFI_ADMIN_USER=$nifi_admin_user
NIFI_ADMIN_PASSWORD=$nifi_admin_password
NIFI_SENSITIVE_PROPS_KEY=$nifi_sensitive_key
NIFI_JVM_HEAP_INIT=${NIFI_JVM_HEAP_INIT:-1g}
NIFI_JVM_HEAP_MAX=${NIFI_JVM_HEAP_MAX:-2g}
NIFI_WEB_PROXY_HOST=localhost:8443
NIFI_USERNAME=$nifi_username
NIFI_PASSWORD=$nifi_password

# Monitoring endpoints via Caddy
GRAFANA_PUBLIC_URL=http://localhost:3030
PROMETHEUS_PUBLIC_URL=http://localhost:9090
LOKI_PUBLIC_URL=http://localhost:3100
EOF
}

stop_postgres_cluster() {
    local pg_dir="$LOCAL_STACK_DIR/postgres"
    local data_dir="$pg_dir/data"
    if [ ! -d "$data_dir" ]; then
        return
    fi

    ensure_postgres_binaries_in_path
    local pg_ctl_bin="$POSTGRES_BIN_DIR/pg_ctl"
    if [ ! -x "$pg_ctl_bin" ]; then
        pg_ctl_bin=$(command -v pg_ctl 2>/dev/null || true)
    fi
    if [ -z "$pg_ctl_bin" ]; then
        warn "pg_ctl not found; skipping PostgreSQL shutdown"
        return
    fi

    local runtime_user="${POSTGRES_RUNTIME_USER:-}"
    if [ -z "$runtime_user" ]; then
        runtime_user=$(stat -c '%U' "$data_dir" 2>/dev/null || id -un 2>/dev/null || whoami 2>/dev/null || printf 'unknown')
    fi

    if run_as_user "$runtime_user" "$pg_ctl_bin" status -D "$data_dir" >/dev/null 2>&1; then
        info "Stopping PostgreSQL cluster before removal"
        if ! run_as_user "$runtime_user" "$pg_ctl_bin" -D "$data_dir" stop -m fast >/dev/null 2>&1; then
            warn "Failed to stop PostgreSQL cleanly; you may need to stop it manually"
        fi
    fi
}

uninstall_local_services() {
    info "Uninstalling local services from $LOCAL_STACK_DIR"

    stop_postgres_cluster

    if [ -d "$LOCAL_STACK_DIR" ]; then
        if [[ -z "$LOCAL_STACK_DIR" || "$LOCAL_STACK_DIR" = "/" ]]; then
            error "Refusing to remove unsafe workspace path: $LOCAL_STACK_DIR"
        fi
        rm -rf "$LOCAL_STACK_DIR"
    fi

    remove_generated_file "$PROJECT_ROOT/backend/start-local.sh"
    remove_generated_file "$PROJECT_ROOT/frontend/start-local.sh"

    success "Local services artifacts removed."
}

# --- PostgreSQL ---------------------------------------------------------------
setup_postgres() {
    info "Configuring local PostgreSQL cluster"
    ensure_postgres_binaries_in_path
    require_cmd initdb
    require_cmd pg_ctl
    require_cmd psql

    local pg_dir="$LOCAL_STACK_DIR/postgres"
    local data_dir="$pg_dir/data"
    local log_file="$LOG_DIR/postgres.log"
    local port="${POSTGRES_PORT:-5432}"
    local current_user
    current_user=$(id -un 2>/dev/null || whoami 2>/dev/null || printf 'unknown')
    local pg_runtime_user="${POSTGRES_RUNTIME_USER:-$current_user}"
    local initdb_bin="$POSTGRES_BIN_DIR/initdb"
    local pg_ctl_bin="$POSTGRES_BIN_DIR/pg_ctl"

    if [ "$pg_runtime_user" = "root" ]; then
        if id postgres >/dev/null 2>&1; then
            info "Running as root; delegating PostgreSQL processes to 'postgres' user"
            pg_runtime_user="postgres"
        else
            error "PostgreSQL cannot be initialized as root. Set POSTGRES_RUNTIME_USER to a non-root user."
        fi
    fi

    local pg_runtime_group
    pg_runtime_group=$(id -gn "$pg_runtime_user" 2>/dev/null || printf '%s' "$pg_runtime_user")

    if [ ! -x "$initdb_bin" ]; then
        initdb_bin=$(command -v initdb 2>/dev/null || true)
    fi
    if [ ! -x "$pg_ctl_bin" ]; then
        pg_ctl_bin=$(command -v pg_ctl 2>/dev/null || true)
    fi

    if [ ! -x "$initdb_bin" ] || [ ! -x "$pg_ctl_bin" ]; then
        error "PostgreSQL binaries not found in PATH. Ensure the client tools are installed."
    fi

    mkdir -p "$pg_dir"

    if [ "$current_user" != "$pg_runtime_user" ]; then
        chown -R "$pg_runtime_user:$pg_runtime_group" "$pg_dir"
    fi

    if [ ! -d "$data_dir/base" ]; then
        info "Initializing PostgreSQL data directory"
        local pwfile
        pwfile=$(mktemp)
        chmod 600 "$pwfile"
        printf '%s' "${POSTGRES_PASSWORD:-password}" > "$pwfile"
        if [ "$current_user" != "$pg_runtime_user" ]; then
            chown "$pg_runtime_user:$pg_runtime_group" "$pwfile"
        fi
        run_as_user "$pg_runtime_user" "$initdb_bin" -D "$data_dir" -U "${POSTGRES_USER:-edi_user}" -A scram-sha-256 --pwfile "$pwfile"
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

    if ! run_as_user "$pg_runtime_user" "$pg_ctl_bin" status -D "$data_dir" >/dev/null 2>&1; then
        info "Starting PostgreSQL"
        touch "$log_file"
        if [ "$current_user" != "$pg_runtime_user" ]; then
            chown "$pg_runtime_user:$pg_runtime_group" "$log_file"
        fi
        run_as_user "$pg_runtime_user" "$pg_ctl_bin" -D "$data_dir" -l "$log_file" start
        sleep 3
    else
        info "PostgreSQL already running"
    fi

    local base_conn="postgresql://${POSTGRES_USER:-edi_user}:${POSTGRES_PASSWORD:-password}@127.0.0.1:$port"
    local psql_super=(psql -v ON_ERROR_STOP=1 "$base_conn/postgres")

    info "Ensuring core extensions and databases exist"

    local target_db="${POSTGRES_DB:-edi_lens}"
    local target_db_exists=0
    if [ "$target_db" = "postgres" ]; then
        target_db_exists=1
    else
        local target_db_check
        target_db_check=$("${psql_super[@]}" -tAc "SELECT 1 FROM pg_database WHERE datname='${target_db}'" | tr -d '[:space:]' || true)
        if [ "$target_db_check" = "1" ]; then
            target_db_exists=1
        else
            "${psql_super[@]}" -c "CREATE DATABASE \"${target_db}\" OWNER \"${POSTGRES_USER:-edi_user}\""
            target_db_exists=1
        fi
    fi

    if [ $target_db_exists -eq 1 ]; then
        local psql_app=(psql -v ON_ERROR_STOP=1 "$base_conn/${target_db}")
        local extension_available
        extension_available=$("${psql_super[@]}" -tAc "SELECT 1 FROM pg_available_extensions WHERE name='vector'" | tr -d '[:space:]' || true)
        if [ "$extension_available" = "1" ]; then
            "${psql_app[@]}" -c "CREATE EXTENSION IF NOT EXISTS vector"
        else
            warn "pgvector extension not available – skipping"
        fi

        extension_available=$("${psql_super[@]}" -tAc "SELECT 1 FROM pg_available_extensions WHERE name='age'" | tr -d '[:space:]' || true)
        if [ "$extension_available" = "1" ]; then
            "${psql_app[@]}" -c "CREATE EXTENSION IF NOT EXISTS age"
        else
            warn "Apache AGE extension not available – skipping"
        fi

        if [ "$target_db" != "postgres" ]; then
            "${psql_super[@]}" -c "ALTER DATABASE \"${target_db}\" SET search_path = ag_catalog, \"\$user\", public"
        fi
    fi

    ensure_db_and_role() {
        local db_name="$1"
        local role_name="$2"
        local role_password="$3"
        local db_check
        db_check=$("${psql_super[@]}" -tAc "SELECT 1 FROM pg_database WHERE datname='${db_name}'" | tr -d '[:space:]' || true)
        if [ "$db_check" != "1" ]; then
            "${psql_super[@]}" -c "CREATE DATABASE \"${db_name}\""
        fi

        local role_check
        role_check=$("${psql_super[@]}" -tAc "SELECT 1 FROM pg_roles WHERE rolname='${role_name}'" | tr -d '[:space:]' || true)
        if [ "$role_check" != "1" ]; then
            local escaped
            escaped=$(sql_escape_literal "$role_password")
            "${psql_super[@]}" -c "CREATE USER \"${role_name}\" WITH PASSWORD '${escaped}'"
        fi

        local psql_db=(psql -v ON_ERROR_STOP=1 "$base_conn/${db_name}")
        "${psql_db[@]}" -c "GRANT ALL PRIVILEGES ON DATABASE \"${db_name}\" TO \"${role_name}\""
        "${psql_db[@]}" -c "GRANT USAGE, CREATE ON SCHEMA public TO \"${role_name}\""
    }

    ensure_db_and_role "${POSTGRES_KC_DB:-keycloak}" "${POSTGRES_KC_USER:-keycloak_user}" "${POSTGRES_KC_PASSWORD:-password}"
    ensure_db_and_role "${POSTGRES_SFTPGO_DB:-sftpgo}" "${POSTGRES_SFTPGO_USER:-sftpgo_user}" "${POSTGRES_SFTPGO_PASSWORD:-password}"
    ensure_db_and_role "${POSTGRES_NIFI_REGISTRY_DB:-nifi_registry}" "${POSTGRES_NIFI_REGISTRY_USER:-nifi_registry}" "${POSTGRES_NIFI_REGISTRY_PASSWORD:-password}"

    unset -f ensure_db_and_role

    success "PostgreSQL configured at 127.0.0.1:$port"
}

setup_minio() {
    info "Preparing MinIO binary and data directory"
    local minio_dir="$LOCAL_STACK_DIR/minio"
    local bin_dir="$LOCAL_STACK_DIR/bin"
    local minio_bin="$bin_dir/minio"
    local mc_bin="$bin_dir/mc"
    mkdir -p "$minio_dir/data" "$bin_dir"

    local minio_url
    local minio_cache
    if [ -n "${MINIO_VERSION:-}" ] && [ "${MINIO_VERSION}" != "latest" ]; then
        minio_url="https://github.com/minio/minio/releases/download/${MINIO_VERSION}/minio"
        minio_cache="$DOWNLOAD_CACHE/minio-${MINIO_VERSION}"
    else
        minio_url="https://github.com/minio/minio/releases/latest/download/minio"
        minio_cache="$DOWNLOAD_CACHE/minio-latest"
    fi
    if ! curl_download "$minio_url" "$minio_cache"; then
        warn "Failed to download MinIO binary directly; attempting to build from source"
        if ! build_minio_from_source "$minio_cache" "${MINIO_VERSION:-}"; then
            error "Unable to obtain MinIO binary"
        fi
    fi
    local minio_tmp="$minio_bin.new"
    cp "$minio_cache" "$minio_tmp"
    chmod +x "$minio_tmp"
    mv -f "$minio_tmp" "$minio_bin"

    local mc_url
    local mc_cache
    if [ -n "${MINIO_CLIENT_VERSION:-}" ] && [ "${MINIO_CLIENT_VERSION}" != "latest" ]; then
        mc_url="https://github.com/minio/mc/releases/download/${MINIO_CLIENT_VERSION}/mc"
        mc_cache="$DOWNLOAD_CACHE/mc-${MINIO_CLIENT_VERSION}"
    else
        mc_url="https://github.com/minio/mc/releases/latest/download/mc"
        mc_cache="$DOWNLOAD_CACHE/mc-latest"
    fi
    if ! curl_download "$mc_url" "$mc_cache"; then
        warn "Failed to download MinIO Client; attempting to build from source"
        if ! build_mc_from_source "$mc_cache" "${MINIO_CLIENT_VERSION:-}"; then
            error "Unable to obtain MinIO Client binary"
        fi
    fi
    local mc_tmp="$mc_bin.new"
    cp "$mc_cache" "$mc_tmp"
    chmod +x "$mc_tmp"
    mv -f "$mc_tmp" "$mc_bin"

    write_start_script "$minio_dir/start.sh" <<SCRIPT
MINIO_ROOT="$minio_dir"
BIN_DIR="$bin_dir"
DATA_DIR="$minio_dir/data"
set -a
source "$LOCAL_ENV_FILE"
set +a
export MINIO_ROOT_USER="\$STORAGE_ACCESS_KEY"
export MINIO_ROOT_PASSWORD="\$STORAGE_SECRET_KEY"
exec "$minio_bin" server "\$DATA_DIR" --console-address ":9001" --address ":9000"
SCRIPT

    write_start_script "$minio_dir/create_bucket.sh" <<SCRIPT
BIN_DIR="$bin_dir"
set -a
source "$LOCAL_ENV_FILE"
set +a
MINIO_ENDPOINT=\${STORAGE_ENDPOINT_URL:-http://127.0.0.1:9000}
BUCKET=\${STORAGE_BUCKET:-edi-lens}
ACCESS=\${STORAGE_ACCESS_KEY:-minioadmin}
SECRET=\${STORAGE_SECRET_KEY:-minioadmin}
"$mc_bin" alias set local-minio "\$MINIO_ENDPOINT" "\$ACCESS" "\$SECRET"
"$mc_bin" mb --ignore-existing local-minio/"\$BUCKET"
"$mc_bin" anonymous set public local-minio/"\$BUCKET" || true
SCRIPT

    success "MinIO setup complete (start via $minio_dir/start.sh)"
}

setup_keycloak() {
    info "Installing Keycloak distribution"
    local version="${KEYCLOAK_VERSION:-25.0.2}"
    local archive="$DOWNLOAD_CACHE/keycloak-$version.tar.gz"
    local install_dir="$LOCAL_STACK_DIR/keycloak"
    local kc_home="$install_dir"

    mkdir -p "$install_dir"
    if ! curl_download "https://github.com/keycloak/keycloak/releases/download/$version/keycloak-$version.tar.gz" "$archive"; then
        error "Failed to download Keycloak $version archive"
    fi
    extract_tarball "$archive" "$install_dir" 1

    write_start_script "$install_dir/start.sh" <<SCRIPT
ROOT=\$(cd "\$(dirname "$0")" && pwd)
KC_HOME="$kc_home"
set -a
source "$LOCAL_ENV_FILE"
set +a
export KEYCLOAK_ADMIN
export KEYCLOAK_ADMIN_PASSWORD
exec "\$KC_HOME/bin/kc.sh" start-dev \
  --http-port=8180 \
  --hostname="\$REMOTE_HOST" \
  --db=postgres \
  --db-url-host=127.0.0.1 \
  --db-url-port=\${POSTGRES_PORT:-5432} \
  --db-username="\$POSTGRES_KC_USER" \
  --db-password="\$POSTGRES_KC_PASSWORD" \
  --db-url-database="\$POSTGRES_KC_DB" \
  --http-management-port=\${KEYCLOAK_MANAGEMENT_PORT:-9002} \
  --proxy=edge \
  --hostname-strict=false
SCRIPT

    success "Keycloak available via start script at $install_dir/start.sh"
}

setup_sftpgo() {
    info "Installing SFTPGo"
    local version="${SFTPGO_VERSION:-2.6.6}"
    local archive="$DOWNLOAD_CACHE/sftpgo_v${version}_linux_x86_64.tar.xz"
    local install_dir="$LOCAL_STACK_DIR/sftpgo"
    local bin_dir="$install_dir"

    mkdir -p "$install_dir"
    local download_url="https://github.com/drakkan/sftpgo/releases/download/v${version}/sftpgo_v${version}_linux_x86_64.tar.xz"
    if ! curl_download "$download_url" "$archive"; then
        error "Failed to download SFTPGo $version archive"
    fi
    if [ ! -x "$bin_dir/sftpgo" ]; then
        info "Extracting SFTPGo archive"
        tar -xf "$archive" -C "$install_dir"
    fi

    mkdir -p "$install_dir/data" "$install_dir/state"

    if [ ! -f "$install_dir/state/sftpgo.json" ]; then
        cp "$install_dir/sftpgo.json" "$install_dir/state/sftpgo.json"
    fi
    if [ ! -d "$install_dir/state/templates" ]; then
        cp -R "$install_dir/templates" "$install_dir/state/"
    fi
    if [ ! -d "$install_dir/state/static" ]; then
        cp -R "$install_dir/static" "$install_dir/state/"
    fi

    write_start_script "$install_dir/start.sh" <<SCRIPT
BASE=\$(cd "\$(dirname "\$0")" && pwd)
BIN="$bin_dir/sftpgo"
set -a
source "$LOCAL_ENV_FILE"
set +a
export SFTPGO_HOME_DIR="\$BASE/data"
export SFTPGO_CONFIG_DIR="\$BASE/state"
export SFTPGO_DEFAULT_ADMIN_USERNAME="\$SFTPGO_ADMIN_USER"
export SFTPGO_DEFAULT_ADMIN_PASSWORD="\$SFTPGO_ADMIN_PASSWORD"
export SFTPGO_LOG__LEVEL=info
export SFTPGO_DATA_PROVIDER__DRIVER=postgresql
export SFTPGO_DATA_PROVIDER__NAME="\$POSTGRES_SFTPGO_DB"
export SFTPGO_DATA_PROVIDER__HOST=127.0.0.1
export SFTPGO_DATA_PROVIDER__PORT=\${POSTGRES_PORT:-5432}
export SFTPGO_DATA_PROVIDER__USERNAME="\$POSTGRES_SFTPGO_USER"
export SFTPGO_DATA_PROVIDER__PASSWORD="\$POSTGRES_SFTPGO_PASSWORD"
export SFTPGO_DATA_PROVIDER__SSLMODE=0
export SFTPGO_HTTPD__BINDINGS__0__ADDRESS=0.0.0.0
export SFTPGO_HTTPD__BINDINGS__0__PORT=8280
export SFTPGO_HTTPD__BINDINGS__0__OIDC__CLIENT_ID="\$KEYCLOAK_SFTPGO_CLIENT_ID"
export SFTPGO_HTTPD__BINDINGS__0__OIDC__CLIENT_SECRET="\$KEYCLOAK_SFTPGO_CLIENT_SECRET"
export SFTPGO_HTTPD__BINDINGS__0__OIDC__CONFIG_URL="\$KEYCLOAK_URL/realms/\$KEYCLOAK_REALM"
export SFTPGO_HTTPD__BINDINGS__0__OIDC__REDIRECT_BASE_URL=http://localhost:8082
export SFTPGO_HTTPD__BINDINGS__0__OIDC__INSECURE_SKIP_SIGNATURE_CHECK=false
export SFTPGO_HTTPD__BINDINGS__0__OIDC__SCOPES=openid,profile,email,groups
export SFTPGO_HTTPD__BINDINGS__0__OIDC__USERNAME_FIELD=preferred_username
export SFTPGO_HTTPD__BINDINGS__0__OIDC__ROLE_FIELD=groups
export SFTPGO_HTTPD__BINDINGS__0__OIDC__AUTO_CREATE_USER=true
exec "\$BIN" serve
SCRIPT

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
    write_start_script "$start_path" <<SCRIPT
PROJECT_ROOT=\$(cd "\$(dirname "\$0")/.." && pwd)
VENV="$venv_dir"
set -a
source "$LOCAL_ENV_FILE"
set +a
source "\$VENV/bin/activate"
cd "\$PROJECT_ROOT/backend"
exec poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir src --reload-dir alembic
SCRIPT

    success "Backend virtualenv ready (start via backend/start-local.sh)"
}

setup_frontend() {
    info "Installing frontend dependencies"
    require_cmd npm

    (cd "\$PROJECT_ROOT/frontend" && npm install)

    local start_path="$PROJECT_ROOT/frontend/start-local.sh"
    write_start_script "$start_path" <<SCRIPT
PROJECT_ROOT=\$(cd "\$(dirname "\$0")/.." && pwd)
set -a
source "$LOCAL_ENV_FILE"
set +a
cd "$PROJECT_ROOT/frontend"
exec npm run dev -- --host 0.0.0.0 --port 3000
SCRIPT

    success "Frontend ready (start via frontend/start-local.sh)"
}

setup_caddy() {
    info "Preparing Caddy reverse proxy"
    local bin_dir="$LOCAL_STACK_DIR/bin"
    local caddy_bin="$bin_dir/caddy"
    local caddy_dir="$LOCAL_STACK_DIR/caddy"
    local caddyfile="$caddy_dir/Caddyfile"

    mkdir -p "$bin_dir" "$caddy_dir"
    if ! curl_download "https://github.com/caddyserver/caddy/releases/download/v2.8.4/caddy_2.8.4_linux_amd64.tar.gz" "$DOWNLOAD_CACHE/caddy_2.8.4_linux_amd64.tar.gz"; then
        error "Failed to download Caddy binary"
    fi
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

    write_start_script "$caddy_dir/start.sh" <<SCRIPT
BIN_DIR="$bin_dir"
CADDYFILE="$caddyfile"
exec "$caddy_bin" run --config "$caddyfile"
SCRIPT

    success "Caddy configuration ready (start via $caddy_dir/start.sh)"
}

setup_nifi() {
    info "Installing Apache NiFi"
    local version="2.5.0"
    local archive="$DOWNLOAD_CACHE/nifi-$version-bin.zip"
    local install_dir="$LOCAL_STACK_DIR/nifi"
    local nifi_home="$install_dir/nifi-$version"

    mkdir -p "$install_dir"
    if ! curl_download "https://downloads.apache.org/nifi/$version/nifi-$version-bin.zip" "$archive"; then
        error "Failed to download NiFi $version archive"
    fi
    require_cmd unzip
    if [ -d "$nifi_home" ] && [ ! -f "$nifi_home/conf/nifi.properties" ]; then
        warn "Existing NiFi directory is missing configuration; re-extracting archive"
        rm -rf "$nifi_home"
    fi
    if [ ! -d "$nifi_home" ]; then
        info "Extracting NiFi archive"
        unzip -q "$archive" -d "$install_dir"
    else
        info "NiFi archive already extracted"
    fi

    require_cmd rsync

    local py_ext_dir="$nifi_home/python_extensions/edi-processors"
    mkdir -p "$py_ext_dir"
    for file in "$PROJECT_ROOT"/nifi-edi-processors/*.py; do
        cp "$file" "$py_ext_dir/"
    done
    rsync -a "$PROJECT_ROOT/nifi-edi-processors/schemas" "$py_ext_dir"/
    mkdir -p "$nifi_home/conf"
    cp "$PROJECT_ROOT/docker/nifi-processors/login-identity-providers.xml" "$nifi_home/conf/login-identity-providers.xml"

    local nifi_props="$nifi_home/conf/nifi.properties"
    python3 - "$nifi_props" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()

def set_prop(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    replacement = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(replacement, content)
    return content + f"\n{replacement}\n"

text = set_prop(text, "nifi.web.http.host", "")
text = set_prop(text, "nifi.web.http.port", "")
text = set_prop(text, "nifi.web.https.host", "0.0.0.0")
text = set_prop(text, "nifi.web.https.port", "8443")
text = set_prop(text, "nifi.web.proxy.host", "localhost:8443")
text = set_prop(text, "nifi.remote.input.secure", "false")
text = set_prop(text, "nifi.remote.input.http.enabled", "false")

path.write_text(text)
PY

    write_start_script "$install_dir/start.sh" <<SCRIPT
NIFI_HOME="$nifi_home"
set -a
source "$LOCAL_ENV_FILE"
set +a
if [ \${#NIFI_SENSITIVE_PROPS_KEY} -ne 32 ]; then
    echo "NIFI_SENSITIVE_PROPS_KEY must be 32 characters. Update local-services/.env.local."
    exit 1
fi
export NIFI_WEB_HTTPS_HOST=0.0.0.0
export NIFI_WEB_HTTPS_PORT=8443
export NIFI_WEB_HTTP_HOST=
export NIFI_WEB_HTTP_PORT=
export NIFI_WEB_PROXY_HOST="\$NIFI_WEB_PROXY_HOST"
export NIFI_WEB_PROXY_CONTEXT_PATH=
export NIFI_SECURITY_USER_LOGIN_IDENTITY_PROVIDER=single-user-provider
export NIFI_SECURITY_USER_AUTHORIZER=single-user-authorizer
export NIFI_JVM_HEAP_INIT="\$NIFI_JVM_HEAP_INIT"
export NIFI_JVM_HEAP_MAX="\$NIFI_JVM_HEAP_MAX"
export NIFI_SENSITIVE_PROPS_KEY
export NIFI_USERNAME
export NIFI_PASSWORD
PYTHONPATH_BASE="\$NIFI_HOME/python_extensions:\$NIFI_HOME/python_extensions/edi-processors"
if [ -n "\${PYTHONPATH:-}" ]; then
    export PYTHONPATH="\$PYTHONPATH_BASE:\${PYTHONPATH}"
else
    export PYTHONPATH="\$PYTHONPATH_BASE"
fi
"\$NIFI_HOME/bin/nifi.sh" set-single-user-credentials "\$NIFI_USERNAME" "\$NIFI_PASSWORD"
exec "\$NIFI_HOME/bin/nifi.sh" run
SCRIPT

    success "NiFi ready (start via $install_dir/start.sh)"
}

setup_nifi_registry() {
    info "Installing Apache NiFi Registry"
    local version="2.0.0"
    local archive="$DOWNLOAD_CACHE/nifi-registry-$version-bin.zip"
    local install_dir="$LOCAL_STACK_DIR/nifi-registry"
    local registry_home="$install_dir/nifi-registry-$version"

    mkdir -p "$install_dir"
    if ! curl_download "https://downloads.apache.org/nifi/$version/nifi-registry-$version-bin.zip" "$archive"; then
        error "Failed to download NiFi Registry $version archive"
    fi
    require_cmd unzip
    if [ ! -d "$registry_home" ]; then
        info "Extracting NiFi Registry archive"
        unzip -q "$archive" -d "$install_dir"
    else
        info "NiFi Registry archive already extracted"
    fi

    cp "$PROJECT_ROOT/docker/nifi-registry/postgresql-42.7.4.jar" "$registry_home/lib/"

    write_start_script "$install_dir/start.sh" <<SCRIPT
REGISTRY_HOME="$registry_home"
set -a
source "$LOCAL_ENV_FILE"
set +a
export NIFI_REGISTRY_DB_URL="jdbc:postgresql://127.0.0.1:\${POSTGRES_PORT:-5432}/\$POSTGRES_NIFI_REGISTRY_DB"
export NIFI_REGISTRY_DB_USER="\$POSTGRES_NIFI_REGISTRY_USER"
export NIFI_REGISTRY_DB_PASS="\$POSTGRES_NIFI_REGISTRY_PASSWORD"
export NIFI_REGISTRY_WEB_HTTP_HOST=0.0.0.0
export NIFI_REGISTRY_WEB_HTTP_PORT=18081
exec "\$REGISTRY_HOME/bin/nifi-registry.sh" run
SCRIPT

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

case "$ACTION" in
    uninstall)
        if [ -f "$ENV_SOURCE_FILE" ]; then
            set -a
            # shellcheck disable=SC1090
            source "$ENV_SOURCE_FILE"
            set +a
        fi
        uninstall_local_services
        exit 0
        ;;
    reinstall)
        if [ -f "$ENV_SOURCE_FILE" ]; then
            set -a
            # shellcheck disable=SC1090
            source "$ENV_SOURCE_FILE"
            set +a
        fi
        uninstall_local_services
        ACTION="install"
        ;;
esac

ensure_workspace_directories
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
