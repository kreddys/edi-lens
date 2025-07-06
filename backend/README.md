
# EDI Lens - Backend Service

This directory contains the backend API for the EDI Lens application, built with Python and FastAPI.

## Overview

The backend is responsible for all core business logic, including:
-   API endpoints for all CRUD operations.
-   EDI parsing and validation logic.
-   Enforcing multi-tenancy and role-based access control (RBAC).
-   Connecting to the PostgreSQL database via SQLAlchemy.
-   Generating automated audit logs for data modifications.
-   Validating JWTs issued by Keycloak.

## Core Technologies

-   **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
-   **Database ORM**: [SQLAlchemy 2.0 (Async)](https://www.sqlalchemy.org/)
-   **Database Driver**: [asyncpg](https://github.com/MagicStack/asyncpg)
-   **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
-   **Authentication**: [python-jose](https://github.com/mpdavis/python-jose) for JWT validation
-   **Testing**: [pytest](https://docs.pytest.org/) with `pytest-asyncio`

## Directory Structure

The `src` directory is organized to promote separation of concerns.

```
src/
├── api/              # FastAPI endpoints and Pydantic schemas
│   ├── endpoints/    # Routers for different resources (e.g., trading_partners.py)
│   └── schemas.py    # Pydantic models for request/response validation
├── core/             # Core application logic and utilities
│   ├── audit.py      # SQLAlchemy event listeners for audit logging
│   ├── auth.py       # Authentication and permission dependency logic
│   ├── config.py     # Application settings and logging setup
│   ├── database.py   # Database engine and session management
│   └── ...
├── models/           # SQLAlchemy ORM models (database table definitions)
├── repositories/     # Data access layer, separates DB queries from API logic
└── main.py           # Main FastAPI application entrypoint
```

## Running Backend-Specific Tasks

All backend tasks should be run through the main `run_app.sh` script in the project root to ensure the service is running inside the correct Docker environment.

-   **Run all tests (unit and integration):**
    ```bash
    ./scripts/run_app.sh test:backend
    ./scripts/run_app.sh test:integration
    ```

-   **Generate a new database migration:**
    ```bash
    ./scripts/run_app.sh migrate:make "Your descriptive message"
    ```
    *After running, inspect the generated file in `backend/alembic/versions/`.*

-   **Apply database migrations:**
    ```bash
    ./scripts/run_app.sh migrate:run
    ```
