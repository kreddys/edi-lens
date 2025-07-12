#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- THIS IS THE FIX ---
# Define absolute paths to the python executable and the alembic config.
# This makes the script resilient to where it's called from.
APP_DIR="/home/appuser/app"
VENV_PYTHON="${APP_DIR}/.venv/bin/python"
ALEMBIC_CONFIG="${APP_DIR}/alembic.ini"

# 1. Run database migrations using absolute paths.
echo "ENTRYPOINT: Running database migrations..."
$VENV_PYTHON -m alembic -c "$ALEMBIC_CONFIG" upgrade head

# 2. Start the main application.
#    Use "exec" to replace the shell process with the Uvicorn process.
echo "ENTRYPOINT: Starting Uvicorn server..."
exec "$@"