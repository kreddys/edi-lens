# EDI Lens Guides

This directory contains comprehensive guides for setting up and using EDI Lens.

## 📚 Available Guides

### Authentication & Security

- **[Authentication Configuration Guide](authentication_configuration_guide.md)** 
  - Complete guide to the standardized authentication system
  - Environment-driven configuration
  - Token generation and usage
  - Troubleshooting authentication issues
  - **👈 Start here for authentication setup**

- **[Keycloak Setup Guide](keycloak_setup_guide.md)**
  - Keycloak realm and client configuration
  - Role-based access control (RBAC)
  - Multi-tenancy setup
  - Default users and permissions

### User Documentation

- **[User Guide](user_guide.md)**
  - End-user documentation for using EDI Lens
  - UI walkthrough and features

## 🚀 Quick Start

For setting up authentication from scratch:

1. **Read** the [Authentication Configuration Guide](authentication_configuration_guide.md)
2. **Configure** your `.env.dev` file based on the examples
3. **Run** the Keycloak setup script: `python backend/scripts/setup_keycloak_realm.py`
4. **Test** your configuration: `./scripts/test_auth_config.sh`

## 🔗 Related Documentation

- [Architecture Documentation](../architecture.md) - System architecture overview
- [NiFi Workflows](../nifi-workflows/) - NiFi workflow implementation guides
- [API Documentation](../nifi-workflows/04-api-specifications.md) - API specifications

---

> **Note**: The authentication configuration has been recently standardized and cleaned up. All authentication-related documentation reflects the current environment-driven approach.