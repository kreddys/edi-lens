# Stage 1: Builder stage with all dependencies
# --- THIS IS THE FIX ---
# Pinning to a specific minor version (3.12) that satisfies the pyproject.toml
# constraint (>=3.11, <=3.13) and provides a stable build environment.
FROM python:3.12-slim AS builder

WORKDIR /home/appuser/app
RUN pip install --no-cache-dir poetry
COPY pyproject.toml poetry.lock ./
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root

# Stage 2: Final application stage
# --- THIS IS THE FIX ---
# Using the same pinned Python version as the builder stage for consistency.
FROM python:3.12-slim

# Install dependencies as root. 'gosu' is for production permission handling.
RUN apt-get update && apt-get install -y curl gosu && \
    rm -rf /var/lib/apt/lists/*

# Create user and workdir
RUN useradd --create-home --shell /bin/bash appuser
WORKDIR /home/appuser/app

# Set the PATH environment variable for the entire container.
# This ensures that any shell, exec command, or main process will automatically
# find the executables inside the virtual environment.
ENV PATH="/home/appuser/app/.venv/bin:$PATH"

# Copy project files from the builder stage and local context
COPY --from=builder --chown=appuser:appuser /home/appuser/app/.venv ./.venv
COPY --chown=appuser:appuser . .

# The ENTRYPOINT will run as root to fix permissions before stepping down.
ENTRYPOINT ["/home/appuser/app/scripts/docker-entrypoint.sh"]

# The command to run after the entrypoint script has prepared the environment.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]