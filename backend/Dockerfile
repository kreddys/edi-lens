# Stage 1: Builder stage with all dependencies
# <<< THE FIX IS HERE >>>
# We set the final WORKDIR *before* installing anything.
FROM python:3.11-slim AS builder

# Set the final working directory that will be used in the app stage
WORKDIR /home/appuser/app

# Install poetry
RUN pip install --no-cache-dir poetry

# Copy only dependency definition files to leverage Docker cache
COPY pyproject.toml poetry.lock ./

# Install all dependencies (including dev) into a virtual environment
# Now, poetry will create the venv with the correct /home/appuser/app path.
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-root


# Stage 2: Final application stage
FROM python:3.11-slim

# Set a non-root user for security
RUN useradd --create-home --shell /bin/bash appuser
USER appuser
# Use the same WORKDIR as the builder stage
WORKDIR /home/appuser/app

# Set the PYTHONPATH to include the root of our app
ENV PYTHONPATH=/home/appuser/app
# Add the venv to the PATH
ENV PATH="/home/appuser/app/.venv/bin:$PATH"

# Copy the virtual environment from the builder stage
# The source path now matches the destination WORKDIR
COPY --from=builder --chown=appuser:appuser /home/appuser/app/.venv ./.venv

# Copy the application source code
COPY --chown=appuser:appuser ./src ./src
COPY --chown=appuser:appuser ./tests ./tests

# Expose the port the app will run on
EXPOSE 8000

# Set the default command to run when the container starts.
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]