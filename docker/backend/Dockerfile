# FILE: docker/backend/Dockerfile (Simplified Approach)
FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y curl gosu && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Install poetry globally
RUN pip install --no-cache-dir poetry

# Create user (but don't switch to it yet)
RUN useradd --create-home --shell /bin/bash appuser

# Set up the app directory
WORKDIR /home/appuser/app

# Copy dependency files
COPY backend/pyproject.toml backend/poetry.lock ./

# Install dependencies as root (we'll fix permissions later)
RUN poetry config virtualenvs.in-project true && \
    poetry config virtualenvs.create true && \
    poetry install --no-root --no-interaction --no-ansi

# Copy the entire backend source code
COPY backend/ .

# Install the project itself
RUN poetry install --no-interaction --no-ansi

# Fix ownership of everything
RUN chown -R appuser:appuser /home/appuser/app

# Set the PATH environment variable
ENV PATH="/home/appuser/app/.venv/bin:$PATH"

# Ensure entrypoint script is executable
RUN chmod +x /home/appuser/app/scripts/docker-entrypoint.sh

# The ENTRYPOINT will run as root to fix permissions before stepping down
ENTRYPOINT ["/home/appuser/app/scripts/docker-entrypoint.sh"]

# The command to run after the entrypoint script has prepared the environment
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]