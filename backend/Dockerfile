# Stage 1: Build stage with production dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy only dependency definition files
COPY pyproject.toml poetry.lock ./

# Install production dependencies into a virtual environment
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root --without dev

# Stage 2: Build stage with all dependencies (for testing)
FROM python:3.11-slim AS test_builder

WORKDIR /app

# Install poetry
RUN pip install poetry

# Copy only dependency definition files
COPY pyproject.toml poetry.lock ./

# Install all dependencies (including dev) into a virtual environment
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root

# Stage 3: Final application stage
FROM python:3.11-slim

# Set the PYTHONPATH to include the root of our app
# This allows imports like 'from src.core import ...' to work correctly everywhere.
ENV PYTHONPATH=/app

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Copy the application source code
COPY ./src ./src

# Copy the entrypoint script and make it executable
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["entrypoint.sh"]

# The port the app will run on
EXPOSE 8000

# Set the default command to run when the container starts
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Stage 4: Test stage
FROM python:3.11-slim AS test

WORKDIR /app

# Set the PYTHONPATH to include the root of our app
ENV PYTHONPATH=/app

# Copy the virtual environment with all dependencies from the test_builder stage
COPY --from=test_builder /app/.venv ./.venv

# Copy the application source code and tests
COPY ./src ./src
COPY ./tests ./tests

# Copy the entrypoint script and make it executable
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

# Set the entrypoint for tests (can be overridden)
ENTRYPOINT ["/app/.venv/bin/pytest"]
