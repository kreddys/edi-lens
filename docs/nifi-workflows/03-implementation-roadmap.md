# Implementation Roadmap

## Overview

This roadmap outlines the transition from the current monolithic backend processing to the new NiFi-based workflow architecture. The implementation is designed to be incremental, allowing for continuous development and testing.

## Phase 1: Foundation Refactoring (3-4 weeks)

### Week 1: Data Model Transformation

**Objective**: Remove trading partner/profile complexity and introduce workflow model.

**Tasks**:
- [ ] Create new database schema for workflows and templates
- [ ] Migrate existing data to new workflow model
- [ ] Create database migration scripts
- [ ] Update existing APIs to support workflow queries

**Database Changes**:
```sql
-- New tables
CREATE TABLE workflow_templates (
    template_id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    category VARCHAR NOT NULL,
    version VARCHAR DEFAULT '1.0',
    nifi_template_file VARCHAR NOT NULL,
    configuration_schema JSONB NOT NULL,
    metadata JSONB,
    status VARCHAR DEFAULT 'ACTIVE',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE workflows (
    workflow_id UUID PRIMARY KEY,
    tenant_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description TEXT,
    tags TEXT[],
    template_id VARCHAR REFERENCES workflow_templates(template_id),
    configuration JSONB NOT NULL,
    status VARCHAR DEFAULT 'ACTIVE',
    created_by VARCHAR,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Migration from existing structure
-- Convert trading_partners + profiles → workflows
-- Preserve existing processing configurations
```

**Deliverables**:
- Database migration scripts
- Data migration utilities
- Updated database documentation

### Week 2: Backend API Refactoring

**Objective**: Extract monolithic processing into focused microservice APIs.

**New Service Architecture**:
```
backend/src/services/
├── workflow_service.py          # Workflow CRUD and management
├── template_service.py          # Template management and validation
├── edi_validation_service.py    # Pure EDI validation logic (extracted)
├── acknowledgment_service.py    # TA1/999 generation (extracted)
├── transformation_service.py    # Format transformations (new)
└── batch_service.py            # Batch processing coordination (new)
```

**API Endpoints to Create**:
```python
# Template Management
GET    /api/v1/templates
GET    /api/v1/templates/{template_id}
POST   /api/v1/templates/{template_id}/validate

# Workflow Management
GET    /api/v1/workflows
POST   /api/v1/workflows
GET    /api/v1/workflows/{workflow_id}
PUT    /api/v1/workflows/{workflow_id}
DELETE /api/v1/workflows/{workflow_id}
POST   /api/v1/workflows/{workflow_id}/pause
POST   /api/v1/workflows/{workflow_id}/resume

# Processing APIs (optimized for NiFi)
POST   /api/v1/edi/validate-batch
POST   /api/v1/edi/validate-single
POST   /api/v1/edi/generate-acknowledgments
POST   /api/v1/edi/transform
```

**Tasks**:
- [ ] Extract EDI validation logic into dedicated service
- [ ] Extract TA1/999 generation into dedicated service
- [ ] Create workflow management service
- [ ] Create template management service
- [ ] Implement batch processing coordination
- [ ] Add connection pooling for NiFi interactions
- [ ] Implement caching for frequently accessed data

**Deliverables**:
- Refactored backend services
- New API endpoints
- API documentation (OpenAPI specs)
- Performance optimization utilities

### Week 3: NiFi Infrastructure Setup

**Objective**: Add NiFi to the Docker Compose environment and establish basic integration.

**Docker Compose Updates**:
```yaml
nifi:
  image: apache/nifi:1.23.2
  container_name: nifi
  environment:
    - NIFI_WEB_HTTP_HOST=0.0.0.0
    - NIFI_WEB_HTTP_PORT=8080
    - NIFI_CLUSTER_IS_NODE=false
    - SINGLE_USER_CREDENTIALS_USERNAME=admin
    - SINGLE_USER_CREDENTIALS_PASSWORD=${NIFI_ADMIN_PASSWORD}
    # Keycloak integration
    - NIFI_SECURITY_USER_OIDC_DISCOVERY_URL=${KEYCLOAK_URL}/realms/edi-lens
    - NIFI_SECURITY_USER_OIDC_CLIENT_ID=nifi
    - NIFI_SECURITY_USER_OIDC_CLIENT_SECRET=${NIFI_CLIENT_SECRET}
  volumes:
    - nifi_database_repository:/opt/nifi/nifi-current/database_repository
    - nifi_flowfile_repository:/opt/nifi/nifi-current/flowfile_repository
    - nifi_content_repository:/opt/nifi/nifi-current/content_repository
    - nifi_provenance_repository:/opt/nifi/nifi-current/provenance_repository
    - nifi_conf:/opt/nifi/nifi-current/conf
    - sftp_tenant_data:/sftp/tenants:ro
  ports:
    - "8080:8080"
  networks:
    - edi_lens_network
  depends_on:
    - keycloak
    - backend

nifi-registry:
  image: apache/nifi-registry:1.23.2
  container_name: nifi-registry
  environment:
    - NIFI_REGISTRY_WEB_HTTP_HOST=0.0.0.0
    - NIFI_REGISTRY_WEB_HTTP_PORT=18080
  volumes:
    - nifi_registry_data:/opt/nifi-registry/nifi-registry-current/database
  ports:
    - "18080:18080"
  networks:
    - edi_lens_network
```

**Tasks**:
- [ ] Add NiFi and NiFi Registry to Docker Compose
- [ ] Configure Keycloak integration for NiFi
- [ ] Set up NiFi service account in Keycloak
- [ ] Create NiFi client for backend communication
- [ ] Test basic NiFi startup and connectivity
- [ ] Configure volume mounts for SFTP access

**Deliverables**:
- Updated Docker Compose configuration
- NiFi integration utilities
- Keycloak configuration for NiFi
- Basic connectivity tests

### Week 4: Admin UI Workflow Foundation

**Objective**: Create the foundation for workflow management in the admin UI.

**New React Components**:
```typescript
// Page components
pages/workflows/
├── list.tsx              # Workflow list with filtering
├── create.tsx            # Workflow creation wizard
├── edit.tsx              # Workflow configuration editor
├── monitor.tsx           # Workflow monitoring dashboard
└── components/
    ├── WorkflowCard.tsx      # Workflow display card
    ├── TemplateSelector.tsx  # Template selection UI
    ├── ConfigurationForm.tsx # Dynamic form based on template schema
    ├── WorkflowStatus.tsx    # Status indicator
    └── TagFilter.tsx         # Tag-based filtering
```

**Tasks**:
- [ ] Remove trading partner and profile pages
- [ ] Create workflow list page with filtering by tags/template
- [ ] Create template selection interface
- [ ] Implement dynamic configuration forms based on JSON schemas
- [ ] Add workflow status management (pause/resume/delete)
- [ ] Create basic monitoring views
- [ ] Update navigation and routing

**Deliverables**:
- New workflow management pages
- Dynamic form components
- Updated UI navigation
- Workflow monitoring dashboard

## Phase 2: Core Template Development (2-3 weeks)

### Week 1: SFTP Batch Processing Template

**Objective**: Create the foundational SFTP batch processing template.

**NiFi Template Development**:
```xml
<!-- Processors in the template -->
- ListSFTP: Monitor SFTP directories
- RouteOnAttribute: Route by tenant/configuration
- FetchSFTP: Download files for processing
- InvokeHTTP: Call backend validation API
- RouteOnContent: Route based on validation results
- InvokeHTTP: Generate acknowledgments
- PutSFTP: Upload acknowledgments and responses
- UpdateAttribute: Add metadata and tracking
- PutFile: Archive processed files
```

**Backend Integration Points**:
```python
# APIs that NiFi will call
POST /api/v1/edi/validate-single
{
    "edi_content": "...",
    "tenant_id": "tenant-a",
    "workflow_id": "workflow-123",
    "validation_schema": "837.5010.X222.A1.json",
    "snip_level": 3
}

POST /api/v1/edi/generate-acknowledgments
{
    "edi_content": "...",
    "tenant_id": "tenant-a",
    "workflow_id": "workflow-123",
    "generate_ta1": true,
    "generate_999": false,
    "validation_errors": [...]
}
```

**Tasks**:
- [ ] Design NiFi flow for SFTP batch processing
- [ ] Create parameterized processors
- [ ] Implement error handling and routing
- [ ] Add monitoring and metrics collection
- [ ] Create template export and import utilities
- [ ] Test with various file types and sizes

**Deliverables**:
- SFTP batch processing NiFi template
- Template deployment utilities
- Error handling documentation
- Performance testing results

### Week 2: Real-time HTTP Processing Template

**Objective**: Create real-time HTTP processing template for synchronous transactions.

**NiFi Template Development**:
```xml
<!-- Processors in the template -->
- ListenHTTP: Accept HTTP requests
- ExtractText: Extract EDI content from request
- InvokeHTTP: Call backend validation API
- InvokeHTTP: Generate acknowledgments (if needed)
- ReplaceText: Format response
- RespondHTTP: Send synchronous response
```

**HTTP Endpoint Design**:
```http
POST /api/workflows/{workflow_id}/process
Content-Type: application/json

{
    "edi_content": "ISA*00*...",
    "request_id": "optional-client-id"
}

Response:
{
    "valid": true,
    "validation_results": [...],
    "ta1_acknowledgment": "ISA*00*...",
    "processing_time_ms": 150,
    "request_id": "optional-client-id"
}
```

**Tasks**:
- [ ] Design NiFi flow for real-time processing
- [ ] Implement synchronous response handling
- [ ] Add timeout and error management
- [ ] Create request/response logging
- [ ] Add rate limiting capabilities
- [ ] Test concurrent request handling

**Deliverables**:
- Real-time HTTP processing NiFi template
- Endpoint testing utilities
- Performance benchmarks
- Rate limiting documentation

### Week 3: Format Transformation Template

**Objective**: Create template for converting between data formats.

**Transformation Capabilities**:
- JSON → EDI (with mapping rules)
- CSV → EDI (with column mapping)
- XML → EDI (with XPath mapping)
- EDI → JSON/XML/CSV (with element extraction)

**Tasks**:
- [ ] Design transformation engine
- [ ] Create mapping rule configuration system
- [ ] Implement format conversion logic
- [ ] Add validation for input and output
- [ ] Create template with configurable transformations
- [ ] Test with various data formats and sizes

**Deliverables**:
- Format transformation NiFi template
- Mapping rule documentation
- Transformation testing utilities
- Sample mapping configurations

## Phase 3: Integration & Advanced Features (2-3 weeks)

### Week 1: End-to-End Integration Testing

**Objective**: Test complete workflow lifecycle from creation to execution.

**Test Scenarios**:
- [ ] Create SFTP batch workflow and process test files
- [ ] Create real-time workflow and send HTTP requests
- [ ] Test workflow pause/resume functionality
- [ ] Test error handling and recovery
- [ ] Test multi-tenant isolation
- [ ] Performance testing with concurrent workflows

**Tasks**:
- [ ] Create comprehensive test suite
- [ ] Set up test data and scenarios
- [ ] Implement automated testing pipeline
- [ ] Performance benchmarking
- [ ] Security testing
- [ ] Load testing

**Deliverables**:
- Automated test suite
- Performance benchmarks
- Security audit results
- Load testing reports

### Week 2: Monitoring & Observability

**Objective**: Implement comprehensive monitoring for the workflow system.

**Monitoring Stack**:
```yaml
# Prometheus metrics
- nifi_processor_events_total
- nifi_flowfile_throughput
- workflow_execution_duration
- edi_validation_success_rate
- acknowledgment_generation_rate

# Grafana dashboards
- Workflow Overview Dashboard
- Tenant Analytics Dashboard  
- System Health Dashboard
- Performance Metrics Dashboard
```

**Tasks**:
- [ ] Configure NiFi metrics export to Prometheus
- [ ] Create custom metrics for workflow execution
- [ ] Design Grafana dashboards
- [ ] Implement alerting rules
- [ ] Add logging aggregation
- [ ] Create monitoring documentation

**Deliverables**:
- Prometheus configuration
- Grafana dashboards
- Alerting rules
- Monitoring documentation

### Week 3: Advanced Workflow Features

**Objective**: Add advanced workflow capabilities and optimizations.

**Advanced Features**:
- Workflow dependencies and chaining
- Scheduled workflow execution
- Conditional processing rules
- Custom processor development
- Workflow versioning
- A/B testing capabilities

**Tasks**:
- [ ] Implement workflow scheduling
- [ ] Add conditional processing logic
- [ ] Create custom NiFi processors for EDI operations
- [ ] Implement workflow versioning
- [ ] Add workflow dependency management
- [ ] Create advanced configuration options

**Deliverables**:
- Advanced workflow features
- Custom NiFi processors
- Workflow versioning system
- Advanced configuration documentation

## Phase 4: Production Readiness (2-3 weeks)

### Week 1: Security & Performance Optimization

**Tasks**:
- [ ] Implement comprehensive security audit
- [ ] Optimize database queries and indexing
- [ ] Implement connection pooling and caching
- [ ] Add rate limiting and throttling
- [ ] Security hardening of NiFi configuration
- [ ] Performance tuning and optimization

### Week 2: Documentation & Training

**Tasks**:
- [ ] Complete user documentation
- [ ] Create administrator guides
- [ ] Develop training materials
- [ ] Record video tutorials
- [ ] Create troubleshooting guides
- [ ] Document deployment procedures

### Week 3: Deployment Preparation

**Tasks**:
- [ ] Create production deployment configurations
- [ ] Set up CI/CD pipelines
- [ ] Implement backup and recovery procedures
- [ ] Create disaster recovery plans
- [ ] Conduct final security review
- [ ] Prepare for production rollout

## Success Metrics

### Technical Metrics
- **Processing Throughput**: 99% of files processed within SLA
- **System Uptime**: 99.9% availability
- **Error Rate**: <1% processing errors
- **Response Time**: <5 seconds for real-time processing

### Business Metrics
- **Configuration Time**: Reduced workflow setup time by 80%
- **Flexibility**: Support for new EDI formats without code changes
- **Scalability**: Handle 10x current processing volume
- **User Satisfaction**: Positive feedback on workflow management UI

## Risk Mitigation

### Technical Risks
- **NiFi Learning Curve**: Provide comprehensive training and documentation
- **Performance Issues**: Implement extensive testing and monitoring
- **Integration Complexity**: Incremental implementation with rollback capability

### Operational Risks
- **Data Migration**: Thorough testing with backup/rollback procedures
- **User Adoption**: Training programs and gradual rollout
- **Production Issues**: Comprehensive monitoring and alerting

This roadmap provides a structured approach to implementing the NiFi-based workflow architecture while minimizing risks and ensuring successful adoption.