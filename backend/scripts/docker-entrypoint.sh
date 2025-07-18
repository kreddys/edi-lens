#!/bin/bash
set -e

# --- FIX: Environment Setup for Docker Volumes ---
# Manually add the virtual environment's bin directory to the start of the PATH.
# This makes the script robust against development volume mounts that can obscure the .venv
# created during the image build, ensuring commands like 'alembic' are found.
export PATH="/home/appuser/app/.venv/bin:$PATH"

# This script intelligently handles both production and local development startup.

# If running as root (in production), fix permissions and then re-execute this script as the appuser.
if [ "$(id -u)" = "0" ]; then
    echo "ENTRYPOINT [root]: Fixing volume permissions..."
    chown -R appuser:appuser /home/appuser/app/data
    # Also ensure the .venv directory has correct permissions
    chown -R appuser:appuser /home/appuser/app/.venv
    exec gosu appuser "$0" "$@"
fi

# From here on, the script is running as 'appuser' with the correct PATH.

echo "ENTRYPOINT (as appuser): Waiting for Keycloak..."
while ! curl --fail --silent --head http://keycloak:8080 > /dev/null; do
    echo "ENTRYPOINT: Keycloak not responding yet, sleeping for 3 seconds..."
    sleep 3
done
echo "ENTRYPOINT: Keycloak is ready."

# Verify alembic is available and working
echo "ENTRYPOINT (as appuser): Checking alembic availability..."
if ! which alembic > /dev/null 2>&1; then
    echo "ERROR: alembic command not found in PATH"
    echo "Current PATH: $PATH"
    echo "Contents of .venv/bin:"
    ls -la /home/appuser/app/.venv/bin/ || echo "No .venv/bin directory found"
    exit 1
fi

# Run migrations automatically on startup.
echo "ENTRYPOINT (as appuser): Running database migrations..."
if [ -f "/home/appuser/app/alembic.ini" ]; then
    alembic -c /home/appuser/app/alembic.ini upgrade head
else
    echo "WARNING: alembic.ini not found, skipping migrations"
fi

# Finally, execute the main command passed to the container (e.g., uvicorn).
echo "ENTRYPOINT (as appuser): Starting application..."
exec "$@"