# NiFi Template System - Developer Quick Start

**Date**: August 16, 2025  
**Author**: Assistant  

## 🚀 Quick Start Guide

### **Prerequisites**
- Development environment running: `./run.sh dev:start`
- Valid auth token for API testing
- Database access via new `db:exec` command

### **1. Verify System Status**

```bash
# Check API health
curl http://localhost:3001/api/v1/health

# Check database tables
./run.sh dev:db:exec "\\dt public.*template* public.*workflow*"

# Expected output: 4 tables
# - workflow_templates
# - template_versions  
# - template_usage
# - workflows
```

### **2. Test Template API**

```bash
# List templates (requires auth - will return 401 without token)
curl -X GET "http://localhost:3001/api/v1/workflow-templates/"

# Expected: {"detail":"Not authenticated"}
```

### **3. Create Your First Global Template**

```sql
-- Use the new db:exec command
./run.sh dev:db:exec "
INSERT INTO workflow_templates (
    template_id, name, description, category, scope, 
    maintainer, flow_definition, configuration_schema,
    is_featured, status
) VALUES (
    'global-sftp-basic-v1.0',
    'Basic SFTP File Processor',
    'Simple SFTP file monitoring and processing template',
    'BATCH',
    'GLOBAL',
    'edi-lens-platform',
    '{\"processors\": [{\"id\": \"sftp-reader\", \"type\": \"GetSFTP\"}], \"connections\": []}',
    '{\"type\": \"object\", \"properties\": {\"input_path\": {\"type\": \"string\", \"description\": \"SFTP directory to monitor\"}}}',
    true,
    'ACTIVE'
);
"
```

### **4. Verify Template Creation**

```bash
# Check template was created
./run.sh dev:db:exec "SELECT template_id, name, scope, category, status FROM workflow_templates;"
```

### **5. API Development Workflow**

#### **Current Working Endpoints**:
- `GET /api/v1/workflow-templates/` - List templates
- `GET /api/v1/workflow-templates/{id}` - Get template

#### **Next Endpoints to Implement**:
1. `POST /api/v1/workflow-templates/` - Create template
2. `POST /api/v1/workflow-templates/clone` - Clone template
3. `PUT /api/v1/workflow-templates/{id}` - Update template

#### **Implementation Pattern**:
```python
# In: backend/src/api/endpoints/workflow_templates.py

@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    template_data: TemplateCreate,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("edi:write"))
) -> TemplateResponse:
    # Validate tenant permissions
    # Create template instance  
    # Save to database
    # Return response
```

### **6. Database Operations**

#### **Common Queries**:

```bash
# List all templates
./run.sh dev:db:exec "SELECT template_id, name, scope, tenant_id FROM workflow_templates ORDER BY created_at;"

# Check template hierarchy (based_on relationships)
./run.sh dev:db:exec "SELECT template_id, name, based_on FROM workflow_templates WHERE based_on IS NOT NULL;"

# View template versions
./run.sh dev:db:exec "SELECT template_id, version, is_current FROM template_versions ORDER BY created_at;"

# Check template usage
./run.sh dev:db:exec "SELECT template_id, action, tenant_id, created_at FROM template_usage ORDER BY created_at DESC LIMIT 10;"
```

#### **Template Management**:

```bash
# Create tenant template based on global
./run.sh dev:db:exec "
INSERT INTO workflow_templates (
    template_id, name, scope, tenant_id, based_on, category,
    maintainer, flow_definition, configuration_schema, status
) VALUES (
    'tenant-a-custom-sftp-v1.0',
    'Custom SFTP Processor for Tenant A', 
    'TENANT',
    'tenant-a',
    'global-sftp-basic-v1.0',
    'BATCH',
    'tenant-a-admin',
    '{\"processors\": [{\"id\": \"custom-sftp-reader\", \"type\": \"GetSFTP\"}]}',
    '{\"type\": \"object\", \"properties\": {\"custom_field\": {\"type\": \"string\"}}}',
    'ACTIVE'
);
"

# Update template status
./run.sh dev:db:exec "UPDATE workflow_templates SET status='DEPRECATED' WHERE template_id='global-sftp-basic-v1.0';"

# Increment usage count
./run.sh dev:db:exec "UPDATE workflow_templates SET usage_count = usage_count + 1 WHERE template_id='global-sftp-basic-v1.0';"
```

### **7. Testing with Authentication**

When implementing endpoints that require auth, use existing patterns:

```bash
# Get JWT token from Keycloak (development)
# Use existing test users: superuser@edilens.com, admin.a@edilens.com

# Test authenticated endpoint
curl -X GET "http://localhost:3001/api/v1/workflow-templates/" \
  -H "Authorization: Bearer $JWT_TOKEN" \
  -H "X-Tenant-Id: tenant-a"
```

### **8. Model Validation**

Test model relationships and constraints:

```bash
# Test foreign key constraint (should fail)
./run.sh dev:db:exec "
INSERT INTO template_versions (template_id, version, flow_definition, configuration_schema, created_by)
VALUES ('non-existent-template', '1.0', '{}', '{}', 'test');
"

# Test scope constraint (should fail)  
./run.sh dev:db:exec "
INSERT INTO workflow_templates (template_id, name, scope, category, flow_definition, configuration_schema)
VALUES ('test', 'Test', 'INVALID_SCOPE', 'BATCH', '{}', '{}');
"

# Test tenant consistency constraint (should fail - TENANT scope without tenant_id)
./run.sh dev:db:exec "
INSERT INTO workflow_templates (template_id, name, scope, category, flow_definition, configuration_schema)
VALUES ('test', 'Test', 'TENANT', 'BATCH', '{}', '{}');
"
```

## 🎯 Next Development Tasks

### **Priority 1: Core CRUD Operations**
1. Implement `POST /workflow-templates/` (create)
2. Implement `PUT /workflow-templates/{id}` (update)
3. Implement `DELETE /workflow-templates/{id}` (delete)

### **Priority 2: Template Operations**
1. Implement `POST /workflow-templates/clone` (clone)
2. Implement template versioning endpoints
3. Add validation for flow_definition JSON schema

### **Priority 3: Workflow Management**
1. Create workflow instance endpoints
2. Implement workflow status management
3. Add NiFi integration points

### **Priority 4: Admin Features**
1. Template import/export
2. Usage analytics
3. Template marketplace/discovery

## 🔧 Development Tips

1. **Use db:exec for rapid prototyping** - Test queries before implementing in code
2. **Follow existing auth patterns** - Use `require_permission()` and `AuthContext`
3. **Validate early** - Check tenant permissions before database operations
4. **Test constraints** - Verify database constraints work as expected
5. **Use transactions** - Wrap multi-table operations in database transactions

## 📚 Key Files

- **Models**: `backend/src/models/workflow_template.py`
- **Schemas**: `backend/src/api/schemas.py` (search for "Template")
- **Endpoints**: `backend/src/api/endpoints/workflow_templates.py`
- **Migration**: `backend/alembic/versions/da70c11e5c83_*`
- **Documentation**: `docs/nifi-workflows/27-template-hierarchy-and-management.md`

The foundation is solid - build incrementally and test each component as you add it!