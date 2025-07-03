# Stage 1: Build stage with dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy only dependency definition files
COPY pyproject.toml poetry.lock ./

# Install dependencies into a virtual environment
# --no-root: don't install the project itself, only dependencies
# --without dev: skip development dependencies (FIXED from --no-dev)
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root --without dev

# Stage 2: Final application stage
FROM python:3.11-slim

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Activate the virtual environment
ENV PATH="/app/.venv/bin:$PATH"

# Copy the application source code
COPY ./src ./src

# The port the app will run on
EXPOSE 8000

# The command to run the application (will be overridden by docker-compose for dev)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]