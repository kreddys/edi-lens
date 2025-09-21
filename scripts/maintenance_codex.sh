#!/usr/bin/env bash
# Lightweight maintenance script intended to run on resumed cached Codex tasks.
# Detects a cache marker and skips expensive installation work when present.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKER_FILE="/opt/codex-services/.codex_cache_marker"
LOGS_DIR="$PROJECT_ROOT/scripts/.logs"
mkdir -p "$LOGS_DIR"

info(){ printf "[INFO] %s\n" "$1"; }
warn(){ printf "[WARN] %s\n" "$1"; }
error(){ printf "[ERROR] %s\n" "$1"; exit 1; }

info "Running Codex maintenance script"

if [ -f "$MARKER_FILE" ]; then
    info "Cache marker found:"
    cat "$MARKER_FILE" || true
    info "Assuming services and artifacts are present. Running lightweight maintenance."

    # Source the environment if present
    if [ -f "/opt/codex-services/.env.codex" ]; then
        set -a
        # shellcheck source=/dev/null
        source /opt/codex-services/.env.codex
        set +a
    elif [ -f "$PROJECT_ROOT/.env.codex" ]; then
        set -a
        source "$PROJECT_ROOT/.env.codex"
        set +a
    else
        warn "No .env.codex found in repo or /opt — proceeding with defaults"
    fi

    # Quick actions: restart services and run DB migrations
    info "Restarting core services (Postgres, MinIO, Keycloak, SFTPGo, NiFi)"
    pkill -f "minio" || true
    pkill -f "kc.home.dir" || true
    pkill -f "sftpgo" || true
    pkill -f "org.apache.nifi.NiFi" || true
    pkill -f "nifi.registry" || true
    sleep 3

    info "Starting infrastructure and app services via setup helpers"
    # Source setup script functions (if available) and call restart helper
    if [ -f "$PROJECT_ROOT/scripts/setup_codex.sh" ]; then
        # shellcheck source=/dev/null
        source "$PROJECT_ROOT/scripts/setup_codex.sh"
        restart_all_services || warn "restart_all_services reported problems"
    else
        warn "setup_codex.sh not found; cannot call restart helpers."
    fi

    info "Running backend database migrations"
    if [ -d "$PROJECT_ROOT/backend" ]; then
        if [ -f "$PROJECT_ROOT/backend/venv/bin/activate" ]; then
            # shellcheck source=/dev/null
            source "$PROJECT_ROOT/backend/venv/bin/activate"
            cd "$PROJECT_ROOT/backend"
            if command -v poetry >/dev/null 2>&1; then
                poetry run alembic upgrade head || warn "alembic upgrade head failed"
            else
                warn "poetry not available; skipping alembic migrations"
            fi
            deactivate || true
        else
            warn "Backend virtualenv not found; skipping migrations"
        fi
    fi

    info "Maintenance complete"
    exit 0
else
    warn "No cache marker found at $MARKER_FILE — this looks like a fresh container"
    warn "Please run full setup: ./scripts/setup_codex.sh"
    exit 2
fi
