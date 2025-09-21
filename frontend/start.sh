#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR"
REPO_ROOT="$(cd "$FRONTEND_DIR/.." && pwd)"

DEFAULT_ENV_FILE="$REPO_ROOT/.env.codex"
PERSISTENT_ENV_FILE="/opt/codex-services/.env.codex"

if [ -f "$PERSISTENT_ENV_FILE" ]; then
    ACTIVE_ENV_FILE="$PERSISTENT_ENV_FILE"
else
    ACTIVE_ENV_FILE="$DEFAULT_ENV_FILE"
fi

if [ -f "$ACTIVE_ENV_FILE" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$ACTIVE_ENV_FILE"
    set +a
fi

cd "$FRONTEND_DIR"
exec npm run dev -- --host 0.0.0.0 --port 3000
