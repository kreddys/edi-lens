# Stage 1: Builder stage with all dependencies
FROM python:3.11-slim AS builder

WORKDIR /home/appuser/app

RUN pip install --no-cache-dir poetry

COPY pyproject.toml poetry.lock ./

RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root


# Stage 2: Final application stage
FROM python:3.11-slim

USER root
RUN apt-get update && apt-get install -y curl && \
    rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash appuser
USER appuser
WORKDIR /home/appuser/app

ENV PYTHONPATH=/home/appuser/app
ENV PATH="/home/appuser/app/.venv/bin:$PATH"

COPY --from=builder --chown=appuser:appuser /home/appuser/app/.venv ./.venv

# Copy only the necessary source code and scripts
COPY --chown=appuser:appuser src/ src/
COPY --chown=appuser:appuser scripts/ scripts/
COPY --chown=appuser:appuser alembic.ini .

# Copy the initial EDI schemas into the image. On first run, Docker will use this
# to populate the `edi_schemas_data` volume.
COPY --chown=appuser:appuser ./data/edi_schemas /var/edi_lens/schemas

ENTRYPOINT ["/home/appuser/app/scripts/docker-entrypoint.sh"]

# Set the default command that the entrypoint will execute with "exec $@".
# This allows us to easily override the command in docker-compose for other tasks.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]