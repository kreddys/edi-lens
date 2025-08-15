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

# --- Create the dedicated database and user for SFTPGo ---
# We check if the database exists before creating it to make this script runnable multiple times.
if ! psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -lqt | cut -d \| -f 1 | grep -qw "$POSTGRES_SFTPGO_DB"; then
  echo "Database '$POSTGRES_SFTPGO_DB' does not exist. Creating it now..."
  # <-- FIX: Added --dbname "$POSTGRES_DB" to connect to the main app DB to run the create command
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
      CREATE DATABASE "$POSTGRES_SFTPGO_DB";
EOSQL
  echo "✅ Database '$POSTGRES_SFTPGO_DB' created."
else
  echo "Database '$POSTGRES_SFTPGO_DB' already exists. Skipping creation."
fi

# We check if the user exists before creating it.
# <-- FIX: Added --dbname "$POSTGRES_DB" to connect to the main app DB to run the check
if ! psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_SFTPGO_USER'" | grep -q 1; then
  echo "User '$POSTGRES_SFTPGO_USER' does not exist. Creating it now..."
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
      CREATE USER "$POSTGRES_SFTPGO_USER" WITH PASSWORD '$POSTGRES_SFTPGO_PASSWORD';
      GRANT ALL PRIVILEGES ON DATABASE "$POSTGRES_SFTPGO_DB" TO "$POSTGRES_SFTPGO_USER";
EOSQL
  echo "✅ User '$POSTGRES_SFTPGO_USER' created and granted privileges."
else
    echo "User '$POSTGRES_SFTPGO_USER' already exists. Skipping creation."
fi

echo "Granting schema permissions to '$POSTGRES_SFTPGO_USER' on database '$POSTGRES_SFTPGO_DB'..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_SFTPGO_DB" <<-EOSQL
    GRANT USAGE, CREATE ON SCHEMA public TO "$POSTGRES_SFTPGO_USER";
EOSQL
echo "✅ Schema permissions granted."

# --- Create the dedicated database and user for NiFi Registry ---
if ! psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -lqt | cut -d \| -f 1 | grep -qw "$POSTGRES_NIFI_REGISTRY_DB"; then
  echo "Database '$POSTGRES_NIFI_REGISTRY_DB' does not exist. Creating it now..."
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
      CREATE DATABASE "$POSTGRES_NIFI_REGISTRY_DB";
EOSQL
  echo "✅ Database '$POSTGRES_NIFI_REGISTRY_DB' created."
else
  echo "Database '$POSTGRES_NIFI_REGISTRY_DB' already exists. Skipping creation."
fi

if ! psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_NIFI_REGISTRY_USER'" | grep -q 1; then
  echo "User '$POSTGRES_NIFI_REGISTRY_USER' does not exist. Creating it now..."
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
      CREATE USER "$POSTGRES_NIFI_REGISTRY_USER" WITH PASSWORD '$POSTGRES_NIFI_REGISTRY_PASSWORD';
      GRANT ALL PRIVILEGES ON DATABASE "$POSTGRES_NIFI_REGISTRY_DB" TO "$POSTGRES_NIFI_REGISTRY_USER";
EOSQL
  echo "✅ User '$POSTGRES_NIFI_REGISTRY_USER' created and granted privileges."
else
    echo "User '$POSTGRES_NIFI_REGISTRY_USER' already exists. Skipping creation."
fi

echo "Granting schema permissions to '$POSTGRES_NIFI_REGISTRY_USER' on database '$POSTGRES_NIFI_REGISTRY_DB'..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_NIFI_REGISTRY_DB" <<-EOSQL
    GRANT USAGE, CREATE ON SCHEMA public TO "$POSTGRES_NIFI_REGISTRY_USER";
EOSQL
echo "✅ Schema permissions granted to NiFi Registry user."
