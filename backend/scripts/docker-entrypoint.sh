#!/bin/bash
set -e

# Manually add the virtual environment's bin directory to the start of the PATH.
export PATH="/home/appuser/app/.venv/bin:$PATH"

# This script intelligently handles both production and local development startup.
if [ "$(id -u)" = "0" ]; then
    echo "ENTRYPOINT [root]: Fixing volume permissions..."
    chown -R appuser:appuser /home/appuser/app
    exec gosu appuser "$0" "$@"
fi

# From here on, the script is running as 'appuser' with the correct PATH.

# --- THIS IS THE FINAL, ROBUST VERSION ---
KEYCLOAK_HEALTH_URL=${KEYCLOAK_URL:-http://keycloak:8080}
MAX_RETRIES=30
RETRY_INTERVAL=3

echo "ENTRYPOINT (as appuser): Waiting for Keycloak at ${KEYCLOAK_HEALTH_URL}..."

# Loop for a maximum number of retries
for i in $(seq 1 $MAX_RETRIES); do
    if curl --fail --silent --head "${KEYCLOAK_HEALTH_URL}" > /dev/null; then
        echo "ENTRYPOINT: Keycloak is ready."
        break # Exit the loop if Keycloak is healthy
    fi

    if [ "$i" -eq "$MAX_RETRIES" ]; then
        echo "ERROR: Keycloak did not become available after ${MAX_RETRIES} attempts."
        exit 1 # Exit with an error code if max retries are reached
    fi

    echo "ENTRYPOINT: Keycloak not responding yet (attempt ${i}/${MAX_RETRIES}). Retrying in ${RETRY_INTERVAL} seconds..."
    sleep $RETRY_INTERVAL
done
# --- END OF FIX ---

# Run migrations automatically on startup.
echo "ENTRYPOINT (as appuser): Running database migrations..."
if [ -f "/home/appuser/app/alembic.ini" ]; then
    alembic -c /home/appuser/app/alembic.ini upgrade head
else
    echo "WARNING: alembic.ini not found, skipping migrations"
fi

# Finally, execute the main command passed to the container (e.g., uvicorn or tail).
echo "ENTRYPOINT (as appuser): Starting container command..."
exec "$@"