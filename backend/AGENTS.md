# Backend Contribution Guide

Welcome to the EDI Lens backend. This service is a FastAPI application that orchestrates NiFi workflows and their corresponding NiFi Registry artefacts. Code under this directory follows a domain-oriented structure with a clear split between API clients, domain services, orchestration workflows, and FastAPI routing layers. Review `README_ARCHITECTURE.md` for a complete architecture map before touching the codebase.

## Local Development Environment

* **Python toolchain**: managed with [Poetry](https://python-poetry.org/). The Codex setup script automatically runs `poetry install --with dev` inside the backend virtual environment; avoid re-running it manually unless you are developing outside the Codex automation.
* **Entry point**: FastAPI app and supporting services live under `src/`. Clients that call NiFi and Registry APIs reside in `src/clients`, domain services in `src/services`, and workflow orchestration in `src/services/workflow_orchestrator.py`.
* **Environment configuration**: default runtime settings are defined via `.env` (optional) and test fixtures in `tests/env`. When `.env.local` is absent, local test runs fall back to localhost defaults that assume Docker services on standard ports (NiFi 8443, Registry 18080, Backend 8000, Postgres 5432).

## Running the Application

Use the helper script in the repository root:

```bash
./scripts/backend.sh start   # Start backend + dependencies via Docker Compose (dev mode)
./scripts/backend.sh stop    # Stop all backend-related containers
./scripts/backend.sh shell   # Open an interactive shell inside the backend container
```

The script ensures Docker/Compose are available, builds containers, and waits for NiFi, the Registry, and Postgres to report ready/healthy states before returning.

## Testing Workflow

All backend tests should be executed through the management script to ensure environment variables are populated consistently.

### Unit Tests

```bash
./scripts/backend.sh test unit
```

* Runs `pytest` with the `unit` marker against `tests/unit/` in the local Poetry virtual environment.
* Requires local dependencies to be installed (`poetry install --with dev`).

### Integration Tests

```bash
./scripts/backend.sh test integration [local|docker]
```

* **Local mode** (default) connects to NiFi and NiFi Registry endpoints using localhost URLs derived from `.env.local` or the fallback values declared in `tests/env/test.local.env`.
* **Docker mode** executes tests inside the running backend container; the script will ensure the container is up and dependencies are installed.

When running locally, verify that NiFi and Registry services are reachable (e.g., via `https://localhost:8443/nifi/` and `http://localhost:18080/nifi-registry-api/config`). The script prints warnings if the endpoints are unreachable but continues so you can decide whether to start the services first.

### End-to-End (E2E) Tests

E2E suites are triggered with `./scripts/backend.sh test e2e <mode>` if/when they are added. Modes include `local`, `local-verbose`, `docker`, and `docker-verbose`. Always prefer verbose modes when debugging data plane issues.

### Additional Tooling

* `./scripts/backend.sh lint` runs the configured lint pipeline (Black, Ruff, mypy, etc.).
* `./scripts/backend.sh format` applies auto-formatting with Black and isort.
* `./scripts/backend.sh test:watch` leverages `pytest-watch` for rapid feedback while editing unit tests.

## Useful References

* **Architecture**: `backend/README_ARCHITECTURE.md` documents module boundaries and responsibilities across clients, services, and orchestrators.
* **Configuration samples**: `backend/tests/env/` contains `.env` templates for local and Docker-based test runs.
* **Pyproject**: `backend/pyproject.toml` defines dependencies, Poetry scripts, and pytest configuration (including markers such as `unit` and `integration`).

Please keep these conventions in mind when modifying backend code or tests to maintain predictable workflows across the team.
