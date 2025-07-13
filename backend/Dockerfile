# Stage 1: Builder stage with all dependencies
FROM python:3.11-slim AS builder

WORKDIR /home/appuser/app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root

# Stage 2: Final application stage
FROM python:3.11-slim

# --- FIX: Install sudo to allow the user to change permissions ---
USER root
RUN apt-get update && apt-get install -y curl sudo && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash appuser
# --- FIX: Give the appuser passwordless sudo privileges ---
RUN echo "appuser ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

USER appuser
WORKDIR /home/appuser/app

ENV PYTHONPATH=/home/appuser/app
ENV PATH="/home/appuser/app/.venv/bin:$PATH"

COPY --from=builder --chown=appuser:appuser /home/appuser/app/.venv ./.venv

# Copy all necessary source code, scripts, and configuration
COPY --chown=appuser:appuser src/ src/
COPY --chown=appuser:appuser scripts/ scripts/
COPY --chown=appuser:appuser alembic/ alembic/
COPY --chown=appuser:appuser alembic.ini .
COPY --chown=appuser:appuser data/ data/

# --- FIX: Change ownership of the data directory inside the container ---
# This ensures the appuser can write to the schema files, even if the
# host directory is owned by root.
RUN sudo chown -R appuser:appuser /home/appuser/app/data

ENTRYPOINT ["/home/appuser/app/scripts/docker-entrypoint.sh"]

# Set the default command that the entrypoint will execute with "exec $@".
# This allows us to easily override the command in docker-compose for other tasks.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]