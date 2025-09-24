#!/usr/bin/env bash
# ==============================================================================
# EDI LENS - MINIMAL CODEX SERVICE SETUP
# ==============================================================================
# Standalone provisioning script that installs and configures the core
# infrastructure services required for local backend development: PostgreSQL,
# Apache NiFi and NiFi Registry. The logic is ported from the legacy Codex setup
# so it can run without sourcing scripts from the legacy directory.
# ==============================================================================

set -euo pipefail

# --- Output helpers -----------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { printf "${BLUE}[INFO]${NC} %s\n" "$1"; }
success() { printf "${GREEN}[SUCCESS]${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}[WARN]${NC} %s\n" "$1"; }
error() { printf "${RED}[ERROR]${NC} %s\n" "$1"; exit 1; }

log_process_state() {
    local name="$1"
    local pattern="$2"
    local pids

    if pids=$(pgrep -f "$pattern" 2>/dev/null); then
        info "$name appears to be running (pids: $pids)"
    else
        info "$name is not currently running"
    fi
}

require_cmd() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        error "Required command '$cmd' is not available. Please install it first."
    fi
}


curl_download() {
    local url="$1"
    local dest="$2"
    if [ -f "$dest" ]; then
        info "Using cached $(basename "$dest")"
        return
    fi
    info "Downloading $(basename "$dest")..."
    if ! curl -fL --retry 3 --retry-delay 2 -H "User-Agent: Mozilla/5.0" "$url" -o "$dest"; then
        rm -f "$dest"
        error "Failed to download $url"
    fi
}

update_property() {
    local file="$1"
    local key="$2"
    local value="$3"

    if grep -q "^$key=" "$file"; then
        sed -i "s#^$key=.*#$key=$value#" "$file"
    else
        echo "$key=$value" >> "$file"
    fi
}

wait_for_service() {
    local url="$1"
    local name="$2"
    local max_attempts="${3:-30}"
    local attempt=1

    info "Waiting for $name to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if [[ "$url" == https:* ]]; then
            curl -kfs "$url" >/dev/null 2>&1 && { success "$name is ready!"; return 0; }
        else
            curl -fs "$url" >/dev/null 2>&1 && { success "$name is ready!"; return 0; }
        fi
        printf "."
        sleep 2
        attempt=$((attempt + 1))
    done
    warn "$name failed to start after $max_attempts attempts"
    return 1
}

ensure_env_value() {
    local file="$1"
    local key="$2"
    local default_value="$3"

    if [ ! -f "$file" ]; then
        touch "$file"
    fi

    if ! grep -q "^$key=" "$file" 2>/dev/null; then
        if [ -s "$file" ] && [ "$(tail -c1 "$file" 2>/dev/null)" != $'\n' ]; then
            echo >> "$file"
        fi
        echo "$key=$default_value" >> "$file"
    fi
}

create_env_file() {
    if [ -f "$ENV_FILE" ]; then
        info "Using existing $ENV_FILE"
        ensure_env_value "$ENV_FILE" "NIFI_SENSITIVE_PROPS_KEY" "codex_nifi_secret_key_2024_pass!"
        ensure_env_value "$ENV_FILE" "NIFI_WEB_PROXY_HOST" "localhost:8443"
        ensure_env_value "$ENV_FILE" "NIFI_JVM_HEAP_INIT" "1g"
        ensure_env_value "$ENV_FILE" "NIFI_JVM_HEAP_MAX" "2g"
        ensure_env_value "$ENV_FILE" "NIFI_ADMIN_USER" "admin"
        ensure_env_value "$ENV_FILE" "NIFI_ADMIN_PASSWORD" "nifi_admin_codex_2024"
        ensure_env_value "$ENV_FILE" "NIFI_USERNAME" "admin"
        ensure_env_value "$ENV_FILE" "NIFI_PASSWORD" "nifi_admin_codex_2024"
        ensure_env_value "$ENV_FILE" "NIFI_VERSION" "2.6.0"
        ensure_env_value "$ENV_FILE" "NIFI_REGISTRY_VERSION" "2.6.0"
        ensure_env_value "$ENV_FILE" "POSTGRES_HOST" "localhost"
        ensure_env_value "$ENV_FILE" "POSTGRES_PORT" "5432"
        ensure_env_value "$ENV_FILE" "POSTGRES_USER" "edi_user"
        ensure_env_value "$ENV_FILE" "POSTGRES_PASSWORD" "codex_password_2024"
        ensure_env_value "$ENV_FILE" "POSTGRES_DB" "edi_lens"
        ensure_env_value "$ENV_FILE" "POSTGRES_NIFI_REGISTRY_USER" "nifi_registry"
        ensure_env_value "$ENV_FILE" "POSTGRES_NIFI_REGISTRY_PASSWORD" "nifi_registry_password_2024"
        ensure_env_value "$ENV_FILE" "POSTGRES_NIFI_REGISTRY_DB" "nifi_registry"
        return
    fi

    info "Creating Codex environment file: $ENV_FILE"
    cat > "$ENV_FILE" <<EOF_ENV
# ==============================================================================
# EDI LENS - CODEX ENVIRONMENT CONFIGURATION
# ==============================================================================

# --- Database Configuration ---
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=edi_user
POSTGRES_PASSWORD=codex_password_2024
POSTGRES_DB=edi_lens

POSTGRES_NIFI_REGISTRY_USER=nifi_registry
POSTGRES_NIFI_REGISTRY_PASSWORD=nifi_registry_password_2024
POSTGRES_NIFI_REGISTRY_DB=nifi_registry

# --- NiFi ---
NIFI_ADMIN_USER=admin
NIFI_ADMIN_PASSWORD=nifi_admin_codex_2024
NIFI_USERNAME=admin
NIFI_PASSWORD=nifi_admin_codex_2024
NIFI_SENSITIVE_PROPS_KEY=codex_nifi_secret_key_2024_pass!
NIFI_WEB_PROXY_HOST=localhost:8443
NIFI_JVM_HEAP_INIT=1g
NIFI_JVM_HEAP_MAX=2g
NIFI_VERSION=2.6.0
NIFI_REGISTRY_VERSION=2.6.0

# --- Service Endpoints ---
NIFI_URL=https://localhost:8443
NIFI_REGISTRY_URL=http://localhost:18080
EOF_ENV
    chmod 644 "$ENV_FILE" || true
}

setup_environment() {
    info "Preparing service directories"

    if [ "$EUID" -ne 0 ]; then
        error "This script must be run as root to manage services and packages"
    fi

    if mkdir -p "$SERVICES_DIR_DEFAULT" 2>/dev/null; then
        SERVICES_DIR="$SERVICES_DIR_DEFAULT"
    else
        warn "Falling back to repository-scoped services directory at $SERVICES_DIR_FALLBACK"
        SERVICES_DIR="$SERVICES_DIR_FALLBACK"
        mkdir -p "$SERVICES_DIR"
    fi

    ENV_FILE="$PROJECT_ROOT/.env.local"
    DOWNLOADS_DIR="$SERVICES_DIR/downloads"
    LOGS_DIR="$SERVICES_DIR/logs"
    BIN_DIR="$SERVICES_DIR/bin"

    mkdir -p "$DOWNLOADS_DIR" "$LOGS_DIR" "$BIN_DIR"

    create_env_file

    set -a
    [ -f "$ENV_FILE" ] && source "$ENV_FILE"
    set +a

    : "${NIFI_VERSION:=2.6.0}"
    : "${NIFI_REGISTRY_VERSION:=2.6.0}"
    : "${POSTGRES_DB:=edi_lens}"
    : "${POSTGRES_USER:=edi_user}"
    : "${POSTGRES_PASSWORD:=codex_password_2024}"
    : "${POSTGRES_NIFI_REGISTRY_DB:=nifi_registry}"
    : "${POSTGRES_NIFI_REGISTRY_USER:=nifi_registry}"
    : "${POSTGRES_NIFI_REGISTRY_PASSWORD:=nifi_registry_password_2024}"
    : "${POSTGRES_PORT:=5432}"

    info "Environment prepared (SERVICES_DIR=$SERVICES_DIR, ENV_FILE=$ENV_FILE)"
}

log_cached_services_state() {
    info "====================================================================="
    info "🔍 DEPENDENCY CHECK - Analyzing cached service state"
    info "====================================================================="

    if [ ! -d "$SERVICES_DIR" ]; then
        info "Services directory $SERVICES_DIR does not exist yet - fresh installation required"
        return
    fi

    local contents
    contents=$(ls -1 "$SERVICES_DIR" 2>/dev/null | paste -sd ' ' - || true)
    if [ -n "$contents" ]; then
        info "📁 Existing service directories: $contents"
        
        # Check each service directory for completeness
        for service_dir in postgresql nifi nifi-registry; do
            if [ -d "$SERVICES_DIR/$service_dir" ]; then
                local size=$(du -sh "$SERVICES_DIR/$service_dir" 2>/dev/null | cut -f1 || echo "unknown")
                info "  ✓ $service_dir directory found (size: $size)"
            else
                warn "  ✗ $service_dir directory missing - will need installation"
            fi
        done
    else
        info "📁 Services directory currently empty - fresh installation required"
    fi

    # Enhanced process state logging with dependency analysis
    info "🔄 Checking running processes:"
    check_service_dependency "PostgreSQL" "postgres.*main" "5432" "postgresql"
    check_service_dependency "NiFi" "org.apache.nifi.NiFi" "8443" "nifi" 
    check_service_dependency "NiFi Registry" "org.apache.nifi.registry.NiFiRegistry" "18080" "nifi-registry"
}

check_service_dependency() {
    local name="$1"
    local pattern="$2" 
    local port="$3"
    local service_dir="$4"
    local pids
    local can_start=false
    
    info "  Analyzing $name:"
    
    if pids=$(pgrep -f "$pattern" 2>/dev/null); then
        success "    ✓ Process running (PIDs: $pids)"
        if check_port "$port"; then
            success "    ✓ Port $port responding"
            info "    → $name is healthy - skipping installation"
            return 0
        else
            warn "    ⚠ Process running but port $port not responding"
        fi
    else
        info "    ○ Process not running"
    fi
    
    # Check if service can be started without reinstallation
    if [ -d "$SERVICES_DIR/$service_dir" ]; then
        info "    ✓ Installation directory exists"
        case "$service_dir" in
            "postgresql")
                if [ -f "/var/lib/postgresql/16/main/PG_VERSION" ]; then
                    can_start=true
                    info "    ✓ PostgreSQL data directory initialized"
                fi
                ;;
            "nifi")
                if [ -f "$SERVICES_DIR/$service_dir/nifi-$NIFI_VERSION/bin/nifi.sh" ]; then
                    can_start=true
                    info "    ✓ NiFi installation complete"
                fi
                ;;
            "nifi-registry") 
                if [ -f "$SERVICES_DIR/$service_dir/nifi-registry-$NIFI_REGISTRY_VERSION/bin/nifi-registry.sh" ]; then
                    can_start=true
                    info "    ✓ NiFi Registry installation complete"
                fi
                ;;
        esac
    else
        info "    ○ Installation directory missing"
    fi
    
    if [ "$can_start" = true ]; then
        info "    → $name can be started without reinstallation"
    else
        info "    → $name requires installation/configuration"
    fi
}

check_port() {
    local port="$1"
    if [ "$port" = "8443" ]; then
        curl -kfs "https://localhost:$port/" >/dev/null 2>&1
    else
        curl -fs "http://localhost:$port/" >/dev/null 2>&1 || nc -z localhost "$port" 2>/dev/null
    fi
}

install_minimal_system_dependencies() {
    info "Installing minimal system dependencies"

    # Check what's already installed to avoid unnecessary work
    local packages_to_install=()
    local required_packages=(
        "postgresql-16"
        "postgresql-client-16" 
        "curl"
        "unzip"
        "openjdk-21-jre-headless"
        "ca-certificates"
        "python3-minimal"
        "python3-pip"
        "netcat-openbsd"
        "sudo"
    )

    for pkg in "${required_packages[@]}"; do
        if ! dpkg -l "$pkg" 2>/dev/null | grep -q "^ii"; then
            packages_to_install+=("$pkg")
        else
            info "  ✓ $pkg already installed"
        fi
    done

    if [ ${#packages_to_install[@]} -eq 0 ]; then
        success "All required packages already installed - skipping installation"
        return 0
    fi

    info "Need to install: ${packages_to_install[*]}"
    
    # Update package lists only if we need to install something
    apt-get update -qq

    # Install only what's needed with minimal recommendations
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends "${packages_to_install[@]}"

    # Clean up to save space
    apt-get clean
    rm -rf /var/lib/apt/lists/*
    
    success "Minimal system dependencies installed (${#packages_to_install[@]} packages)"
}

setup_backend_dependencies() {
    info "====================================================================="
    info "🐍 BACKEND DEPENDENCIES SETUP"
    info "====================================================================="

    local backend_dir="$PROJECT_ROOT/backend"
    
    if [ ! -d "$backend_dir" ]; then
        warn "Backend directory not found at $backend_dir - skipping backend setup"
        return 0
    fi

    if [ ! -f "$backend_dir/pyproject.toml" ]; then
        warn "pyproject.toml not found in backend directory - skipping backend setup"
        return 0
    fi

    # Check if poetry is available
    if ! command -v poetry >/dev/null 2>&1; then
        info "Installing Poetry..."
        curl -sSL https://install.python-poetry.org | python3 -
        export PATH="$HOME/.local/bin:$PATH"
    fi

    cd "$backend_dir"
    
    # Check if dependencies are already installed
    if poetry env info --path >/dev/null 2>&1; then
        local venv_path
        venv_path=$(poetry env info --path)
        if [ -d "$venv_path" ] && poetry check >/dev/null 2>&1; then
            success "✓ Backend dependencies already installed and up to date"
            cd "$PROJECT_ROOT"
            return 0
        fi
    fi

    info "Installing backend dependencies with Poetry..."
    poetry install --with test

    success "✅ Backend dependencies installed successfully"
    cd "$PROJECT_ROOT"
}

start_backend_service() {
    info "====================================================================="
    info "🚀 BACKEND SERVICE STARTUP"
    info "====================================================================="

    local backend_dir="$PROJECT_ROOT/backend"
    
    if [ ! -d "$backend_dir" ]; then
        warn "Backend directory not found - skipping backend startup"
        return 0
    fi

    # Check if backend is already running
    if check_port "8000" 2; then
        success "✓ Backend already running on port 8000"
        return 0
    fi

    cd "$backend_dir"
    
    # Check if dependencies are installed
    if ! poetry env info --path >/dev/null 2>&1; then
        warn "Backend dependencies not installed - skipping backend startup"
        cd "$PROJECT_ROOT"
        return 1
    fi

    info "Starting backend service..."
    
    # Start backend in background
    nohup poetry run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload > "$LOGS_DIR/backend.log" 2>&1 &
    
    # Wait for backend to be ready
    if wait_for_service "http://localhost:8000/health" "Backend API" 30; then
        success "✅ Backend service started successfully"
        cd "$PROJECT_ROOT"
        return 0
    else
        warn "Backend service failed to start - check logs at $LOGS_DIR/backend.log"
        cd "$PROJECT_ROOT"
        return 1
    fi
}

setup_postgresql() {
    info "====================================================================="
    info "🐘 POSTGRESQL SETUP"
    info "====================================================================="

    # Enhanced dependency check
    if pgrep -f "postgres.*main" >/dev/null; then
        local postgres_pids
        postgres_pids=$(pgrep -f "postgres.*main" 2>/dev/null | paste -sd ' ' - || true)
        if sudo -u postgres psql -lqt | cut -d '|' -f 1 | grep -qw "$POSTGRES_DB"; then
            success "✓ PostgreSQL already running with required databases (PIDs: ${postgres_pids:-unknown})"
            info "  → Skipping PostgreSQL installation and configuration"
            return 0
        else
            info "PostgreSQL running but missing required databases - will configure"
        fi
    else
        # Check if PostgreSQL can be started without reinstallation
        if [ -f "/var/lib/postgresql/16/main/PG_VERSION" ] && command -v postgres >/dev/null 2>&1; then
            info "PostgreSQL installation detected - attempting to start existing service"
            if ! pgrep -f "postgres.*main" >/dev/null; then
                info "Starting existing PostgreSQL server"
                su - postgres -c '/usr/lib/postgresql/16/bin/pg_ctl start -D /var/lib/postgresql/16/main -l /var/log/postgresql/postgresql-16-main.log -o "-c config_file=/etc/postgresql/16/main/postgresql.conf"' >/dev/null 2>&1
                sleep 5
                if pgrep -f "postgres.*main" >/dev/null; then
                    success "✓ Successfully started existing PostgreSQL installation"
                    # Continue to database creation
                else
                    warn "Failed to start existing PostgreSQL - proceeding with fresh installation"
                fi
            fi
        else
            info "No existing PostgreSQL installation found - proceeding with fresh installation"
        fi
    fi

    if [ ! -f "/var/lib/postgresql/16/main/PG_VERSION" ]; then
        info "Initializing PostgreSQL cluster"
        chown -R postgres:postgres /var/lib/postgresql/16/main
        su - postgres -c '/usr/lib/postgresql/16/bin/initdb -D /var/lib/postgresql/16/main' >/dev/null 2>&1
    fi

    mkdir -p /var/log/postgresql
    chown postgres:postgres /var/log/postgresql

    if ! pgrep -f "postgres.*main" >/dev/null; then
        info "Starting PostgreSQL server"
        su - postgres -c '/usr/lib/postgresql/16/bin/pg_ctl start -D /var/lib/postgresql/16/main -l /var/log/postgresql/postgresql-16-main.log -o "-c config_file=/etc/postgresql/16/main/postgresql.conf"' >/dev/null 2>&1
    fi

    sleep 5

    info "Creating databases and users"
    sudo -u postgres psql -c "CREATE USER $POSTGRES_USER WITH PASSWORD '$POSTGRES_PASSWORD' CREATEDB;" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE $POSTGRES_DB OWNER $POSTGRES_USER;" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE USER $POSTGRES_NIFI_REGISTRY_USER WITH PASSWORD '$POSTGRES_NIFI_REGISTRY_PASSWORD';" 2>/dev/null || true
    sudo -u postgres psql -c "CREATE DATABASE $POSTGRES_NIFI_REGISTRY_DB OWNER $POSTGRES_NIFI_REGISTRY_USER;" 2>/dev/null || true

    success "PostgreSQL configured"
}

setup_nifi_registry() {
    info "====================================================================="
    info "📋 NIFI REGISTRY SETUP"
    info "====================================================================="

    # Enhanced dependency check
    if pgrep -f "org.apache.nifi.registry.NiFiRegistry" >/dev/null; then
        if curl -fs "http://localhost:18080/nifi-registry/" >/dev/null 2>&1; then
            local registry_pids
            registry_pids=$(pgrep -f "org.apache.nifi.registry.NiFiRegistry" 2>/dev/null | paste -sd ' ' - || true)
            success "✓ NiFi Registry already running and healthy (PIDs: ${registry_pids:-unknown})"
            info "  → Skipping NiFi Registry installation"
            return 0
        else
            warn "NiFi Registry process found but not responding - will restart"
            pkill -f "org.apache.nifi.registry.NiFiRegistry" 2>/dev/null || true
            sleep 3
        fi
    else
        # Check if NiFi Registry can be started without reinstallation
        local install_dir="$SERVICES_DIR/nifi-registry"
        if [ -f "$install_dir/nifi-registry-$NIFI_REGISTRY_VERSION/bin/nifi-registry.sh" ]; then
            info "Existing NiFi Registry installation detected - attempting to start"
            local registry_home="$install_dir/nifi-registry-$NIFI_REGISTRY_VERSION"
            cd "$registry_home"
            
            info "Starting existing NiFi Registry installation"
            NIFI_REGISTRY_DB_URL="jdbc:postgresql://localhost:$POSTGRES_PORT/$POSTGRES_NIFI_REGISTRY_DB" \
            NIFI_REGISTRY_DB_USER="$POSTGRES_NIFI_REGISTRY_USER" \
            NIFI_REGISTRY_DB_PASS="$POSTGRES_NIFI_REGISTRY_PASSWORD" \
            NIFI_REGISTRY_WEB_HTTP_HOST=0.0.0.0 \
            NIFI_REGISTRY_WEB_HTTP_PORT=18080 \
            nohup ./bin/nifi-registry.sh run > "$LOGS_DIR/nifi-registry.log" 2>&1 &
            
            if wait_for_service "http://localhost:18080/nifi-registry/" "NiFi Registry" 30; then
                success "✓ Successfully started existing NiFi Registry installation"
                return 0
            else
                warn "Failed to start existing NiFi Registry - proceeding with fresh installation"
                pkill -f "org.apache.nifi.registry.NiFiRegistry" 2>/dev/null || true
                sleep 3
            fi
        else
            info "No existing NiFi Registry installation found - proceeding with fresh installation"
        fi
    fi

    local install_dir="$SERVICES_DIR/nifi-registry"
    local archive="$DOWNLOADS_DIR/nifi-registry-$NIFI_REGISTRY_VERSION-bin.zip"

    mkdir -p "$install_dir"

    if [ -d "$install_dir/nifi-registry-$NIFI_REGISTRY_VERSION" ]; then
        info "NiFi Registry already extracted, skipping download"
    else
        curl_download "https://downloads.apache.org/nifi/$NIFI_REGISTRY_VERSION/nifi-registry-$NIFI_REGISTRY_VERSION-bin.zip" "$archive"
        info "Extracting NiFi Registry"
        unzip -q "$archive" -d "$install_dir"
    fi

    local registry_home="$install_dir/nifi-registry-$NIFI_REGISTRY_VERSION"
    local jdbc_jar="$registry_home/lib/postgresql-42.7.4.jar"

    if [ ! -f "$jdbc_jar" ]; then
        curl_download "https://jdbc.postgresql.org/download/postgresql-42.7.4.jar" "$jdbc_jar"
    fi

    info "Starting NiFi Registry"
    cd "$registry_home"
    NIFI_REGISTRY_DB_URL="jdbc:postgresql://localhost:$POSTGRES_PORT/$POSTGRES_NIFI_REGISTRY_DB" \
    NIFI_REGISTRY_DB_USER="$POSTGRES_NIFI_REGISTRY_USER" \
    NIFI_REGISTRY_DB_PASS="$POSTGRES_NIFI_REGISTRY_PASSWORD" \
    NIFI_REGISTRY_WEB_HTTP_HOST=0.0.0.0 \
    NIFI_REGISTRY_WEB_HTTP_PORT=18080 \
    nohup ./bin/nifi-registry.sh run > "$LOGS_DIR/nifi-registry.log" 2>&1 &

    wait_for_service "http://localhost:18080/nifi-registry/" "NiFi Registry" 60

    success "NiFi Registry configured and running"
}

setup_nifi() {
    info "====================================================================="
    info "🌊 APACHE NIFI SETUP"
    info "====================================================================="

    # Enhanced dependency check
    if curl -kfs "https://localhost:8443/nifi/" >/dev/null 2>&1; then
        local nifi_pids
        nifi_pids=$(pgrep -f "org.apache.nifi.NiFi" 2>/dev/null | paste -sd ' ' - || true)
        success "✓ NiFi already running and healthy (PIDs: ${nifi_pids:-unknown})"
        info "  → Skipping NiFi installation"
        return 0
    elif pgrep -f "org.apache.nifi.NiFi" >/dev/null; then
        warn "NiFi process found but not responding - will restart"
        pkill -f "org.apache.nifi.NiFi" 2>/dev/null || true
        sleep 5
    fi

    # Check if NiFi can be started without reinstallation
    local install_dir="$SERVICES_DIR/nifi"
    if [ -f "$install_dir/nifi-$NIFI_VERSION/bin/nifi.sh" ]; then
        info "Existing NiFi installation detected - attempting to start"
        local nifi_home="$install_dir/nifi-$NIFI_VERSION"
        
        if [ -f "$nifi_home/start_nifi.sh" ]; then
            info "Starting existing NiFi installation"
            su -s /bin/bash nifi -c "$nifi_home/start_nifi.sh" >> "$LOGS_DIR/nifi.log" 2>&1 &
            
            sleep 10
            if wait_for_service "https://localhost:8443/nifi/" "NiFi" 60; then
                success "✓ Successfully started existing NiFi installation"
                return 0
            else
                warn "Failed to start existing NiFi - proceeding with fresh installation"
                pkill -f "org.apache.nifi.NiFi" 2>/dev/null || true
                sleep 5
            fi
        else
            info "Existing NiFi installation incomplete - proceeding with fresh installation"
        fi
    else
        info "No existing NiFi installation found - proceeding with fresh installation"
    fi

    local install_dir="$SERVICES_DIR/nifi"
    local archive="$DOWNLOADS_DIR/nifi-$NIFI_VERSION-bin.zip"

    mkdir -p "$install_dir"

    if [ -d "$install_dir/nifi-$NIFI_VERSION" ]; then
        info "NiFi already extracted, skipping download"
    else
        curl_download "https://downloads.apache.org/nifi/$NIFI_VERSION/nifi-$NIFI_VERSION-bin.zip" "$archive"
        info "Extracting NiFi"
        unzip -q "$archive" -d "$install_dir"
    fi

    local nifi_home="$install_dir/nifi-$NIFI_VERSION"
    local conf_dir="$nifi_home/conf"
    local py_ext_dir="$nifi_home/python_extensions/edi-processors"
    local vendor_dir="$py_ext_dir/vendor"

    mkdir -p "$py_ext_dir" "$vendor_dir"

    if [ -d "$PROJECT_ROOT/nifi-edi-processors" ]; then
        info "Syncing EDI NiFi processors"
        find "$py_ext_dir" -mindepth 1 -maxdepth 1 -type f -delete
        find "$py_ext_dir" -mindepth 1 -maxdepth 1 -type d ! -path "$vendor_dir" -exec rm -rf {} +
        cp -f "$PROJECT_ROOT/nifi-edi-processors"/*.py "$py_ext_dir/" 2>/dev/null || true
        if [ -d "$PROJECT_ROOT/nifi-edi-processors/schemas" ]; then
            rm -rf "$py_ext_dir/schemas"
            cp -r "$PROJECT_ROOT/nifi-edi-processors/schemas" "$py_ext_dir/"
        fi
        touch "$py_ext_dir/__init__.py"
    fi

    if [ ! -d "$vendor_dir" ] || [ -z "$(ls -A "$vendor_dir" 2>/dev/null)" ]; then
        info "Installing Python dependencies for NiFi processors"
        python3 -m pip install --no-cache-dir --target "$vendor_dir" pydantic>=2.0.0 typing-extensions>=4.0.0
    fi

    chmod -R 755 "$py_ext_dir"

    if [ -f "$PROJECT_ROOT/docker/nifi-processors/login-identity-providers.xml" ]; then
        cp "$PROJECT_ROOT/docker/nifi-processors/login-identity-providers.xml" "$conf_dir/login-identity-providers.xml"
    fi

    local properties_file="$conf_dir/nifi.properties"
    local keystore="$conf_dir/nifi-keystore.p12"
    local truststore="$conf_dir/nifi-truststore.p12"
    local storepass="codexnifi_storepass"

    update_property "$properties_file" "nifi.web.https.host" "0.0.0.0"
    update_property "$properties_file" "nifi.web.https.port" "8443"
    update_property "$properties_file" "nifi.web.proxy.host" "${NIFI_WEB_PROXY_HOST:-localhost:8080}"
    update_property "$properties_file" "nifi.web.http.host" ""
    update_property "$properties_file" "nifi.web.http.port" ""
    update_property "$properties_file" "nifi.security.user.login.identity.provider" "single-user-provider"
    update_property "$properties_file" "nifi.security.user.authorizer" "single-user-authorizer"
    update_property "$properties_file" "nifi.security.allow.anonymous.authentication" "false"
    update_property "$properties_file" "nifi.sensitive.props.key" "$NIFI_SENSITIVE_PROPS_KEY"
    update_property "$properties_file" "nifi.python.path" "$py_ext_dir:$vendor_dir"
    update_property "$properties_file" "nifi.python.command" "/usr/bin/python3"
    update_property "$properties_file" "nifi.registry.url" "http://localhost:18080"

    if [ ! -f "$keystore" ] || [ ! -f "$truststore" ]; then
        info "Generating NiFi TLS keystore and truststore"
        local cert_file="$conf_dir/nifi-cert.cer"
        keytool -genkeypair -alias nifi -keyalg RSA -keysize 4096 -storetype PKCS12 \
            -keystore "$keystore" -storepass "$storepass" -keypass "$storepass" \
            -dname "CN=localhost, OU=EDI Lens, O=Codex, L=San Francisco, S=CA, C=US" -validity 3650 >/dev/null 2>&1
        keytool -exportcert -alias nifi -keystore "$keystore" -storepass "$storepass" -file "$cert_file" >/dev/null 2>&1
        keytool -importcert -alias nifi -file "$cert_file" -keystore "$truststore" -storetype PKCS12 -storepass "$storepass" -noprompt >/dev/null 2>&1
        rm -f "$cert_file"
        chmod 600 "$keystore" "$truststore"
    fi

    update_property "$properties_file" "nifi.security.keystore" "$keystore"
    update_property "$properties_file" "nifi.security.keystoreType" "PKCS12"
    update_property "$properties_file" "nifi.security.keystorePasswd" "$storepass"
    update_property "$properties_file" "nifi.security.keyPasswd" "$storepass"
    update_property "$properties_file" "nifi.security.truststore" "$truststore"
    update_property "$properties_file" "nifi.security.truststoreType" "PKCS12"
    update_property "$properties_file" "nifi.security.truststorePasswd" "$storepass"

    if ! id -u nifi >/dev/null 2>&1; then
        useradd --system --no-create-home --home-dir "$nifi_home" --shell /usr/sbin/nologin nifi
    fi

    chown -R nifi:nifi "$nifi_home"

    local java_cmd
    java_cmd=$(command -v javac || command -v java)
    local java_home=""
    if [ -n "$java_cmd" ]; then
        java_home=$(dirname "$(dirname "$(readlink -f "$java_cmd")")")
    fi

    local start_script="$nifi_home/start_nifi.sh"

    cat > "$start_script" <<'EOF_START'
#!/usr/bin/env bash
set -euo pipefail

if [ -n "${JAVA_HOME:-}" ] && [ ! -x "${JAVA_HOME}/bin/java" ]; then
    unset JAVA_HOME
fi

DEFAULT_JAVA_HOME_PLACEHOLDER

detect_java_home() {
    if [ -n "${DEFAULT_JAVA_HOME:-}" ] && [ -x "${DEFAULT_JAVA_HOME}/bin/java" ]; then
        echo "${DEFAULT_JAVA_HOME}"
        return 0
    fi

    if [ -n "${JAVA_HOME:-}" ] && [ -x "${JAVA_HOME}/bin/java" ]; then
        echo "${JAVA_HOME}"
        return 0
    fi

    candidates=(
        "/usr/lib/jvm/java-21-openjdk-amd64"
        "/usr/lib/jvm/java-17-openjdk-amd64"
        "/usr/lib/jvm/java-11-openjdk-amd64"
        "/usr/lib/jvm/default-java"
        "/usr/lib/jvm/java-21-openjdk"
        "/usr/lib/jvm/java-17-openjdk"
    )
    for c in "${candidates[@]}"; do
        if [ -x "${c}/bin/java" ]; then
            echo "${c}"
            return 0
        fi
    done

    if command -v java >/dev/null 2>&1; then
        java_path=$(readlink -f "$(command -v java)" ) || java_path=""
        if [ -n "$java_path" ]; then
            echo "$(dirname "$(dirname "$java_path")")"
            return 0
        fi
    fi

    return 1
}

JAVA_HOME_DETECTED=$(detect_java_home || true)
if [ -n "$JAVA_HOME_DETECTED" ] && [ -x "$JAVA_HOME_DETECTED/bin/java" ]; then
    export JAVA_HOME="$JAVA_HOME_DETECTED"
else
    echo "[WARN] Could not determine a valid JAVA_HOME; proceeding without exporting JAVA_HOME" >&2
fi
EOF_START

    cat >> "$start_script" <<EOF_APPEND
export NIFI_HOME="$nifi_home"
export NIFI_WEB_HTTPS_HOST=0.0.0.0
export NIFI_WEB_HTTPS_PORT=8443
export NIFI_WEB_PROXY_HOST="${NIFI_WEB_PROXY_HOST:-localhost:8080}"
export NIFI_SECURITY_USER_LOGIN_IDENTITY_PROVIDER=single-user-provider
export NIFI_SECURITY_USER_AUTHORIZER=single-user-authorizer
export NIFI_SENSITIVE_PROPS_KEY="$NIFI_SENSITIVE_PROPS_KEY"
export NIFI_JVM_HEAP_INIT="${NIFI_JVM_HEAP_INIT:-1g}"
export NIFI_JVM_HEAP_MAX="${NIFI_JVM_HEAP_MAX:-2g}"
export PYTHONPATH="$py_ext_dir:$vendor_dir"

"$nifi_home/bin/nifi.sh" set-single-user-credentials "$NIFI_ADMIN_USER" "$NIFI_ADMIN_PASSWORD"
"$nifi_home/bin/nifi.sh" start
EOF_APPEND

    chmod +x "$start_script"
    chown nifi:nifi "$start_script"

    if [ -n "$java_home" ] && [ -x "$java_home/bin/java" ]; then
        esc_java_home=$(printf '%s' "$java_home" | sed 's/[\\/&]/\\&/g')
        sed -i "s/DEFAULT_JAVA_HOME_PLACEHOLDER/DEFAULT_JAVA_HOME=\"$esc_java_home\"/" "$start_script" || true
    else
        sed -i "s/DEFAULT_JAVA_HOME_PLACEHOLDER/#DEFAULT_JAVA_HOME_NOT_SET/" "$start_script" || true
    fi

    info "Starting NiFi with single-user authentication"
    su -s /bin/bash nifi -c "$start_script" >> "$LOGS_DIR/nifi.log" 2>&1

    sleep 10
    wait_for_service "https://localhost:8443/nifi/" "NiFi" 180

    success "NiFi configured and running"
}

verify_minimal_services() {
    info "Verifying minimal service health"

    if command -v pg_isready >/dev/null 2>&1; then
        if sudo -u postgres pg_isready -q -d "$POSTGRES_DB"; then
            success "PostgreSQL is accepting connections"
        else
            error "PostgreSQL is not ready — pg_isready check failed"
        fi
    else
        info "pg_isready not available; performing fallback psql check"
        sudo -u postgres psql -d "$POSTGRES_DB" -c "SELECT 1;" >/dev/null
        success "PostgreSQL responded to SELECT 1"
    fi

    wait_for_service "http://localhost:18080/nifi-registry/" "NiFi Registry" 60
    wait_for_service "https://localhost:8443/nifi/" "NiFi" 180

    success "All minimal services are healthy"
}

minimal_setup_main() {
    local start_time=$(date +%s)
    
    info "====================================================================="
    info "🚀 EDI LENS - MINIMAL CODEX SETUP"
    info "====================================================================="
    info "Starting setup for PostgreSQL, NiFi, and NiFi Registry"
    info "Timestamp: $(date)"
    info "====================================================================="

    # Step 1: Environment preparation
    info "📋 STEP 1/7: Environment preparation"
    setup_environment

    # Step 2: Dependency analysis
    info "📋 STEP 2/7: Analyzing cached dependencies"
    log_cached_services_state

    # Step 3: System dependencies
    info "📋 STEP 3/9: Installing system dependencies"
    install_minimal_system_dependencies

    # Step 4: Backend dependencies
    info "📋 STEP 4/9: Backend dependencies setup"
    setup_backend_dependencies

    # Step 5: PostgreSQL setup
    info "📋 STEP 5/9: PostgreSQL setup"
    setup_postgresql

    # Step 6: NiFi Registry setup
    info "📋 STEP 6/9: NiFi Registry setup"
    setup_nifi_registry

    # Step 7: NiFi setup
    info "📋 STEP 7/9: Apache NiFi setup"
    setup_nifi

    # Step 8: Backend service startup
    info "📋 STEP 8/9: Backend service startup"
    start_backend_service

    # Step 9: Final verification
    info "📋 STEP 9/9: Service verification"
    verify_minimal_services

    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    echo ""
    echo "====================================================================="
    success "🎉 SETUP COMPLETED SUCCESSFULLY"
    echo "====================================================================="
    info "⏱️  Total setup time: ${duration} seconds"
    echo ""
    info "🌐 Service endpoints:"
    info "  PostgreSQL : localhost:${POSTGRES_PORT:-5432} (database: $POSTGRES_DB)"
    info "  NiFi       : https://localhost:8443 (user: $NIFI_ADMIN_USER)"
    info "  Registry   : http://localhost:18080"
    info "  Backend API: http://localhost:8000 (docs: http://localhost:8000/docs)"
    echo ""
    info "📁 Service directories:"
    info "  Services   : $SERVICES_DIR"
    info "  Logs       : $LOGS_DIR"
    info "  Environment: $ENV_FILE"
    echo ""
    info "🔧 Maintenance commands:"
    info "  Start all  : sudo bash scripts/maintain_codex.sh start"
    info "  Stop all   : sudo bash scripts/maintain_codex.sh stop"
    info "  Status     : sudo bash scripts/maintain_codex.sh status"
    echo "====================================================================="
}

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICES_DIR_DEFAULT="/opt/codex-services"
SERVICES_DIR_FALLBACK="$PROJECT_ROOT/.codex-services"
SERVICES_DIR="$SERVICES_DIR_DEFAULT"
DOWNLOADS_DIR=""
LOGS_DIR=""
BIN_DIR=""
ENV_FILE="$PROJECT_ROOT/.env.local"

minimal_setup_main "$@"
