# ADR 0001: Choice of Keycloak for Authentication and Authorization

-   **Status**: Accepted
-   **Date**: 2025-07-06

## Context

The EDI Lens application requires a robust, secure, and flexible system for managing user authentication and authorization. Key requirements include support for multi-tenancy, fine-grained Role-Based Access Control (RBAC), and the ability to integrate with future enterprise identity systems.

## Decision

We have decided to use **Keycloak** as the central Identity and Access Management (IAM) provider for the entire application.

## Rationale

1.  **Open Source and Self-Hosted**: Keycloak is a mature, open-source solution that can be self-hosted within our Docker environment. This gives us full control over our user data and avoids vendor lock-in and the recurring costs associated with third-party identity providers like Auth0 or Okta.

2.  **Excellent Multi-Tenancy Support**: Keycloak's concept of "Groups" maps perfectly to our multi-tenancy requirement. We can assign users to one or more tenant groups (e.g., `tenant-a`, `tenant-b`), and this information is embedded directly into the user's JWT as a `groups` claim. The backend API uses this claim to enforce strict data isolation.

3.  **Advanced RBAC Capabilities**: Keycloak provides a powerful system for defining realm-level roles (e.g., `partner:create`, `validation:run`) and composite roles (e.g., `tenant-admin`). This allows us to create a sophisticated permission model that can be managed through the Keycloak UI without requiring code changes.

4.  **Standard Protocols**: Keycloak is built on industry standards like OAuth 2.0 and OpenID Connect (OIDC), ensuring broad compatibility with frontend libraries (`keycloak-js`) and backend validation libraries.

5.  **Scalability and Federation**: It is designed for enterprise use and supports identity federation, allowing us to connect to external SAML or OIDC providers in the future if a client requires it.

## Consequences

-   **Operational Overhead**: We are responsible for managing, backing up, and securing the Keycloak service and its database.
-   **Learning Curve**: There is a learning curve associated with configuring Keycloak realms, clients, and roles effectively.
-   **Automated Setup**: To mitigate the configuration complexity, a Python script (`scripts/setup_keycloak_realm.py`) has been created to programmatically set up the realm, ensuring a consistent and reproducible environment.