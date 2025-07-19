# FILE: docker/backend/Dockerfile (Corrected Paths)

# --- Stage 1: The Builder ---
# This stage installs all dependencies, including build-time tools.
FROM python:3.12-slim as builder

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_CACHE_DIR=/tmp/poetry_cache

# Install build-time system dependencies and Poetry
RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential && \
    pip install --no-cache-dir poetry

# --- FIX: Use the final WORKDIR path in the builder stage ---
WORKDIR /home/appuser/app

# Copy only the dependency definition files to leverage Docker cache
COPY backend/pyproject.toml backend/poetry.lock ./

# Install project dependencies
RUN poetry install --only main --no-root

# Copy the rest of the application source code
COPY backend/src ./src
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/scripts ./scripts

# --- Stage 2: The Final Image ---
# This stage is clean and minimal, containing only what's needed to run the app.
FROM python:3.12-slim

# Install runtime-only system dependencies and create the app user
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gosu && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    useradd --create-home --shell /bin/bash appuser

# --- Use the same WORKDIR as the builder ---
WORKDIR /home/appuser/app

# --- FIX: Copy from the corrected builder path ---
# Copy the virtual environment from the builder stage
COPY --from=builder --chown=appuser:appuser /home/appuser/app/.venv ./.venv

# Copy the application code from the builder stage
COPY --from=builder --chown=appuser:appuser /home/appuser/app/src ./src
COPY --from=builder --chown=appuser:appuser /home/appuser/app/alembic ./alembic
COPY --from=builder --chown=appuser:appuser /home/appuser/app/alembic.ini ./
COPY --from=builder --chown=appuser:appuser /home/appuser/app/scripts ./scripts

# Set the PATH to include the virtual environment's executables
ENV PATH="/home/appuser/app/.venv/bin:$PATH"

# Ensure entrypoint script is executable
RUN chmod +x /home/appuser/app/scripts/docker-entrypoint.sh

# The ENTRYPOINT will run as root to fix permissions before stepping down
ENTRYPOINT ["/home/appuser/app/scripts/docker-entrypoint.sh"]

# The command to run after the entrypoint script has prepared the environment
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]