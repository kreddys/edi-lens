# Detailed Implementation Phases

## Overview

This document outlines the incremental development approach for transitioning to the NiFi workflow architecture. Each phase is designed to be small, testable, and independently deployable to minimize risk and ensure continuous system functionality.

## Development Philosophy

### Small Incremental Steps
- **Maximum 3-5 days per step**
- **Single responsibility per step**
- **Backward compatibility maintained**
- **Comprehensive tests before proceeding**

### Testing at Each Step
- **Unit tests** for new code
- **Integration tests** for API changes
- **Regression tests** to ensure no breakage
- **Manual validation** of key workflows

### Deployment Strategy
- **Feature flags** for new functionality
- **Parallel running** of old and new systems
- **Gradual migration** with rollback capability
- **Zero downtime** transitions

## Phase 1: Core EDI API Extraction (3-4 weeks)

**Goal**: Extract core EDI operations into focused APIs while maintaining current functionality.

### Step 1.1: Realtime EDI Validation API (3-4 days)
**Objective**: Create realtime validation endpoint for synchronous HTTP workflows.

#### Implementation
```python
# NEW: src/api/endpoints/edi_validation.py
@router.post("/api/v1/edi/validate-realtime")
async def validate_realtime_edi(
    request: RealtimeEDIValidationRequest,
    auth: AuthContext = Depends(require_service_auth)
):
    """Validate EDI document with immediate synchronous response."""
    pass

# NEW: src/api/schemas/edi_schemas.py
class RealtimeEDIValidationRequest(BaseModel):
    edi_content: str
    tenant_id: str
    workflow_id: str
    validation_schema: str
    snip_level: int = 3
    generate_ta1: bool = False
    generate_999: bool = False

class RealtimeEDIValidationResponse(BaseModel):
    valid: bool
    validation_results: List[ValidationFinding]
    processing_time_ms: int
    schema_used: str
    snip_level_used: int
    ta1_content: Optional[str] = None
    workflow_id: str
    processed_at: datetime
```

#### Testing Strategy

Use the project's `run.sh` script for all testing:

```bash
# Start development environment (auto-reloads on code changes)
./run.sh dev:start

# Unit tests (fast, no Docker needed)
./run.sh dev:test unit tests/api/test_edi_validation.py -v

# Integration tests (with Docker stack)
./run.sh dev:test integration tests/api/test_edi_validation.py -v

# E2E tests (full system with Keycloak + SFTPGo setup)
./run.sh dev:test e2e tests/api/test_edi_validation.py -v

# Run all API tests
./run.sh dev:test integration tests/api/ -v

# Run specific test class
./run.sh dev:test integration tests/api/test_edi_validation.py::TestRealtimeEDIValidation -v
```

**Development Notes:**
- The backend auto-reloads in dev mode - no need to restart containers after code changes
- Only restart containers when changing Docker configs or environment variables
- Check container health: `docker ps` or `./run.sh dev:logs backend`

**Test Types:**
- **Unit tests**: Fast, isolated tests using mocks (marked with `@pytest.mark.unit`)
- **Integration tests**: Test against real Docker services (marked with `@pytest.mark.integration`) 
- **E2E tests**: Full system tests with authentication and SFTP processing (marked with `@pytest.mark.e2e`)

**Test Coverage:**
```python
# tests/api/test_edi_validation.py
class TestRealtimeEDIValidation:
    async def test_valid_edi_document(self):
        """Test validation of valid EDI document."""
        
    async def test_invalid_edi_document(self):
        """Test validation of invalid EDI document."""
        
    async def test_missing_schema(self):
        """Test error handling for missing schema."""
        
    async def test_service_authentication(self):
        """Test service account authentication."""
        
    async def test_tenant_isolation(self):
        """Test tenant data isolation."""
```

#### Acceptance Criteria
- [ ] New endpoint returns same validation results as current system
- [ ] Service authentication works correctly
- [ ] All existing validation tests pass
- [ ] Performance within 10% of current system
- [ ] Proper error handling and logging

### Step 1.2: TA1 Generation API (2-3 days)
**Objective**: Extract TA1 generation into dedicated endpoint.

#### Implementation
```python
# NEW: src/api/endpoints/edi_acknowledgments.py
@router.post("/api/v1/edi/generate-ta1")
async def generate_ta1_acknowledgment(
    request: TA1GenerationRequest,
    auth: AuthContext = Depends(require_service_auth)
):
    """Generate TA1 acknowledgment for EDI interchange."""
    pass

class TA1GenerationRequest(BaseModel):
    edi_content: str
    tenant_id: str
    workflow_id: str
    validation_errors: List[ValidationFinding] = []
    file_name: Optional[str] = None

class TA1GenerationResponse(BaseModel):
    ta1_content: Optional[str]
    acknowledgment_status: str  # A, E, R
    error_code: Optional[str]
    processing_time_ms: int
```

#### Testing Strategy
```python
# tests/api/test_edi_acknowledgments.py
class TestTA1Generation:
    async def test_generate_ta1_for_valid_edi(self):
        """Test TA1 generation for valid EDI."""
        
    async def test_generate_ta1_for_invalid_edi(self):
        """Test TA1 generation with validation errors."""
        
    async def test_ta1_structure_compliance(self):
        """Test TA1 structure meets EDI standards."""
```

#### Acceptance Criteria
- [ ] TA1 generation matches current system output
- [ ] Handles all error scenarios correctly
- [ ] Generated TA1 passes EDI structure validation
- [ ] Performance acceptable for batch processing

### Step 1.3: 999 Generation API (2-3 days)
**Objective**: Extract 999 generation into dedicated endpoint.

#### Implementation
```python
@router.post("/api/v1/edi/generate-999")
async def generate_999_acknowledgment(
    request: Ack999GenerationRequest,
    auth: AuthContext = Depends(require_service_auth)
):
    """Generate 999 functional acknowledgment."""
    pass
```

#### Testing Strategy
- Similar to TA1 generation with 999-specific test cases
- Validation against 999 EDI structure requirements

### Step 1.4: Batch Validation API with Job Queue (4-5 days)
**Objective**: Create batch validation endpoint with asynchronous job processing and webhook callbacks.

#### Implementation
```python
@router.post("/api/v1/edi/validate-batch")
async def validate_batch_edi(
    request: BatchEDIValidationRequest,
    auth: AuthContext = Depends(require_service_auth)
):
    """Process single EDI file asynchronously with webhook callback."""
    pass

class BatchEDIValidationRequest(BaseModel):
    edi_content: str              # ONE file only
    tenant_id: str
    workflow_id: str
    validation_schema: str
    snip_level: int = 3
    file_name: Optional[str] = None
    callback_url: str             # Webhook endpoint for completion
    generate_ta1: bool = False
    generate_999: bool = False

class BatchEDIValidationResponse(BaseModel):
    job_id: str                   # Job tracking ID
    status: str                   # QUEUED, PROCESSING, COMPLETED, FAILED
    workflow_id: str
    file_name: Optional[str]
    estimated_processing_time_ms: int
    created_at: datetime

# NEW: Job status endpoint
@router.get("/api/v1/edi/jobs/{job_id}")
async def get_batch_job_status(job_id: str):
    """Get status of batch processing job."""
    pass

# NEW: Webhook payload structure
class BatchJobCompletionWebhook(BaseModel):
    job_id: str
    status: str
    workflow_id: str
    file_name: Optional[str]
    results: Optional[RealtimeEDIValidationResponse] = None
    error_message: Optional[str] = None
```

#### Job Queue Implementation
```python
# NEW: src/services/batch_job_service.py
class BatchJobService:
    def __init__(self, db: AsyncSession, job_queue: JobQueue):
        self.db = db
        self.job_queue = job_queue
    
    async def create_batch_job(self, request: BatchEDIValidationRequest) -> str:
        """Create batch processing job and queue it."""
        job_id = str(uuid.uuid4())
        
        # Store job in database
        await self.store_job(job_id, request)
        
        # Queue for processing
        await self.job_queue.enqueue(job_id, request)
        
        return job_id
    
    async def process_batch_job(self, job_id: str):
        """Process batch job and send webhook callback."""
        pass
```

#### Testing Strategy
```python
class TestBatchEDIValidation:
    async def test_batch_job_creation(self):
        """Test batch job creation and queuing."""
        
    async def test_batch_job_processing(self):
        """Test asynchronous batch job processing."""
        
    async def test_webhook_callback(self):
        """Test webhook callback on job completion."""
        
    async def test_job_status_tracking(self):
        """Test job status endpoint."""
        
    async def test_multiple_files_from_sftp(self):
        """Test 5 files from SFTP create 5 separate jobs."""
```

### Step 1.5: Service Authentication (2-3 days)
**Objective**: Implement service-to-service authentication for NiFi.

#### Implementation
```python
# NEW: src/core/service_auth.py
class ServiceAuthManager:
    def __init__(self, keycloak_client):
        self.keycloak_client = keycloak_client
    
    async def get_service_token(self) -> str:
        """Get service account token for NiFi."""
        pass
    
    async def validate_service_token(self, token: str) -> bool:
        """Validate incoming service token."""
        pass

# NEW: src/core/auth.py addition
async def require_service_auth(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db)
) -> ServiceContext:
    """Dependency for service-to-service authentication."""
    pass
```

#### Testing Strategy
```python
class TestServiceAuthentication:
    async def test_service_token_generation(self):
        """Test service token generation."""
        
    async def test_service_token_validation(self):
        """Test service token validation."""
        
    async def test_expired_token_handling(self):
        """Test expired token handling."""
        
    async def test_invalid_token_rejection(self):
        """Test invalid token rejection."""
```

### Step 1.6: Integration Testing (2-3 days)
**Objective**: Comprehensive testing of all new APIs together.

#### Testing Strategy
```python
class TestEDIAPIIntegration:
    async def test_complete_edi_processing_workflow(self):
        """Test complete workflow: validate → generate TA1 → generate 999."""
        
    async def test_batch_processing_workflow(self):
        """Test batch validation with acknowledgment generation."""
        
    async def test_error_handling_across_apis(self):
        """Test error propagation and handling."""
        
    async def test_performance_under_load(self):
        """Test API performance under concurrent load."""
```

## Phase 2: Workflow Model Implementation (2-3 weeks)

**Goal**: Implement new workflow-based data model while maintaining current functionality.

### Step 2.1: Workflow Templates Model (3-4 days)
**Objective**: Create workflow template data model and basic CRUD operations.

#### Implementation
```python
# NEW: src/models/workflow_template.py
class WorkflowTemplate(Base):
    __tablename__ = 'workflow_templates'
    
    template_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    category = Column(String, nullable=False)  # BATCH, REALTIME, TRANSFORMATION
    flow_definition = Column(JSON, nullable=False)
    configuration_schema = Column(JSON, nullable=False)
    deployment_method = Column(String, default='registry')
    nifi_registry_flow_id = Column(String)
    status = Column(String, default='ACTIVE')
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

# NEW: src/repositories/workflow_template_repo.py
class WorkflowTemplateRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, template: WorkflowTemplateCreate) -> WorkflowTemplate:
        """Create a new workflow template."""
        pass
    
    async def get_by_id(self, template_id: str) -> Optional[WorkflowTemplate]:
        """Get template by ID."""
        pass
    
    async def list_by_category(self, category: str) -> List[WorkflowTemplate]:
        """List templates by category."""
        pass
```

#### Database Migration
```python
# alembic/versions/xxx_add_workflow_templates.py
def upgrade():
    op.create_table(
        'workflow_templates',
        sa.Column('template_id', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('flow_definition', sa.JSON(), nullable=False),
        sa.Column('configuration_schema', sa.JSON(), nullable=False),
        sa.Column('deployment_method', sa.String(), nullable=True),
        sa.Column('nifi_registry_flow_id', sa.String(), nullable=True),
        sa.Column('status', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('template_id')
    )
```

#### Testing Strategy
```python
class TestWorkflowTemplateModel:
    async def test_create_workflow_template(self):
        """Test creating a workflow template."""
        
    async def test_template_validation(self):
        """Test template schema validation."""
        
    async def test_template_retrieval(self):
        """Test template retrieval operations."""
        
    async def test_template_listing(self):
        """Test template listing and filtering."""
```

### Step 2.2: Workflow Model (3-4 days)
**Objective**: Create workflow instance data model.

#### Implementation
```python
# NEW: src/models/workflow.py
class Workflow(Base):
    __tablename__ = 'workflows'
    
    workflow_id = Column(String, primary_key=True)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    tags = Column(ARRAY(String))
    template_id = Column(String, ForeignKey('workflow_templates.template_id'))
    configuration = Column(JSON, nullable=False)
    status = Column(String, default='ACTIVE')
    nifi_process_group_id = Column(String)
    created_by = Column(String)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    
    template = relationship("WorkflowTemplate")
```

#### Testing Strategy
```python
class TestWorkflowModel:
    async def test_create_workflow(self):
        """Test creating a workflow instance."""
        
    async def test_workflow_template_relationship(self):
        """Test workflow-template relationship."""
        
    async def test_workflow_configuration_validation(self):
        """Test configuration validation against template schema."""
        
    async def test_tenant_isolation(self):
        """Test tenant data isolation."""
```

### Step 2.3: Template Management API (3-4 days)
**Objective**: Create API for managing workflow templates.

#### Implementation
```python
# NEW: src/api/endpoints/templates.py
@router.get("/api/v1/templates")
async def list_templates(
    category: Optional[str] = None,
    auth: AuthContext = Depends(require_permission("templates:read"))
):
    """List available workflow templates."""
    pass

@router.get("/api/v1/templates/{template_id}")
async def get_template(
    template_id: str,
    auth: AuthContext = Depends(require_permission("templates:read"))
):
    """Get template details including configuration schema."""
    pass

@router.post("/api/v1/templates/{template_id}/validate")
async def validate_template_configuration(
    template_id: str,
    configuration: dict,
    auth: AuthContext = Depends(require_permission("templates:read"))
):
    """Validate configuration against template schema."""
    pass
```

### Step 2.4: Workflow Management API (4-5 days)
**Objective**: Create API for managing workflow instances.

#### Implementation
```python
# NEW: src/api/endpoints/workflows.py
@router.get("/api/v1/workflows")
async def list_workflows(
    tenant_id: str,
    tags: Optional[List[str]] = Query(None),
    template_id: Optional[str] = None,
    auth: AuthContext = Depends(require_permission("workflows:read"))
):
    """List workflows for tenant with filtering."""
    pass

@router.post("/api/v1/workflows")
async def create_workflow(
    workflow: WorkflowCreateRequest,
    auth: AuthContext = Depends(require_permission("workflows:create"))
):
    """Create a new workflow instance."""
    pass

@router.put("/api/v1/workflows/{workflow_id}")
async def update_workflow(
    workflow_id: str,
    updates: WorkflowUpdateRequest,
    auth: AuthContext = Depends(require_permission("workflows:update"))
):
    """Update workflow configuration."""
    pass
```

### Step 2.5: Data Migration Strategy (2-3 days)
**Objective**: Plan and test migration from trading partners to workflows.

#### Migration Script
```python
# scripts/migrate_partners_to_workflows.py
async def migrate_trading_partners_to_workflows():
    """
    Migrate existing trading partners and profiles to workflow model.
    """
    # 1. Create default SFTP template if not exists
    # 2. For each trading partner with profiles:
    #    - Create workflow for each profile
    #    - Map profile configuration to workflow configuration
    #    - Preserve tenant isolation
    # 3. Validate migration results
    # 4. Create rollback script
    pass
```

#### Testing Strategy
```python
class TestDataMigration:
    async def test_migration_accuracy(self):
        """Test migration preserves all data correctly."""
        
    async def test_migration_rollback(self):
        """Test migration rollback functionality."""
        
    async def test_migrated_workflow_functionality(self):
        """Test migrated workflows work correctly."""
```

## Phase 3: NiFi Integration Layer (2-3 weeks)

**Goal**: Implement NiFi integration without disrupting current functionality.

### Step 3.1: NiFi Client Implementation (3-4 days)
**Objective**: Create NiFi API client for basic operations.

#### Implementation
```python
# NEW: src/services/nifi_client.py
class NiFiClient:
    def __init__(self, base_url: str, service_token: str):
        self.base_url = base_url
        self.service_token = service_token
    
    async def create_process_group(self, name: str) -> Dict:
        """Create a new process group in NiFi."""
        pass
    
    async def upload_template(self, template_xml: str) -> str:
        """Upload template to NiFi."""
        pass
    
    async def start_process_group(self, process_group_id: str):
        """Start processors in process group."""
        pass
    
    async def get_process_group_status(self, process_group_id: str) -> Dict:
        """Get process group status."""
        pass
```

#### Testing Strategy
```python
class TestNiFiClient:
    async def test_nifi_connection(self):
        """Test connection to NiFi instance."""
        
    async def test_process_group_creation(self):
        """Test process group creation."""
        
    async def test_template_operations(self):
        """Test template upload and instantiation."""
        
    async def test_error_handling(self):
        """Test NiFi error handling."""
```

### Step 3.2: Template Deployment Service (4-5 days)
**Objective**: Implement workflow deployment to NiFi.

#### Implementation
```python
# NEW: src/services/workflow_deployment.py
class WorkflowDeploymentService:
    def __init__(self, nifi_client: NiFiClient, template_manager):
        self.nifi_client = nifi_client
        self.template_manager = template_manager
    
    async def deploy_workflow(self, workflow: Workflow) -> str:
        """Deploy workflow to NiFi and return process group ID."""
        pass
    
    async def update_workflow_deployment(self, workflow: Workflow):
        """Update existing workflow deployment."""
        pass
    
    async def remove_workflow_deployment(self, workflow: Workflow):
        """Remove workflow from NiFi."""
        pass
```

### Step 3.3: Docker Integration (2-3 days)
**Objective**: Add NiFi to Docker Compose and configure networking.

#### Implementation
```yaml
# docker/docker-compose.yml additions
services:
  nifi:
    image: apache/nifi:1.23.2
    container_name: nifi
    environment:
      - NIFI_WEB_HTTP_HOST=0.0.0.0
      - NIFI_WEB_HTTP_PORT=8080
      - SINGLE_USER_CREDENTIALS_USERNAME=admin
      - SINGLE_USER_CREDENTIALS_PASSWORD=${NIFI_ADMIN_PASSWORD}
    ports:
      - "8080:8080"
    volumes:
      - nifi_data:/opt/nifi/nifi-current/conf
      - sftp_tenant_data:/sftp/tenants:ro
    networks:
      - edi_lens_network
    depends_on:
      - backend
      - keycloak

  nifi-registry:
    image: apache/nifi-registry:1.23.2
    container_name: nifi-registry
    environment:
      - NIFI_REGISTRY_WEB_HTTP_HOST=0.0.0.0
      - NIFI_REGISTRY_WEB_HTTP_PORT=18080
    ports:
      - "18080:18080"
    networks:
      - edi_lens_network
```

#### Testing Strategy
```python
class TestNiFiDockerIntegration:
    def test_nifi_startup(self):
        """Test NiFi container starts correctly."""
        
    def test_nifi_backend_connectivity(self):
        """Test NiFi can connect to backend APIs."""
        
    def test_nifi_sftp_access(self):
        """Test NiFi can access SFTP volumes."""
```

### Step 3.4: Basic Template Creation (3-4 days)
**Objective**: Create first working NiFi template for SFTP processing.

#### Implementation
- Create JSON template definition for SFTP EDI processing
- Implement template conversion to NiFi format
- Test end-to-end workflow deployment

### Step 3.5: Monitoring Integration (2-3 days)
**Objective**: Add monitoring for NiFi workflows.

#### Implementation
```python
# NEW: src/services/workflow_monitoring.py
class WorkflowMonitoringService:
    def __init__(self, nifi_client: NiFiClient):
        self.nifi_client = nifi_client
    
    async def get_workflow_metrics(self, workflow_id: str) -> Dict:
        """Get workflow processing metrics."""
        pass
    
    async def get_workflow_status(self, workflow_id: str) -> str:
        """Get current workflow status."""
        pass
```

## Phase 4: Legacy Code Cleanup (1-2 weeks)

**Goal**: Remove obsolete code after new system is proven stable.

### Step 4.1: Feature Flag Implementation (2-3 days)
**Objective**: Implement feature flags for gradual migration.

#### Implementation
```python
# NEW: src/core/feature_flags.py
class FeatureFlags:
    def __init__(self):
        self.flags = {
            'use_workflow_api': os.getenv('USE_WORKFLOW_API', 'false').lower() == 'true',
            'use_nifi_processing': os.getenv('USE_NIFI_PROCESSING', 'false').lower() == 'true',
            'legacy_trading_partners': os.getenv('LEGACY_TRADING_PARTNERS', 'true').lower() == 'true'
        }
    
    def is_enabled(self, flag_name: str) -> bool:
        return self.flags.get(flag_name, False)
```

### Step 4.2: Parallel System Testing (3-4 days)
**Objective**: Run old and new systems in parallel for validation.

### Step 4.3: Legacy Code Removal (2-3 days)
**Objective**: Remove obsolete code after validation.

#### Files to Remove
- AI/LLM components
- Old SFTP processing
- Trading partner model (after migration)
- Unused test files

### Step 4.4: Documentation Update (2-3 days)
**Objective**: Update all documentation to reflect new architecture.

## Testing Strategy Overview

### Automated Testing
- **Unit tests**: 95%+ coverage for new code
- **Integration tests**: API endpoint testing
- **E2E tests**: Complete workflow testing
- **Performance tests**: Load and stress testing

### Manual Testing
- **User acceptance testing**: Admin UI workflows
- **Integration testing**: NiFi workflow execution
- **Security testing**: Authentication and authorization
- **Data validation**: Migration accuracy

### Continuous Integration
```yaml
# .github/workflows/test.yml
name: Test Suite
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: poetry install
      - name: Run unit tests
        run: poetry run pytest tests/unit/ -v
      - name: Run integration tests
        run: poetry run pytest tests/integration/ -v
      - name: Run API tests
        run: poetry run pytest tests/api/ -v
```

## Risk Mitigation

### Technical Risks
1. **NiFi integration complexity**: Start with simple templates, gradual complexity
2. **Performance degradation**: Benchmark each step, optimize bottlenecks
3. **Data loss during migration**: Comprehensive backup and rollback procedures

### Process Risks
1. **Scope creep**: Strict adherence to phase boundaries
2. **Testing gaps**: Mandatory test coverage before proceeding
3. **Timeline pressure**: Buffer time built into each phase

### Mitigation Strategies
1. **Feature flags**: Enable/disable new functionality
2. **Parallel systems**: Run old and new systems simultaneously
3. **Incremental rollout**: Phase-by-phase deployment
4. **Rollback procedures**: Quick revert capability at each step

This detailed phase approach ensures we can make steady progress while maintaining system stability and having comprehensive tests at each step.