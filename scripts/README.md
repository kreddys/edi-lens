# Utility Scripts Directory

This directory contains utility scripts for the EDI Lens project.

## Current Scripts

### 🔐 Security & Authentication

- **`auth_token_helper.py`** - Generate JWT tokens from Keycloak for testing
  ```bash
  # Generate service token for NiFi
  python3 scripts/auth_token_helper.py --service nifi-service
  
  # Generate user token for admin user  
  python3 scripts/auth_token_helper.py --user admin.a@edilens.com --password password --tenant tenant-a
  ```

### 🧪 API Testing

- **`test_api.py`** - Generic script for testing backend APIs with proper authentication
  ```bash
  # List workflow templates
  python3 scripts/test_api.py
  
  # Get a specific template
  python3 scripts/test_api.py -e /api/v1/workflow-templates/global-batch-edi-processor-v1.0
  
  # List schemas
  python3 scripts/test_api.py -e /api/v1/schemas
  
  # Create a new schema (example)
  python3 scripts/test_api.py -m POST -e /api/v1/schemas -d '{"name":"test","content":"{}"}'
  ```

### 📊 Development Tools

- **`export_for_llm.py`** - Export project structure for AI analysis
- **`queries.sql`** - Common database queries for debugging

## Security Notes

- **Test JWT tokens are for development only** - Never use in production
- **Always use proper authentication** - All production operations require valid JWT tokens

## Usage

Most scripts should be run from the project root directory:

```bash
# From project root
cd /path/to/edi-lens

# Generate a service token
python3 scripts/auth_token_helper.py --service backend

# Test an API endpoint
python3 scripts/test_api.py -e /api/v1/workflows
```

## Script Details

### `auth_token_helper.py`

This script generates JWT tokens from Keycloak for testing EDI validation endpoints and service authentication.
Supports both user tokens and service account tokens.

### `test_api.py`

This script provides a generic way to test any backend API endpoint with proper authentication.
It handles token generation and API requests automatically.

### `test_auth_config.sh`

This script demonstrates the standardized, environment-driven authentication configuration.
It tests token generation and basic API endpoints to verify the authentication setup.

## Best Practices

1. **Always run from project root** - Scripts expect to be run from the project root directory
2. **Use proper authentication** - Never bypass authentication in production
3. **Test in development first** - Use these scripts to verify functionality before deploying
4. **Keep credentials secure** - Never commit real credentials to version control