#!/usr/bin/env bash
# ==============================================================================
# EDI-Lens - Codex Universal Bootstrap
# ------------------------------------------------------------------------------
# Pulls the codex-universal image, starts a container with port mappings, mounts
# the current repo into /workspace/edi-lens, and runs the full setup script to
# start all services and run validations inside the container.
# ==============================================================================
set -euo pipefail

IMAGE=${IMAGE:-ghcr.io/openai/codex-universal:latest}
CONTAINER=${CONTAINER:-edi-lens-codex}
PLATFORM=${PLATFORM:-linux/amd64}   # codex-universal runs on amd64
WORKDIR_HOST=${WORKDIR_HOST:-"$(pwd)"}
WORKDIR_CONT=${WORKDIR_CONT:-/workspace/edi-lens}

# Language runtimes for codex-universal
CODEX_ENV_PYTHON_VERSION=${CODEX_ENV_PYTHON_VERSION:-3.12}
CODEX_ENV_NODE_VERSION=${CODEX_ENV_NODE_VERSION:-22}
CODEX_ENV_GO_VERSION=${CODEX_ENV_GO_VERSION:-1.24.3}

# Ports to expose (host:container)
PORTS=(
  5432:5432   # PostgreSQL
  8000:8000   # Backend
  3000:3000   # Frontend
  8180:8180   # Keycloak
  8280:8280   # SFTPGo
  2022:2022   # SFTPGo SFTP
  9000:9000   # MinIO S3
  9001:9001   # MinIO Console
  8080:8080   # NiFi HTTP (optional)
  8443:8443   # NiFi HTTPS
  18080:18080 # NiFi Registry
)

log() { printf "\033[0;34m[INFO]\033[0m %s\n" "$*"; }
ok()  { printf "\033[0;32m[SUCCESS]\033[0m %s\n" "$*"; }
warn(){ printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
err() { printf "\033[0;31m[ERROR]\033[0m %s\n" "$*"; exit 1; }

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || err "Missing required command: $1"
}

usage() {
  cat <<EOF
Usage: $0 [--recreate] [--no-pull] [--no-setup] [--platform linux/amd64]

Options:
  --recreate     Remove any existing container named '${CONTAINER}' and start fresh.
  --no-pull      Do not pull the image before starting.
  --no-setup     Start the container only; skip running setup scripts inside.
  --platform P   Override platform (default: ${PLATFORM}).

Environment overrides:
  IMAGE, CONTAINER, CODEX_ENV_PYTHON_VERSION, CODEX_ENV_NODE_VERSION, CODEX_ENV_GO_VERSION
EOF
}

RECREATE=false
PULL=true
RUN_SETUP=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --recreate) RECREATE=true; shift ;;
    --no-pull)  PULL=false; shift ;;
    --no-setup) RUN_SETUP=false; shift ;;
    --platform) PLATFORM="$2"; shift 2 ;;
    -h|--help)  usage; exit 0 ;;
    *) warn "Unknown argument: $1"; shift ;;
  esac
done

require_cmd docker

if $PULL; then
  log "Pulling image: ${IMAGE}"
  docker pull "${IMAGE}"
fi

# Remove existing container if requested
if $RECREATE && docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  log "Removing existing container ${CONTAINER}"
  docker rm -f "${CONTAINER}" >/dev/null 2>&1 || true
fi

# Start container if not running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  log "Starting container ${CONTAINER} from ${IMAGE} (${PLATFORM})"
  PORT_ARGS=()
  for p in "${PORTS[@]}"; do PORT_ARGS+=( -p "$p" ); done

  docker run -dit \
    --name "${CONTAINER}" \
    --platform "${PLATFORM}" \
    -e CODEX_ENV_PYTHON_VERSION="${CODEX_ENV_PYTHON_VERSION}" \
    -e CODEX_ENV_NODE_VERSION="${CODEX_ENV_NODE_VERSION}" \
    -e CODEX_ENV_GO_VERSION="${CODEX_ENV_GO_VERSION}" \
    -v "${WORKDIR_HOST}:${WORKDIR_CONT}" \
    -w "${WORKDIR_CONT}" \
    "${PORT_ARGS[@]}" \
    "${IMAGE}"
else
  log "Container ${CONTAINER} already running"
fi

# Helper to run a command inside the container
cexec() {
  docker exec -i "${CONTAINER}" bash -lc "$*"
}

if $RUN_SETUP; then
  log "Normalizing script line endings (if any)"
  cexec 'find ./docker/codex-universal ./scripts -maxdepth 1 -type f -name "*.sh" -exec sed -i "s/\r$//" {} + || true'

  log "Running EDI-Lens Codex setup (this will take a while)"
  # Capture logs locally for convenience
  mkdir -p scripts/.logs
  cexec "bash ./scripts/setup_codex.sh --skip-frontend-tests" | tee scripts/.logs/codex_setup_$(date +%Y%m%d_%H%M%S).log

  log "Checking service status"
  cexec "bash ./scripts/setup_codex.sh --check-services --skip-frontend-tests" || true

  ok "Setup completed. Services should be available on your host:"
  cat <<URLS
  - Frontend:        http://localhost:3000
  - Backend API:     http://localhost:8000
  - API Docs:        http://localhost:8000/docs
  - Keycloak:        http://localhost:8180  (admin / admin_codex_2024)
  - SFTPGo:          http://localhost:8280  (admin / sftpgo_admin_2024)
  - MinIO Console:   http://localhost:9001  (codex_minio_access / codex_minio_secret_2024)
  - NiFi:            https://localhost:8443 (admin / nifi_admin_codex_2024)
  - NiFi Registry:   http://localhost:18080

  Container name: ${CONTAINER}
  To inspect logs: docker exec -it ${CONTAINER} bash -lc 'ls -lah codex-services/logs && tail -n 200 codex-services/logs/backend.log'
URLS
else
  ok "Container started without running setup. You can now exec into it:"
  echo "  docker exec -it ${CONTAINER} bash"
  echo "Then run: ./docker/codex-universal/setup_universal.sh && ./docker/codex-universal/verify.sh && ./scripts/setup_codex.sh"
fi
