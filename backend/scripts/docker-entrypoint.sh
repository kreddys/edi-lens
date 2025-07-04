#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Define the absolute path to the Python interpreter in our virtual environment.
# This avoids any ambiguity or reliance on the PATH variable.
VENV_PYTHON="/home/appuser/app/.venv/bin/python"

# 1. Run database migrations using the full path to the venv's Python.
#    We use `python -m alembic` which is the most reliable way to run it.
echo "ENTRYPOINT: Running database migrations..."
$VENV_PYTHON -m alembic upgrade head

# 2. Start the main application.
#    Use "exec" to replace the shell process with the Uvicorn process.
#    We can call uvicorn directly because its script will use the same
#    venv python via its own shebang line, which exec handles correctly.
echo "ENTRYPOINT: Starting Uvicorn server..."
exec "$@"