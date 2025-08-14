
# EDI Lens - Backend Service

This directory contains the clean, focused backend API for EDI processing and validation, built with Python and FastAPI.

## Overview

The backend provides core EDI processing capabilities, including:
-   **EDI Validation**: Real-time and batch validation of EDI documents
-   **EDI Parsing**: Breaking down EDI content into structured segments
-   **TA1 Generation**: Creating functional acknowledgments
-   **Schema Management**: Managing EDI schemas for validation
-   **Multi-tenancy**: Enforcing tenant isolation and role-based access control
-   **Audit Logging**: Comprehensive tracking of all operations
-   **Authentication**: JWT validation with Keycloak integration

## Core Technologies

-   **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
-   **Database ORM**: [SQLAlchemy 2.0 (Async)](https://www.sqlalchemy.org/)
-   **Database Driver**: [asyncpg](https://github.com/MagicStack/asyncpg)
-   **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
-   **Authentication**: [python-jose](https://github.com/mpdavis/python-jose) for JWT validation
-   **Testing**: [pytest](https://docs.pytest.org/) with `pytest-asyncio`

## Directory Structure

The `src` directory is organized for clarity and maintainability:

```
src/
├── api/                    # FastAPI endpoints and request/response schemas
│   ├── endpoints/          # API route definitions
│   │   ├── auth.py        # Authentication endpoints
│   │   ├── edi.py         # Consolidated EDI processing endpoints
│   │   └── schemas.py     # Schema management endpoints
│   └── schemas.py         # Pydantic models for API validation
├── core/                  # Core business logic and utilities
│   ├── acknowledgements/  # TA1 generation logic
│   ├── audit.py          # Audit logging system
│   ├── auth.py           # Authentication and authorization
│   ├── config.py         # Application configuration
│   ├── database.py       # Database connectivity
│   ├── edi_parser.py     # EDI parsing engine
│   ├── schema_manager.py # EDI schema management
│   └── storage.py        # File storage abstraction
├── models/               # SQLAlchemy ORM models
│   ├── audit_log.py     # Audit trail model
│   ├── processing_log.py # Processing history model
│   └── validation_transaction.py # Transaction tracking model
├── services/             # Business logic services
│   ├── batch_job_service.py     # Batch processing
│   ├── edi_parsing_service.py   # EDI parsing service
│   ├── edi_validation_service.py # EDI validation service
│   └── ta1_generation_service.py # TA1 acknowledgment service
└── main.py              # FastAPI application entrypoint
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
