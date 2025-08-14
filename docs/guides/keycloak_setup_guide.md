# Keycloak Setup Guide

This document explains how the EDI Lens application uses Keycloak for authentication, Role-Based Access Control (RBAC), and multi-tenancy. All of this configuration is applied automatically by the `scripts/setup_keycloak_realm.py` script.

## Realm

-   **Name**: `edi-lens`
-   This is the dedicated realm for the entire application.

## Clients

Two clients are configured to represent the two main parts of our application that interact with Keycloak.

1.  **`edi-lens-backend` (Confidential Client)**
    -   **Purpose**: Represents the backend FastAPI service.
    -   **Access Type**: `Confidential`. It uses a client ID and secret to securely communicate with Keycloak (e.g., for direct token grants during integration tests).
    -   **Authentication Flow**: Service Accounts and Direct Access Grants are enabled.
    -   **Token Mappers**: It uses mappers to ensure the `audience` (`aud`) claim in the JWT is correctly set to `edi-lens-backend`, which the API validates.

2.  **`edi-lens-ui` (Public Client)**
    -   **Purpose**: Represents the frontend React application.
    -   **Access Type**: `Public`. It has no secret, as it runs in the user's browser.
    -   **Authentication Flow**: Standard OIDC Authorization Code Flow.
    -   **Redirect URIs**: Configured to allow redirects back to `http://localhost:3001/*` after login.

## Multi-Tenancy Strategy

-   **Mechanism**: Multi-tenancy is implemented using **Keycloak Groups**.
-   **Configuration**:
    -   Each tenant in our system corresponds to a Group in Keycloak (e.g., `tenant-a`, `tenant-b`).
    -   When a user is assigned to a tenant, they are added as a member of the corresponding group.
    -   A "Group Membership" token mapper is configured to include the user's groups in their access token under the `groups` claim.
-   **Enforcement**: The backend API reads the `groups` claim and the `X-Tenant-ID` header to enforce data isolation.

## Role-Based Access Control (RBAC) Model

Our permission model is built on a combination of atomic and composite roles.

### Atomic Roles

These represent the smallest possible permissions in the system.

-   `trading-partners:create`: Can create new trading partners.
-   `trading-partners:read`: Can view trading partner configurations.
-   `trading-partners:update`: Can update existing trading partners.
-   `trading-partners:delete`: Can delete trading partners.
-   `validation:run`: Can use the EDI validation endpoint.
-   `user:*`: Roles for managing users within a tenant.
-   `billing:*`: Roles for managing billing and subscriptions.
-   `superuser:*`: Special roles for global administrators.

### Composite Roles

These are user-facing roles that group multiple atomic roles together for convenience.

-   **`tenant-admin`**: Has full control over a single tenant's resources (all `trading-partners:*`, `user:*`, `billing:*`, and `validation:run` permissions).
-   **`tenant-editor`**: Can manage trading partners but not users or billing.
-   **`tenant-viewer`**: Has read-only access (`trading-partners:read`, `validation:run`).
-   **`superuser`**: A global role with permissions that bypass tenant boundaries.

### Default Users

The setup script creates the following users for immediate testing:

| Username                | Password   | Roles                               | Groups           | Description                                    |
| :---------------------- | :--------- | :---------------------------------- | :--------------- | :--------------------------------------------- |
| `superuser@edilens.com` | `password` | `superuser`, `tenant-admin`         | `tenant-a`, `tenant-b` | Full global and tenant-level access.           |
| `admin.a@edilens.com`   | `password` | Inherits `tenant-admin` via group | `tenant-a`         | An administrator for Tenant A only.            |
| `viewer.b@edilens.com`  | `password` | Inherits `tenant-viewer` via group  | `tenant-b`         | A read-only user for Tenant B only.            |