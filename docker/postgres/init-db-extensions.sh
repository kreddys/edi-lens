#!/bin/bash
set -e

# This script is executed after the main PostgreSQL entrypoint has created the database.
# We connect to the newly created database and install the required extensions.

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE EXTENSION IF NOT EXISTS vector;
    CREATE EXTENSION IF NOT EXISTS age;
    
    -- Load AGE into the search path for the database
    ALTER DATABASE "$POSTGRES_DB" SET search_path = ag_catalog, '$user', public;
EOSQL

echo "✅ pgvector and Apache AGE extensions created successfully in database '$POSTGRES_DB'."