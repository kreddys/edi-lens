
# EDI Lens - Backend Service

This directory contains the backend API for EDI processing and validation.

> **Note:** For a complete architecture overview, technology stack, and setup/run commands, please see the main [**`README.md`**](../README.md) and the [**`docs/architecture.md`**](../docs/architecture.md) file in the project root.

## Backend Directory Structure

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
