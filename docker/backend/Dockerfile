# FILE: docker/backend/Dockerfile (Multi-Target, Corrected)

# --- Stage 1: A common builder for all dependencies AND source code ---
FROM python:3.12-slim as builder
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_CACHE_DIR=/tmp/poetry_cache

RUN apt-get update && apt-get install -y --no-install-recommends curl build-essential && \
    pip install --no-cache-dir poetry

WORKDIR /home/appuser/app
COPY backend/pyproject.toml backend/poetry.lock ./

# Install ALL dependencies, including dev, in this stage
RUN poetry install --no-root

# --- THIS IS THE FIX ---
# Now, copy the application source code into the builder stage.
# This makes it available for the subsequent stages to copy from.
COPY backend/src ./src
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/scripts ./scripts
# --- END OF FIX ---


# --- Stage 2: The lean PRODUCTION image ---
FROM python:3.12-slim as production

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gosu postgresql-client && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    useradd --create-home --shell /bin/bash appuser

WORKDIR /home/appuser/app

# 1. Copy the project definition files from the builder
COPY --from=builder /home/appuser/app/pyproject.toml /home/appuser/app/poetry.lock ./

# 2. Copy the full virtual environment from the builder
COPY --from=builder /home/appuser/app/.venv ./.venv

# 3. Now, run the poetry command in the same layer as its installation/uninstallation
RUN pip install --no-cache-dir poetry && \
    . .venv/bin/activate && \
    poetry install --only main --sync --no-root && \
    pip uninstall -y poetry

# Copy application source code from the builder
COPY --from=builder /home/appuser/app/src ./src
COPY --from=builder /home/appuser/app/alembic ./alembic
COPY --from=builder /home/appuser/app/alembic.ini ./
COPY --from=builder /home/appuser/app/scripts ./scripts

ENV PATH="/home/appuser/app/.venv/bin:$PATH"
RUN chmod +x /home/appuser/app/scripts/docker-entrypoint.sh
ENTRYPOINT ["/home/appuser/app/scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]


# --- Stage 3: The TEST image (includes dev dependencies) ---
FROM python:3.12-slim as test

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl gosu postgresql-client && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean && \
    useradd --create-home --shell /bin/bash appuser

WORKDIR /home/appuser/app

# Copy the FULL virtual environment (with pytest) from the builder.
COPY --from=builder /home/appuser/app/.venv ./.venv

# Copy application source code from the builder (this will now work)
COPY --from=builder /home/appuser/app/src ./src
COPY --from=builder /home/appuser/app/alembic ./alembic
COPY --from=builder /home/appuser/app/alembic.ini ./
COPY --from=builder /home/appuser/app/scripts ./scripts

ENV PATH="/home/appuser/app/.venv/bin:$PATH"
RUN chmod +x /home/appuser/app/scripts/docker-entrypoint.sh
ENTRYPOINT ["/home/appuser/app/scripts/docker-entrypoint.sh"]
CMD ["tail", "-f", "/dev/null"]