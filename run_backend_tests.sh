#!/bin/bash
echo "--- Attempting to change to backend directory ---"
cd backend
if [ $? -ne 0 ]; then
  echo "--- ERROR: Failed to cd into backend directory ---"
  exit 1
fi
echo "--- Successfully changed to backend directory ---"
echo "--- Current directory: $(pwd) ---"

echo "--- Creating .env file for testing ---"
cat <<EOF > .env
POSTGRES_USER=edi_user
POSTGRES_PASSWORD=your_super_secret_password
POSTGRES_DB=edi_lens_test_db
POSTGRES_SERVER=localhost
POSTGRES_PORT=5432
LOG_LEVEL=DEBUG
BACKEND_HOST=localhost
KEYCLOAK_ADMIN_USER=admin
KEYCLOAK_ADMIN_PASSWORD=admin
KEYCLOAK_DB_VENDOR=postgres
KEYCLOAK_DB_HOST=localhost
KEYCLOAK_DB_PORT=5432
KEYCLOAK_DB_DATABASE=keycloak_test_db
KEYCLOAK_DB_USER=edi_user
KEYCLOAK_DB_PASSWORD=edi_password
KEYCLOAK_URL=http://localhost:8088
KEYCLOAK_BROWSER_URL=http://localhost:8088
KEYCLOAK_REALM=edi-lens-test
KEYCLOAK_BACKEND_CLIENT_ID=edi-lens-backend-test
KEYCLOAK_BACKEND_CLIENT_SECRET=this-is-a-very-secret-key-for-tests
KEYCLOAK_UI_CLIENT_ID=edi-lens-ui-test
EOF
echo "--- .env file created ---"

echo "--- Exporting .env variables ---"
# Ensure python-dotenv is available to parse .env for export if needed,
# or do it manually. For simplicity, let's try a common way to export.
# This requires the variables to not have spaces or special chars that break `export`.
# The values I'm using are simple enough.
set -a # Automatically export all variables subsequently set or modified
source .env
set +a # Stop auto-exporting
echo "--- .env variables exported ---"

echo "--- Attempting to install dependencies (should be cached) ---"
poetry install --with dev
if [ $? -ne 0 ]; then
  echo "--- ERROR: Poetry install failed ---"
  exit 1
fi
echo "--- Successfully installed dependencies ---"

echo "--- Attempting to run tests using poetry run ---"
poetry run pytest -s -m "not integration" tests/core/test_edi_parser_837p.py tests/core/test_edi_parser.py
PYTEST_EXIT_CODE=$? # Capture exit code

if [ $PYTEST_EXIT_CODE -ne 0 ]; then
  echo "--- ERROR: Pytest failed with exit code $PYTEST_EXIT_CODE ---"
fi
echo "--- Tests completed ---"
# Clean up the .env file
rm .env
echo "--- Cleaned up .env file ---"
exit $PYTEST_EXIT_CODE # Exit with pytest's exit code
