#!/bin/bash
set -e

# Check if the main database is ready
echo "Checking main database connection..."
pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"
echo "Main database is ready."

# Check if Apache AGE extension is installed
echo "Checking Apache AGE extension..."
if psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT extname FROM pg_extension WHERE extname = 'age'" | grep -q age; then
    echo "Apache AGE extension is installed."
    # Check if AGE schema is available
    if psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'ag_catalog'" | grep -q ag_catalog; then
        echo "Apache AGE schema is available."
    else
        echo "Apache AGE schema is not available."
        exit 1
    fi
else
    echo "Apache AGE extension is not installed."
    exit 1
fi

# Check if pgvector extension is installed
echo "Checking pgvector extension..."
if psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT extname FROM pg_extension WHERE extname = 'vector'" | grep -q vector; then
    echo "pgvector extension is installed."
    # Simple test to verify pgvector is working by creating a vector
    if psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT '[1,2,3]'::vector" >/dev/null 2>&1; then
        echo "pgvector is working correctly."
    else
        echo "pgvector is not working correctly."
        exit 1
    fi
else
    echo "pgvector extension is not installed."
    exit 1
fi

# Check if the Keycloak user has been created
echo "Checking if Keycloak user exists..."
if psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_KC_USER'" | grep -q 1; then
    echo "Keycloak user exists."
else
    echo "Keycloak user does not exist."
    exit 1
fi

# Check if the sftpgo user has been created
echo "Checking if SFTPGo user exists..."
if psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_SFTPGO_USER'" | grep -q 1; then
    echo "SFTPGo user exists."
else
    echo "SFTPGo user does not exist."
    exit 1
fi

# Check if the nifi_registry user has been created
echo "Checking if NiFi Registry user exists..."
if psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_NIFI_REGISTRY_USER'" | grep -q 1; then
    echo "NiFi Registry user exists."
else
    echo "NiFi Registry user does not exist."
    exit 1
fi

echo "All checks passed."
