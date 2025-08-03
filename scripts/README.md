# Scripts Directory

This directory contains utility scripts for the EDI Lens project.

## Current Scripts

### 🔐 Security & Authentication

- **`create_test_jwt.py`** - Generate test JWT tokens for development and testing
  ```bash
  python3 scripts/create_test_jwt.py
  ```

### 📊 Development Tools

- **`export_for_llm.py`** - Export project structure for AI analysis
- **`queries.sql`** - Common database queries for debugging

### ⚠️ Legacy Scripts

All legacy SFTP processors have been moved to `backend/scripts/` and are accessible via the secure CLI tools in `run.sh`. No legacy scripts remain in this directory.

## Security Notes

- **Test JWT tokens are for development only** - Never use in production
- **Legacy processors lack authentication** - Use secure alternatives via `./run.sh dev:sftp:process`
- **Always use proper authentication** - All production operations require valid JWT tokens

## Usage

Most scripts should be run from the project root directory:

```bash
# From project root
cd /path/to/edi-lens
python3 scripts/create_test_jwt.py
```

For SFTP operations, use the secure CLI tools via run.sh:

```bash
# Secure SFTP operations (recommended)
./run.sh dev:sftp:process --auth-token <JWT> --tenant <TENANT> --list-partners

# Legacy operations (deprecated)
./run.sh dev:sftp:legacy --tenant <TENANT> --partner <PARTNER>
```

## Cleanup History

**Removed Files** (no longer needed):
- `manual_sftp_processor.py` - Original insecure processor
- `manual_sftp_processor_v2.py` - Duplicate (kept in backend/scripts/ only)
- `process_sftp.sh` - Old shell script approach  
- `setup-sftpgo-users.py` - Replaced by automated setup
- `secure_sftp_processor.py` - Moved to backend/scripts/

**Moved Files**:
- JWT test generator moved from `/tmp/` to permanent location

All legacy and insecure scripts have been removed or deprecated with proper warnings.