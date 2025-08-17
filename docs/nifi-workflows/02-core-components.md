# NiFi Integration Core Components and Implementation

## Component Overview

The NiFi integration consists of several core components that work together to provide a complete workflow management system:

### 1. NiFi API Clients

**Location**: `backend/src/nifi/clients/`

#### NiFiAPIClient (`nifi_client.py`)
- Process group management (create, start, stop, delete)
- Parameter context creation and management
- Template operations (upload, instantiate)
- System diagnostics and health checks
- Connection management with proper context managers

#### NiFiRegistryClient (`registry_client.py`)
- Bucket management (create, list, delete)
- Flow management (create, list, get)
- Flow version management (create, list, get)
- Registry health and information queries

### 2. Workflow Services

**Location**: `backend/src/services/`

#### NiFiWorkflowService (`nifi_workflow_service.py`)
- **Deployment**: Deploy workflows to NiFi with template instantiation
- **Lifecycle Management**: Start, stop, restart, and undeploy workflows
- **Status Monitoring**: Get detailed workflow status from NiFi
- **Template Integration**: Automatic bucket and flow creation in NiFi Registry
- **Parameter Management**: Workflow-specific configuration through parameter contexts

#### BuiltInTemplatesService (`nifi/services/built_in_templates_service.py`)
- Management of built-in workflow templates
- Template seeding into database
- Registry registration for built-in templates
- Three core templates: SFTP EDI Processor, HTTP EDI Processor, Format Converter

#### TemplateSeederService (`nifi/services/template_seeder_service.py`)
- Seeding of built-in templates into the system
- Custom template import/export functionality
- Registry registration for all templates

#### HealthService (`nifi/services/health_service.py`)
- NiFi instance health monitoring
- NiFi Registry health checks
- Comprehensive health diagnostics

### 3. Database Models

**Location**: `backend/src/models/workflow_template.py`

#### WorkflowTemplate
- Template storage with flow definitions and configuration schemas
- Version management and usage tracking
- Tenant scoping (GLOBAL vs TENANT)
- Feature tagging and documentation

#### TemplateVersion
- Version history for templates
- Flow definition snapshots
- Change tracking and deployment counts

#### TemplateUsage
- Usage analytics and audit trails
- Action tracking (DEPLOY, UPDATE, DELETE, CLONE)
- Success/failure monitoring

#### Workflow
- Running workflow instances
- Deployment information (process group ID, parameter context ID)
- Status tracking (ACTIVE, PAUSED, ERROR, DELETED)
- Configuration storage

## Implementation Details

### Template Storage Strategy

Templates are stored as JSON objects in PostgreSQL with two deployment methods:

1. **Registry Method** (Preferred): Templates stored in NiFi Registry as versioned flows
2. **XML Method** (Fallback): Templates converted to XML and uploaded directly to NiFi

### Built-in Templates

#### 1. SFTP EDI Processor Template
- Monitors SFTP directories for EDI files
- Validates content through EDI Lens backend
- Generates TA1/999 acknowledgments
- Archives processed files appropriately
- Handles errors with separate error paths

#### 2. HTTP EDI Processor Template
- HTTP endpoint for real-time EDI processing
- Synchronous validation and response
- Immediate acknowledgment generation
- Authentication and authorization validation

#### 3. Format Converter Template
- Converts between JSON/CSV/XML and EDI formats
- Configurable mapping rules
- Multiple input/output methods (SFTP, HTTP)
- Validation of converted content

### Parameter Context Management

Workflow configurations are managed through NiFi parameter contexts:
- Tenant-specific parameters
- Sensitive parameter handling
- Dynamic parameter updates
- Parameter validation and default values

### Error Handling

- **Graceful Degradation**: Falls back to mock processing if NiFi unavailable
- **Comprehensive Logging**: Detailed error logging for debugging
- **Status Updates**: Workflow status reflects deployment issues
- **Recovery Mechanisms**: Automatic retry logic for transient failures

## API Endpoints

### Workflow Management
- `POST /workflows/{workflow_id}/deploy` - Deploy workflow to NiFi
- `POST /workflows/{workflow_id}/undeploy` - Undeploy workflow from NiFi
- `POST /workflows/{workflow_id}/start` - Start deployed workflow
- `POST /workflows/{workflow_id}/stop` - Stop deployed workflow
- `POST /workflows/{workflow_id}/restart` - Restart deployed workflow
- `GET /workflows/{workflow_id}/status` - Get detailed workflow status

### Template Management
- `GET /workflow-templates` - List templates with filtering
- `GET /workflow-templates/{template_id}` - Get template details
- `POST /workflow-templates` - Create new template
- `PUT /workflow-templates/{template_id}` - Update template
- `DELETE /workflow-templates/{template_id}` - Delete template
- `POST /workflow-templates/{template_id}/clone` - Clone template to tenant

## Security Implementation

- **Authentication**: JWT-based authentication for all endpoints
- **Authorization**: Role-based access control (admin, viewer)
- **Tenant Isolation**: Complete data separation between tenants
- **Sensitive Data**: Secure handling of passwords and tokens
- **Audit Trail**: Usage tracking and operation logging

## Performance Characteristics

- **Response Time**: Sub-100ms for API operations (excluding NiFi deployment)
- **Scalability**: Horizontally scalable architecture
- **Concurrency**: Async/await implementation for high throughput
- **Resource Management**: Efficient resource utilization with connection pooling