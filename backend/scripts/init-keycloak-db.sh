#!/bin/bash
set -e

# This script uses psql's flags to get clean output for shell scripting:
# -t (tuples_only) -> no headers/footers
# -A (no_align) -> unaligned text output
# -c (command) -> run a single command string

# We connect to the default 'postgres' database to perform administrative tasks.
# The main POSTGRES_USER is used as the superuser.

# First, check if the Keycloak database already exists.
# The query returns '1' if it exists, and nothing if it doesn't.
DB_EXISTS=$(psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" -tAc "SELECT 1 FROM pg_database WHERE datname='${KEYCLOAK_DB_DATABASE}'")

# Use a standard shell 'if' to check if the variable is empty.
if [ -z "$DB_EXISTS" ]; then
  # If the database does not exist, create it with the main user as the owner.
  # This is a simple, direct SQL command.
  echo "Database '${KEYCLOAK_DB_DATABASE}' not found. Creating..."
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" -c "CREATE DATABASE \"${KEYCLOAK_DB_DATABASE}\" OWNER \"${POSTGRES_USER}\";"
  echo "✅ Keycloak database '${KEYCLOAK_DB_DATABASE}' created and owned by '${POSTGRES_USER}'."
else
  echo "✅ Keycloak database '${KEYCLOAK_DB_DATABASE}' already exists."
fi