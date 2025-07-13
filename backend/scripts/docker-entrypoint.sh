#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- THIS IS THE FIX: Wait for Keycloak before starting the backend ---
# This script runs inside the backend container, which has curl installed.
echo "ENTRYPOINT: Waiting for Keycloak to become available at http://keycloak:8080..."
# We will check the root URL. We expect a 3xx redirect, which is fine.
# We just need to know the port is open and the service is responding to HTTP.
while ! curl --fail --silent --head http://keycloak:8080 > /dev/null; do
    echo "ENTRYPOINT: Keycloak not responding yet, sleeping for 3 seconds..."
    sleep 3
done
echo "ENTRYPOINT: Keycloak is ready."

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