#!/bin/bash
set -e

# Check if the main database is ready
pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"

# Check if the sftpgo user has been created
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_SFTPGO_USER'" | grep -q 1

# Check if the nifi_registry user has been created
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_NIFI_REGISTRY_USER'" | grep -q 1
