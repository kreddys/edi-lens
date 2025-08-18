#!/bin/bash
set -e

# Function to print timestamped messages
log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}

# Manually add the virtual environment's bin directory to the start of the PATH.
export PATH="/home/appuser/app/.venv/bin:$PATH"

# This script intelligently handles both production and local development startup.
if [ "$(id -u)" = "0" ]; then
    log "ENTRYPOINT [root]: Fixing volume permissions..."
    chown -R appuser:appuser /home/appuser/app
    exec gosu appuser "$0" "$@"
fi

# From here on, the script is running as 'appuser' with the correct PATH.

# Wait for database to be ready before proceeding
DB_HOST=${POSTGRES_HOST:-db}
DB_PORT=${POSTGRES_PORT:-5432}
DB_USER=${POSTGRES_USER}
DB_NAME=${POSTGRES_DB}
DB_MAX_RETRIES=30
DB_RETRY_INTERVAL=1

log "ENTRYPOINT (as appuser): Waiting for database at ${DB_HOST}:${DB_PORT}..."
log "ENTRYPOINT: Using user '${DB_USER}' and database '${DB_NAME}'"

# Loop for a maximum number of retries to check database readiness
for i in $(seq 1 $DB_MAX_RETRIES); do
    log "ENTRYPOINT: Attempt $i/$DB_MAX_RETRIES to check database readiness..."
    
    # Try a simple psql connection
    if PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" > /dev/null 2>&1; then
        log "ENTRYPOINT: Database is ready (psql connection succeeded)."
        break # Exit the loop if database is ready
    else
        # Get more detailed error information
        PGPASSWORD="${POSTGRES_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "SELECT 1;" 2>&1 || true
    fi

    if [ "$i" -eq "$DB_MAX_RETRIES" ]; then
        log "ERROR: Database did not become available after ${DB_MAX_RETRIES} attempts."
        exit 1 # Exit with an error code if max retries are reached
    fi

    log "ENTRYPOINT: Database not responding yet (attempt ${i}/${DB_MAX_RETRIES}). Retrying in ${DB_RETRY_INTERVAL} seconds..."
    sleep $DB_RETRY_INTERVAL
done

# Only wait for Keycloak in non-test environments or when explicitly needed
if [ "$WAIT_FOR_KEYCLOAK" != "false" ]; then
    KEYCLOAK_HEALTH_URL=${KEYCLOAK_URL:-http://keycloak:8080}
    MAX_RETRIES=30
    RETRY_INTERVAL=1

    log "ENTRYPOINT (as appuser): Waiting for Keycloak at ${KEYCLOAK_HEALTH_URL}..."

    # Loop for a maximum number of retries
    for i in $(seq 1 $MAX_RETRIES); do
        if curl --fail --silent --head "${KEYCLOAK_HEALTH_URL}" > /dev/null; then
            log "ENTRYPOINT: Keycloak is ready."
            break # Exit the loop if Keycloak is healthy
        fi

        if [ "$i" -eq "$MAX_RETRIES" ]; then
            log "ERROR: Keycloak did not become available after ${MAX_RETRIES} attempts."
            exit 1 # Exit with an error code if max retries are reached
        fi

        log "ENTRYPOINT: Keycloak not responding yet (attempt ${i}/${MAX_RETRIES}). Retrying in ${RETRY_INTERVAL} seconds..."
        sleep $RETRY_INTERVAL
    done
else
    log "ENTRYPOINT: Skipping Keycloak wait (WAIT_FOR_KEYCLOAK=false)"
fi

# Run migrations automatically on startup.
log "ENTRYPOINT (as appuser): Running database migrations..."
if [ -f "/home/appuser/app/alembic.ini" ]; then
    alembic -c /home/appuser/app/alembic.ini upgrade head
else
    log "WARNING: alembic.ini not found, skipping migrations"
fi

# Finally, execute the main command passed to the container (e.g., uvicorn or tail).
log "ENTRYPOINT (as appuser): Starting container command..."
exec "$@"