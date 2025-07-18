#!/bin/bash
set -e

# This script now connects to the main application database (${POSTGRES_DB})
# and ensures the schema for Keycloak's tables exists.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE SCHEMA IF NOT EXISTS ${KEYCLOAK_DB_SCHEMA};
    GRANT ALL ON SCHEMA ${KEYCLOAK_DB_SCHEMA} TO ${POSTGRES_USER};
EOSQL

echo "✅ Keycloak schema '${KEYCLOAK_DB_SCHEMA}' is ready in database '${POSTGRES_DB}'."