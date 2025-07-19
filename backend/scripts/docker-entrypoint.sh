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
echo "ENTRYPOINT (as appuser): Waiting for Keycloak..."
while ! curl --fail --silent --head http://keycloak:8080 > /dev/null; do
    echo "ENTRYPOINT: Keycloak not responding yet, sleeping for 3 seconds..."
    sleep 3
done
echo "ENTRYPOINT: Keycloak is ready."

# Run migrations automatically on startup.
echo "ENTRYPOINT (as appuser): Running database migrations..."
if [ -f "/home/appuser/app/alembic.ini" ]; then
    # --- FIX: Revert to the direct command now that the shebang is correct ---
    alembic -c /home/appuser/app/alembic.ini upgrade head
else
    echo "WARNING: alembic.ini not found, skipping migrations"
fi

# Finally, execute the main command passed to the container (e.g., uvicorn).
echo "ENTRYPOINT (as appuser): Starting application..."
exec "$@"