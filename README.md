# EDI Lens Validator

EDI Lens is a full-stack web application designed for validating and managing Electronic Data Interchange (EDI) files. It features a modern, multi-tenant architecture with a powerful backend API and a responsive administrative user interface.

## Key Features

-   **Multi-Tenant Architecture**: Securely isolates data and configurations for different clients using Keycloak groups.
-   **Role-Based Access Control (RBAC)**: Fine-grained permissions for users, managed centrally in Keycloak.
-   **Automated Audit Logging**: Captures all `CREATE`, `UPDATE`, and `DELETE` operations on the database for compliance and traceability.
-   **Rich Admin UI**: A modern interface built with Refine.js and Ant Design for managing trading partners and configurations.
-   **Asynchronous Backend**: High-performance API built with Python, FastAPI, and SQLAlchemy 2.0.

---
---

## 🚀 Quick Start

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/kreddys/edi-lens.git
    cd edi-lens
    ```

2.  **Create your environment file:**
    Copy the example `.env.dev.example` file for local development.
    ```bash
    cp .env.dev.example .env.dev
    ```

3.  **Build and Start All Services:**
    This command builds the Docker images and starts all services defined in the `dev` environment.
    ```bash
    ./run.sh dev:start
    ```
    *This command can be safely re-run. It will also perform the one-time setup for Keycloak and other infrastructure.*

4.  **Access the Application:**
    -   **Admin UI**: [http://localhost:3001](http://localhost:3001)
    -   **Keycloak Admin**: [http://localhost:8080](http://localhost:8080)
    -   **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
    -   **MinIO Console**: [http://localhost:9001](http://localhost:9001)

    **Default Login Credentials:**
    -   **Superuser**: `superuser@edilens.com` / `password`
    -   **Tenant A Admin**: `admin.a@edilens.com` / `password`
    -   **Tenant B Viewer**: `viewer.b@edilens.com` / `password`

---

## Development Scripts

All common development tasks are managed via the `./run.sh` script. The script uses the format `[environment]:[action]`.

| Command                               | Description                                                              |
| :------------------------------------ | :----------------------------------------------------------------------- |
| `./run.sh dev:start`                  | Starts all services for the `dev` environment.                           |
| `./run.sh dev:stop`                   | Stops all services.                                                      |
| `./run.sh dev:clean`                  | **DANGEROUS**. Stops services and deletes all data and volumes.          |
| `./run.sh dev:logs`                   | Tails the logs for all running services.                                 |
| `./run.sh dev:migrate:make "message"` | Generates a new Alembic database migration file.                         |
| `./run.sh dev:migrate:run`            | Applies all pending database migrations.                                 |
| `./run.sh dev:test unit`              | Runs pure backend unit tests locally (no Docker required).               |
| `./run.sh dev:test integration`       | Runs backend tests requiring services (DB, Keycloak) inside Docker.      |
| `./run.sh dev:test ui`                | Runs the UI test suite inside Docker.                                    |
| `./run.sh dev:setup:keycloak`         | (Re)configures the Keycloak realm with required settings.                |

---

## 📚 Documentation

This project contains several layers of documentation to aid developers and users.

-   **Architecture Overview**: For a detailed look at the service architecture, data models, and technology stack, see the [`docs/architecture.md`](./docs/architecture.md) file.

-   **User Guide**: Explains the core application logic, such as how to configure Trading Partners. See the [`docs/user_guide.md`](./docs/user_guide.md) for details.

-   **API Documentation**: Once the application is running, a full, interactive OpenAPI (Swagger UI) is available at [http://localhost:8000/docs](http://localhost:8000/docs). This documentation is automatically generated from the backend code.

-   **Keycloak Setup Guide**: Our specific configuration for Keycloak, including the RBAC and multi-tenancy model, is detailed in the [`docs/keycloak_setup_guide.md`](./docs/keycloak_setup_guide.md) file.

-   **Architectural Decision Records (ADRs)**: Key architectural decisions are documented in the [`docs/adr`](./docs/adr) directory. These records explain *why* certain technical choices were made.

-   **Service-Specific READMEs**: Each service (`backend/`, `frontend/`) has its own `README.md` file with details about its specific technology stack and development practices.