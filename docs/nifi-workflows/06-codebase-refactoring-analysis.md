# Codebase Refactoring Analysis

## Executive Summary

After thorough analysis of the current EDI Lens codebase, I've identified significant opportunities for cleanup and refactoring to support the new NiFi workflow architecture. The current code shows evidence of evolution and experimentation, with some obsolete components and unnecessary complexity that should be removed.

## Current Code Structure Analysis

### Backend Structure
```
backend/src/
├── agents/                    # 🔴 AI/LLM components - REMOVE
├── api/endpoints/             # ✅ Keep - Core API functionality
├── core/                      # ✅ Keep - Core EDI operations
│   ├── acknowledgements/      # ✅ Keep - TA1/999 generation
│   ├── airflow/              # 🔴 Empty directory - REMOVE
│   └── processing/           # 🔴 Empty directory - REMOVE
├── models/                    # 🟡 Refactor - Remove trading partner model
├── repositories/              # ✅ Keep - Data access layer
├── services/                  # 🟡 Refactor - Simplify and extract APIs
└── utils/                     # 🟡 Cleanup - Remove LLM utilities
```

## Components to Remove (Ruthless Cleanup)

### 1. AI/LLM Integration Components 🔴 REMOVE ENTIRELY
**Why**: Not part of core EDI processing, adds complexity without value for workflow architecture

**Files to Delete**:
- `src/agents/` (entire directory)
  - `crews.py` - CrewAI integration
  - `llm.py` - LLM client
  - `models.py` - AI response models
  - `prompt_utils.py` - Prompt management
  - `tools/` - RAG and schema lookup tools
- `src/services/enrichment_service.py` - AI-powered schema enrichment
- `src/utils/llm_output_parser.py` - LLM response parsing
- `src/api/endpoints/enrichment.py` - AI enrichment API
- `src/api/endpoints/knowledge.py` - Knowledge base API

**Tests to Delete**:
- `tests/agents/` (entire directory - 8 test files)
- `tests/api/test_enrichment_api.py`
- `tests/api/test_knowledge_api.py`

### 2. Empty/Unused Directories 🔴 REMOVE
**Files to Delete**:
- `src/core/airflow/` (empty)
- `src/core/processing/` (empty)  
- `src/processing/` (empty)

### 3. Trading Partner/Profile Model 🔴 REMOVE
**Why**: Being replaced by workflow model

**Files to Refactor/Remove**:
- `src/models/trading_partner.py` - Replace with workflow model
- `src/models/partner_profile.py` - Replace with workflow configuration
- `src/api/endpoints/trading_partners.py` - Replace with workflow API
- `src/repositories/trading_partner.py` - Replace with workflow repository
- `src/core/profile_matcher.py` - Simplify to workflow matcher

**Database Tables to Drop**:
```sql
-- These will be replaced by workflow tables
DROP TABLE partner_profiles;
DROP TABLE trading_partners;
```

### 4. SFTP-Specific Processing 🔴 REMOVE
**Why**: Moving to NiFi workflow orchestration

**Files to Remove**:
- `src/services/sftp_file_processor.py` - Replace with NiFi templates
- `src/services/sftp_webhook_processor.py` - NiFi will handle webhooks
- `src/services/sftp_user_manager.py` - Maintain in separate service
- `src/api/endpoints/sftp.py` - Replace with workflow management

## Components to Keep and Refactor

### 1. Core EDI Operations ✅ EXTRACT TO FOCUSED APIs

**Keep These Files** (core business logic):
- `src/core/edi_parser.py` - EDI parsing engine
- `src/core/schema_manager.py` - Schema loading and validation
- `src/core/acknowledgements/` - TA1/999 generation
- `src/services/validation_service.py` - EDI validation logic

**Refactor Strategy**:
Extract into focused microservice APIs for NiFi consumption:
```python
# New API structure
/api/v1/edi/validate-single     # Single EDI validation
/api/v1/edi/validate-batch      # Batch EDI validation
/api/v1/edi/generate-ta1        # TA1 generation
/api/v1/edi/generate-999        # 999 generation
/api/v1/edi/parse              # EDI parsing
/api/v1/schemas/validate        # Schema validation
```

### 2. Authentication & Authorization ✅ KEEP
**Files to Keep**:
- `src/core/auth.py` - JWT validation and RBAC
- `src/api/endpoints/auth.py` - Authentication endpoints
- `src/core/config.py` - Configuration management

### 3. Database & Storage ✅ KEEP
**Files to Keep**:
- `src/core/database.py` - Database connection
- `src/core/storage.py` - MinIO/S3 integration
- `src/models/audit_log.py` - Audit logging
- `src/models/processing_log.py` - Processing history
- `src/models/validation_transaction.py` - Transaction tracking

## New Components to Add

### 1. Workflow Management
```python
# New files to create
src/models/workflow.py           # Workflow entity
src/models/workflow_template.py  # Template entity
src/services/workflow_service.py # Workflow CRUD
src/services/template_service.py # Template management
src/api/endpoints/workflows.py   # Workflow API
src/api/endpoints/templates.py   # Template API
```

### 2. NiFi Integration
```python
# New files to create
src/services/nifi_client.py         # NiFi API client
src/services/nifi_deployment.py     # Workflow deployment
src/services/template_converter.py  # JSON to NiFi conversion
```

### 3. Batch Processing Coordination
```python
# New files to create
src/services/batch_service.py       # Batch job management
src/models/batch_job.py             # Batch job tracking
```

## Detailed Refactoring Plan

### Phase 1: Remove Obsolete Code (Week 1)
```bash
# Delete AI/LLM components
rm -rf src/agents/
rm src/services/enrichment_service.py
rm src/utils/llm_output_parser.py
rm src/api/endpoints/enrichment.py
rm src/api/endpoints/knowledge.py
rm -rf tests/agents/
rm tests/api/test_enrichment_api.py
rm tests/api/test_knowledge_api.py

# Delete empty directories
rm -rf src/core/airflow/
rm -rf src/core/processing/
rm -rf src/processing/

# Delete SFTP processors (will be replaced by NiFi)
rm src/services/sftp_file_processor.py
rm src/services/sftp_webhook_processor.py
rm src/api/endpoints/sftp.py
```

### Phase 2: Extract Core EDI APIs (Week 2)
Transform monolithic validation service into focused APIs:

**Before** (current):
```python
# Single large validation endpoint
@router.post("/validate")
async def validate_edi_endpoint(request: ValidationRequest):
    # Handles everything: parsing, validation, TA1/999 generation
```

**After** (focused APIs):
```python
# Separate focused endpoints for NiFi
@router.post("/api/v1/edi/validate-single")
async def validate_single_edi(request: SingleValidationRequest):
    # Only validates EDI content

@router.post("/api/v1/edi/generate-acknowledgments") 
async def generate_acknowledgments(request: AcknowledgmentRequest):
    # Only generates TA1/999

@router.post("/api/v1/edi/parse")
async def parse_edi(request: ParseRequest):
    # Only parses EDI structure
```

### Phase 3: Implement Workflow Model (Week 3)
Replace trading partner/profile with workflow model:

**Database Migration**:
```sql
-- Create new workflow tables
CREATE TABLE workflow_templates (
    template_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    flow_definition JSONB NOT NULL,
    configuration_schema JSONB NOT NULL,
    -- ... other fields
);

CREATE TABLE workflows (
    workflow_id UUID PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    template_id VARCHAR REFERENCES workflow_templates(template_id),
    configuration JSONB NOT NULL,
    -- ... other fields
);

-- Migrate existing data
INSERT INTO workflows (tenant_id, name, template_id, configuration)
SELECT 
    tp.tenant_id,
    CONCAT(tp.name, ' - ', pp.name),
    'sftp-edi-processor-v1.0',
    jsonb_build_object(
        'validation', jsonb_build_object(
            'schema', pp.validation_schema_name,
            'snip_level', pp.snip_level
        ),
        'acknowledgments', jsonb_build_object(
            'generate_ta1', pp.generate_ta1,
            'generate_999', pp.generate_999
        )
    )
FROM trading_partners tp
JOIN partner_profiles pp ON tp.id = pp.partner_id
WHERE tp.sftp_enabled = true;

-- Drop old tables
DROP TABLE partner_profiles;
DROP TABLE trading_partners;
```

## Test Cleanup Strategy

### Tests to Keep
- `tests/core/test_edi_parser*.py` (14 files) - Core EDI functionality
- `tests/core/test_ta1_generator.py` - TA1 generation
- `tests/core/test_schema_manager.py` - Schema management
- `tests/api/test_authorization.py` - Auth testing
- `tests/services/test_validation_service.py` - Validation logic

### Tests to Remove
- `tests/agents/` (8 files) - AI/LLM functionality
- `tests/api/test_enrichment_api.py` - AI API
- `tests/api/test_knowledge_api.py` - Knowledge API
- `tests/core/test_enhanced_partner_profile.py` - Old profile model
- `tests/e2e/test_onboarding_e2e.py` - Partner onboarding workflow

### New Tests to Create
- `tests/services/test_workflow_service.py` - Workflow management
- `tests/services/test_template_service.py` - Template management
- `tests/api/test_workflows_api.py` - Workflow API
- `tests/integration/test_nifi_integration.py` - NiFi integration

## Configuration Cleanup

### Remove from pyproject.toml
```toml
# Remove AI/LLM dependencies
crewai = "^0.83.5"
langchain = "^0.3.7"
langchain-community = "^0.3.5"
langchain-openai = "^0.2.8"
openai = "^1.54.3"
lightrag = "^0.0.0b7"
```

### Keep Essential Dependencies
```toml
# Core dependencies to keep
fastapi = "^0.115.4"
sqlalchemy = "^2.0.36"
alembic = "^1.13.3"
pydantic = "^2.10.2"
python-keycloak = "^4.6.1"
boto3 = "^1.35.62"  # For MinIO/S3
```

## Expected Benefits

### Code Reduction
- **Remove ~3,000 lines** of AI/LLM code
- **Remove ~2,000 lines** of trading partner/profile code  
- **Remove ~1,500 lines** of SFTP processing code
- **Remove ~2,500 lines** of related tests

**Total: ~9,000 lines removed** (~40% code reduction)

### Architectural Benefits
1. **Clear separation of concerns**: Backend focuses on EDI operations, NiFi handles orchestration
2. **Simplified data model**: Single workflow concept vs trading partners + profiles
3. **API-first design**: Focused endpoints optimized for NiFi consumption
4. **Reduced dependencies**: No AI/ML libraries, simpler deployment
5. **Better testability**: Focused components with clear responsibilities

### Maintenance Benefits
1. **Easier onboarding**: Less code to understand
2. **Faster development**: Focused codebase
3. **Better performance**: Removed unused functionality
4. **Cleaner documentation**: No obsolete concepts

This refactoring plan provides a clean foundation for the NiFi workflow architecture while maintaining all essential EDI processing capabilities.

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"id": "1", "content": "Analyze current backend code structure and identify refactoring needs", "status": "completed"}, {"id": "2", "content": "Review existing database models and identify cleanup opportunities", "status": "completed"}, {"id": "3", "content": "Analyze current API endpoints and service architecture", "status": "completed"}, {"id": "4", "content": "Identify obsolete code, tests, and documentation to remove", "status": "completed"}, {"id": "5", "content": "Document refactoring plan for clean, service-driven architecture", "status": "completed"}]