### 3. Admin-UI `README.md`

Create a new file at `admin-ui/README.md`.

```markdown
# EDI Lens - Admin UI

This directory contains the frontend admin interface for the EDI Lens application.

## Overview

The Admin UI is a Single-Page Application (SPA) built to provide a rich, interactive experience for managing application data.

-   **Framework**: [React](https://reactjs.org/) with [Vite](https://vitejs.dev/)
-   **UI/App Framework**: [Refine.js](https://refine.dev/) (handles data fetching, routing, and state management)
-   **Component Library**: [Ant Design](https://ant.design/)
-   **Authentication**: Integration with Keycloak via `keycloak-js`.

## Directory Structure

The `src` directory is organized by feature and domain.

```
src/
├── components/     # Reusable React components (e.g., Layout)
├── pages/          # Top-level views for each resource (e.g., Trading Partners)
├── providers/      # Refine providers (auth, data, theme, accessControl)
├── utils/          # Utility functions and singleton instances (logger, keycloak)
├── App.tsx         # Main application component with routing
└── main.tsx        # Application entrypoint and Keycloak initialization
```

## Environment Variables

The application requires a `.env` file in the **project root**. The UI uses the following variables from that file:

```dotenv
# The public-facing URL of your Keycloak instance
VITE_KEYCLOAK_URL=http://localhost:8080
# The Keycloak realm name
VITE_KEYCLOAK_REALM=edi-lens
# The public client ID for the UI
VITE_KEYCLOAK_CLIENT_ID=edi-lens-ui
# The base URL of the backend API
VITE_API_URL=http://localhost:8000/api/v1
```

## Local Development

The UI is managed by the main `docker-compose.yml` and `scripts/run_app.sh` script in the project root. It's recommended to run it this way.

However, if you need to run the UI standalone (e.g., for faster HMR), you can run the following commands from within the `admin-ui` directory, assuming the backend and Keycloak services are already running via Docker.

```bash
# In the admin-ui/ directory
npm install
npm run dev
```