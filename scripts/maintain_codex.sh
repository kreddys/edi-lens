#!/usr/bin/env bash
# Maintenance script to be run on Codex cached container resume.
# It performs lightweight health checks and restarts services if needed.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICES_DIR="/opt/codex-services"
ENV_FILE="$SERVICES_DIR/.env.codex"

# Load environment if available
if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

info() { printf "[MAINTAIN] %s\n" "$1"; }

# Helper to call setup functions from the main script when needed
if [ -f "$PROJECT_ROOT/scripts/setup_codex.sh" ]; then
  # shellcheck source=/dev/null
  source "$PROJECT_ROOT/scripts/setup_codex.sh"
fi

# Ensure PostgreSQL is running
if ! pgrep -f "postgres" >/dev/null 2>&1; then
  info "Postgres not running, attempting setup_postgresql"
  (setup_postgresql) || info "setup_postgresql encountered issues"
else
  info "Postgres running"
fi

# MinIO
if ! curl -fs "http://localhost:9000/minio/health/live" >/dev/null 2>&1; then
  info "MinIO not healthy, attempting setup_minio"
  (setup_minio) || info "setup_minio encountered issues"
else
  info "MinIO healthy"
fi

# Keycloak
if ! curl -fs "http://localhost:8180" >/dev/null 2>&1; then
  info "Keycloak not responding, attempting setup_keycloak"
  (setup_keycloak) || info "setup_keycloak encountered issues"
else
  info "Keycloak responding"
fi

# SFTPGo
if ! curl -fs "http://localhost:8280/healthz" >/dev/null 2>&1; then
  info "SFTPGo not responding, attempting setup_sftpgo"
  (setup_sftpgo) || info "setup_sftpgo encountered issues"
else
  info "SFTPGo responding"
fi

info "Maintenance run complete"
