#!/bin/bash
set -e

# This script intelligently handles both production and local development startup.

# If running as root (in production), fix permissions and then re-execute this script as the appuser.
if [ "$(id -u)" = "0" ]; then
    echo "ENTRYPOINT [root]: Fixing volume permissions..."
    chown -R appuser:appuser /home/appuser/app/data
    exec gosu appuser "$0" "$@"
fi

# From here on, the script is running as 'appuser' with the correct PATH from the Dockerfile.

echo "ENTRYPOINT (as appuser): Waiting for Keycloak..."
while ! curl --fail --silent --head http://keycloak:8080 > /dev/null; do
    echo "ENTRYPOINT: Keycloak not responding yet, sleeping for 3 seconds..."
    sleep 3
done
echo "ENTRYPOINT: Keycloak is ready."

# Run migrations automatically on startup.
echo "ENTRYPOINT (as appuser): Running database migrations..."
alembic -c /home/appuser/app/alembic.ini upgrade head

# Finally, execute the main command passed to the container (e.g., uvicorn).
echo "ENTRYPOINT (as appuser): Starting application..."
exec "$@"