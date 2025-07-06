# ADR 0002: Multi-Tenancy Implementation Strategy

-   **Status**: Accepted
-   **Date**: 2025-07-06

## Context

The application must support multiple tenants, ensuring that data created by one tenant is completely inaccessible to another, except by authorized superusers. The implementation must be secure, efficient, and consistently applied across the backend.

## Decision

We will implement multi-tenancy using a combination of a `tenant_id` column on database tables and JWT claims for enforcement at the API layer.

1.  **Database Layer**: Every tenant-specific table (e.g., `trading_partners`, `partner_profiles`) will have a non-nullable `tenant_id` (String) column. This column will be indexed for performance.
2.  **Authentication Layer**: The user's JWT, issued by Keycloak, will contain a `groups` claim, which is a list of tenant IDs the user belongs to (e.g., `["tenant-a", "tenant-c"]`).
3.  **API Layer**: Every API request for a tenant-specific resource must include an `X-Tenant-ID` header.
4.  **Enforcement**: A FastAPI dependency (`require_permission`) will perform two checks on every request:
    -   It verifies that the `X-Tenant-ID` from the header is present in the user's JWT `groups` claim. If not, the request is rejected with a `403 Forbidden` error.
    -   All subsequent database queries for that request must be filtered by this validated `tenant_id`.

## Rationale

-   **Security**: This approach provides strong data isolation. Since every query is filtered by `tenant_id` at the repository level, it's nearly impossible to accidentally leak data between tenants. A user cannot even attempt to query for data outside their authorized tenants.
-   **Explicitness**: Requiring the `X-Tenant-ID` header makes the tenant context explicit for every API call, which simplifies debugging and makes the API's behavior clear.
-   **Performance**: Indexing the `tenant_id` column ensures that queries remain performant even as the number of tenants and the volume of data grows.
-   **Flexibility**: This model allows a single user to be a member of multiple tenants and switch between them seamlessly on the frontend by changing the `X-Tenant-ID` header.

## Consequences

-   **Developer Discipline**: Developers must remember to include the `tenant_id` filter in all new repository methods for tenant-specific data.
-   **Schema Overhead**: A `tenant_id` column must be added to all relevant models.
-   **Frontend Responsibility**: The client application is responsible for managing the currently selected tenant and sending the correct `X-Tenant-ID` header with each request.