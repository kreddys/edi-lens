# Backend Testing Overview

This document summarises the structure of the backend automated test suites and how to run them locally.

## Test Layout

| Directory | Purpose | Notes |
| --- | --- | --- |
| `backend/tests/unit/` | Fast unit tests that exercise the service layer with mocked clients. | Tests share fixtures in `backend/tests/unit/conftest.py` and are grouped by service under `backend/tests/unit/services/`. |
| `backend/tests/integration/` | Tests that interact with live NiFi and NiFi Registry services. | Fixtures in `backend/tests/integration/conftest.py` provide real clients sourced from `.env.local`. |
| `backend/tests/e2e/` | End-to-end scenarios that orchestrate NiFi deployments and data processing. | Uses live services and shared filesystem directories mounted at `/e2e_test_files`. |

Common utilities for real clients live in `backend/tests/test_config.py`.

## Running the Test Suites

All backend test commands are wrapped by `./scripts/backend.sh` to ensure dependencies and the Poetry environment are configured correctly.

```bash
# Unit tests (mocked services)
./scripts/backend.sh test unit

# Integration tests (requires running NiFi, NiFi Registry, PostgreSQL)
./scripts/backend.sh test integration

# End-to-end tests (requires same services plus filesystem access)
./scripts/backend.sh test e2e
```

> **Tip:** Use `sudo bash scripts/maintain_codex.sh status` to confirm the NiFi services are running before launching integration or end-to-end suites.

## Test Conventions

* **Fixtures** – Async clients are provided via fixtures so that connections are properly opened and closed. Unit tests use lightweight mocks that live alongside the fixtures.
* **Helper Functions** – Flow definitions and sample payload builders are defined at the top of each test module for clarity and reuse.
* **Assertions** – Each test includes descriptive assertion messages to speed up diagnosis when a check fails.
* **Cleanup** – Integration and E2E tests perform explicit cleanup of NiFi/Registry artefacts to keep the environment tidy for subsequent runs.

## Environment Configuration

The test suites load configuration from `.env.local` when present. The file should contain the same connection details used for development, for example:

```
NIFI_URL=https://localhost:8443
NIFI_USERNAME=admin
NIFI_PASSWORD=adminadmin123
NIFI_VERIFY_SSL=false
NIFI_REGISTRY_URL=http://localhost:18080
REGISTRY_VERIFY_SSL=false
```

When `.env.local` is absent the default values from `src/core/config.py` are used.

## Troubleshooting

* **SSL or connection failures:** Ensure the NiFi and NiFi Registry containers are running and accessible on the expected ports.
* **Permission errors in E2E tests:** The tests create directories under `/e2e_test_files`. Make sure the directory exists and is writable by your user.
* **Hanging tests:** Use the verbose variants of the test commands (`./scripts/backend.sh test e2e local-verbose`) for detailed logging when diagnosing long-running operations.
