# Keycloak Setup Guide

This document explains how the EDI Lens application uses Keycloak for authentication, Role-Based Access Control (RBAC), and multi-tenancy. All of this configuration is applied automatically by the `backend/scripts/setup_keycloak_realm.py` script.

> **Note**: For the complete authentication configuration guide including token generation and environment setup, see [Authentication Configuration Guide](authentication_configuration_guide.md).

## Realm

-   **Name**: `edi-lens`
-   This is the dedicated realm for the entire application.

## Clients

Four clients are configured to represent the different parts of our application that interact with Keycloak:

### Main Application Clients

1.  **`edi-lens-backend` (Confidential Client)**
    -   **Purpose**: Represents the backend FastAPI service
    -   **Access Type**: `Confidential` - Uses client ID and secret for service authentication
    -   **Authentication Flow**: Service Accounts and Direct Access Grants enabled
    -   **Token Mappers**: Configured to set `audience` (`aud`) claim to `edi-lens-backend`
    -   **Environment Variable**: `KEYCLOAK_BACKEND_CLIENT_ID`

2.  **`edi-lens-ui` (Public Client)**
    -   **Purpose**: Represents the frontend React application
    -   **Access Type**: `Public` - No secret required (browser-based)
    -   **Authentication Flow**: Standard OIDC Authorization Code Flow
    -   **Redirect URIs**: Configured for `http://localhost:3001/*` and production URLs
    -   **Environment Variable**: `KEYCLOAK_UI_CLIENT_ID`

### Service Account Clients

3.  **`nifi-service` (Service Account)**
    -   **Purpose**: Apache NiFi processors for EDI workflow automation
    -   **Access Type**: `Confidential` - Service account with client credentials
    -   **Authentication Flow**: Client Credentials Grant only
    -   **Roles**: `edi:process`, `edi:validate`, `edi:generate-acknowledgments`, `validation:run`, `schemas:read`
    -   **Environment Variable**: `KEYCLOAK_NIFI_CLIENT_ID`

4.  **`sftpgo` (Confidential Client)**
    -   **Purpose**: SFTPGo admin interface SSO authentication
    -   **Access Type**: `Confidential` - OIDC client with secret
    -   **Authentication Flow**: Authorization Code Flow
    -   **Redirect URIs**: Configured for SFTPGo admin interface
    -   **Environment Variable**: `KEYCLOAK_SFTPGO_CLIENT_ID`

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

#### EDI Processing Roles
-   `validation:run`: Can run EDI validation
-   `schemas:read`: Can read EDI schemas
-   `schemas:create`: Can create EDI schemas
-   `schemas:update`: Can update EDI schemas

#### NiFi Service Roles
-   `edi:process`: Can process EDI content (for NiFi service accounts)
-   `edi:validate`: Can validate EDI content (for NiFi service accounts)
-   `edi:generate-acknowledgments`: Can generate EDI acknowledgments (for NiFi service accounts)

#### User Management Roles
-   `admin`: Administrator role
-   `workflow:read`: Can read workflow templates and configurations
-   `workflow:write`: Can create and modify workflows
-   `workflow:admin`: Advanced workflow management

### Composite Roles

These are user-facing roles that group multiple atomic roles together for convenience.

-   **`tenant-admin`**: Full control over a single tenant (`validation:run`, `schemas:read/create/update`, `workflow:read/write`, `admin`)
-   **`tenant-viewer`**: Read-only access to a tenant's data (`schemas:read`, `workflow:read`)
-   **`superuser`**: Global administrator with access across all tenants (includes `tenant-admin` + `workflow:admin`)

### Default Users

The setup script creates the following users for immediate testing:

| Username                | Password   | Roles                               | Groups           | Description                                    |
| :---------------------- | :--------- | :---------------------------------- | :--------------- | :--------------------------------------------- |
| `superuser@edilens.com` | `password` | `superuser`                         | `tenant-a`, `tenant-b` | Full global and tenant-level access           |
| `admin.a@edilens.com`   | `password` | Inherits `tenant-admin` via group   | `tenant-a`       | Administrator for Tenant A only               |
| `viewer.b@edilens.com`  | `password` | Inherits `tenant-viewer` via group  | `tenant-b`       | Read-only user for Tenant B only              |

## Environment-Driven Configuration

All Keycloak client configuration is now managed through environment variables:

```bash
# Required environment variables (from .env.dev)
KEYCLOAK_REALM=edi-lens
KEYCLOAK_BACKEND_CLIENT_ID=edi-lens-backend
KEYCLOAK_BACKEND_CLIENT_SECRET=this-is-a-very-secret-key-change-it
KEYCLOAK_UI_CLIENT_ID=edi-lens-ui
KEYCLOAK_NIFI_CLIENT_ID=nifi-service
KEYCLOAK_NIFI_CLIENT_SECRET=nifi-service-secret
KEYCLOAK_SFTPGO_CLIENT_ID=sftpgo
KEYCLOAK_SFTPGO_CLIENT_SECRET=a_very_secure_sftpgo_secret_change_it
```

## Setup Instructions

### Automatic Setup

1. **Configure Environment**:
   ```bash
   # Copy and configure environment file
   cp .env.dev.example .env.dev
   # Edit .env.dev with your specific configuration
   ```

2. **Run Setup Script**:
   ```bash
   python backend/scripts/setup_keycloak_realm.py
   ```

### What the Setup Script Does

The setup script automatically:
- Creates the `edi-lens` realm
- Configures all clients using environment variables
- Creates atomic and composite roles
- Sets up tenant groups (`tenant-a`, `tenant-b`)
- Creates default test users
- Assigns appropriate roles to service accounts
- Configures token mappers for proper JWT audience claims

### Service Account Configuration

The setup script automatically configures service account roles:

**NiFi Service Account** (`nifi-service`):
- Receives roles: `edi:process`, `edi:validate`, `edi:generate-acknowledgments`, `validation:run`, `schemas:read`
- Used for: EDI processing workflows, validation, TA1 generation

**Backend Service Account** (`edi-lens-backend`):
- Used for: Internal service-to-service communication

## Token Generation

After setup, you can generate tokens using the standardized script:

```bash
# Service account tokens
python scripts/get_auth_token.py --service nifi-service
python scripts/get_auth_token.py --service backend

# User tokens
python scripts/get_auth_token.py --user admin.a@edilens.com --password password --tenant tenant-a
```

For complete token generation documentation, see [Authentication Configuration Guide](authentication_configuration_guide.md).

## Troubleshooting

### Common Issues

1. **Client Creation Fails**:
   - Verify environment variables are set correctly
   - Check Keycloak is running and accessible

2. **Service Account Roles Missing**:
   - Re-run the setup script
   - Verify the service account user was created

3. **Token Generation Fails**:
   - Check client secrets match environment configuration
   - Verify realm and client names are correct

### Debug Commands

```bash
# Check setup script output
python backend/scripts/setup_keycloak_realm.py

# Test token generation
python scripts/test_auth_config.sh
```