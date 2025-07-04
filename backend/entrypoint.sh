#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

# --- THIS IS THE FIX ---
# Manually add the virtual environment's bin directory to the start of the PATH.
# This is the most reliable way to make its executables available.
export PATH="/app/.venv/bin:$PATH"

# Now, the shell can find 'poetry', 'pytest', 'uvicorn', etc.
# Execute the command passed to the script (e.g., 'poetry run pytest')
exec "$@"