# Missing API Specifications

**Date**: August 16, 2025  
**Author**: Assistant  
**Status**: Detailed API Gap Analysis  

## Overview

This document details the specific API endpoints and functionality that are missing from our current workflow implementation. These APIs are required by the specifications in `04-api-specifications.md` but are not yet implemented.

## 🚨 Critical Missing APIs

### 1. Workflow Execution Endpoints

#### Real-time Processing Endpoint
```http
POST /api/workflows/{workflow_id}/process
Content-Type: application/json
Authorization: Bearer {jwt_token}
X-Tenant-ID: {tenant_id}

{
    "edi_content": "ISA*00*          *00*          *ZZ*...",
    "request_id": "client-request-123",
    "processing_options": {
        "generate_ta1": true,
        "generate_999": false,
        "validate_syntax": true
    }
}
```

**Expected Response:**
```json
{
    "valid": true,
    "validation_results": [
        {
            "level": "warning",
            "code": "W001", 
            "message": "Optional element missing",
            "location": {
                "segment": "NM1",
                "element": "04"
            }
        }
    ],
    "ta1_acknowledgment": "ISA*00*          *00*          *ZZ*...",
    "ack999_acknowledgment": null,
    "processing_time_ms": 180,
    "request_id": "client-request-123",
    "workflow_id": "workflow-123"
}
```

**Current Status**: ❌ **Not Implemented**
**Implementation Required**: 
- Workflow execution logic
- NiFi process group triggering
- Real-time EDI processing pipeline
- Response formatting

---

#### Workflow Status Endpoint
```http
GET /api/v1/workflows/{workflow_id}/status
Authorization: Bearer {jwt_token}
X-Tenant-ID: {tenant_id}
```

**Expected Response:**
```json
{
    "workflow_id": "workflow-123",
    "status": "ACTIVE",
    "nifi_status": "RUNNING",
    "deployment_status": "DEPLOYED",
    "last_execution": "2025-08-16T10:30:00Z",
    "execution_count": 1547,
    "error_count": 12,
    "success_rate": 0.992,
    "process_group_id": "process-group-uuid",
    "parameter_context_id": "param-context-uuid",
    "flow_version": 3,
    "health_check": {
        "status": "healthy",
        "last_check": "2025-08-16T10:35:00Z",
        "issues": []
    }
}
```

**Current Status**: ❌ **Not Implemented**
**Current Limitation**: Basic workflow model exists but no NiFi integration

---

### 2. Advanced Workflow Control APIs

#### Dedicated Control Endpoints
```http
# Currently we only have generic actions endpoint
POST /api/v1/workflows/{workflow_id}/actions
{
    "action": "pause",
    "parameters": {}
}

# Missing dedicated endpoints:
POST /api/v1/workflows/{workflow_id}/pause
POST /api/v1/workflows/{workflow_id}/resume  
POST /api/v1/workflows/{workflow_id}/restart
POST /api/v1/workflows/{workflow_id}/stop
```

**Expected Response for Control Operations:**
```json
{
    "workflow_id": "workflow-uuid",
    "action": "pause",
    "status": "PAUSED",
    "nifi_status": "STOPPED",
    "timestamp": "2025-08-16T10:30:00Z",
    "message": "Workflow paused successfully"
}
```

**Current Status**: 🔶 **Partially Implemented** 
- Generic actions endpoint exists
- Missing dedicated endpoints
- No actual NiFi control integration

---

### 3. Workflow Metrics & Monitoring APIs

#### Workflow Metrics Endpoint
```http
GET /api/v1/workflows/{workflow_id}/metrics
Authorization: Bearer {jwt_token}
X-Tenant-ID: {tenant_id}

# Query Parameters:
?from=2025-08-15T00:00:00Z
&to=2025-08-16T00:00:00Z
&granularity=hour
```

**Expected Response:**
```json
{
    "workflow_id": "workflow-123",
    "period": {
        "from": "2025-08-15T00:00:00Z",
        "to": "2025-08-16T00:00:00Z",
        "granularity": "hour"
    },
    "metrics": {
        "files_processed": 150,
        "processing_time_avg_ms": 2500,
        "processing_time_p95_ms": 4200,
        "processing_time_p99_ms": 6800,
        "success_rate": 0.987,
        "error_rate": 0.013,
        "throughput_files_per_hour": 6.25,
        "acknowledgments_generated": {
            "ta1_count": 150,
            "999_count": 5
        }
    },
    "time_series": [
        {
            "timestamp": "2025-08-15T10:00:00Z",
            "files_processed": 12,
            "avg_processing_time_ms": 2300,
            "errors": 0
        }
    ]
}
```

**Current Status**: ❌ **Not Implemented**
**Implementation Required**:
- Metrics collection system
- Time-series data storage
- Aggregation logic
- Performance monitoring

---

#### Workflow Logs Endpoint
```http
GET /api/v1/workflows/{workflow_id}/logs
Authorization: Bearer {jwt_token}
X-Tenant-ID: {tenant_id}

# Query Parameters:
?level=INFO
&from=2025-08-16T10:00:00Z
&limit=100
&offset=0
```

**Expected Response:**
```json
{
    "workflow_id": "workflow-123",
    "logs": [
        {
            "timestamp": "2025-08-16T10:30:15.123Z",
            "level": "INFO",
            "message": "Processing EDI file: claims_20250816_001.edi",
            "component": "SFTP_Processor",
            "processor_id": "processor-uuid",
            "file_name": "claims_20250816_001.edi",
            "metadata": {
                "file_size": 125643,
                "processing_time_ms": 1800
            }
        },
        {
            "timestamp": "2025-08-16T10:30:17.456Z", 
            "level": "WARN",
            "message": "Validation warning: Optional element missing",
            "component": "EDI_Validator",
            "processor_id": "validator-uuid",
            "file_name": "claims_20250816_001.edi",
            "metadata": {
                "warning_code": "W001",
                "segment": "NM1",
                "element": "04"
            }
        }
    ],
    "total": 1247,
    "limit": 100,
    "offset": 0,
    "has_more": true
}
```

**Current Status**: ❌ **Not Implemented**
**Implementation Required**:
- Centralized logging system
- Log aggregation from NiFi
- Log filtering and pagination
- Structured log storage

---

### 4. Template Configuration Validation API

#### Configuration Validation Endpoint
```http
POST /api/v1/workflow-templates/{template_id}/validate
Content-Type: application/json
Authorization: Bearer {jwt_token}
X-Tenant-ID: {tenant_id}

{
    "configuration": {
        "input_path": "/sftp/tenants/tenant-a/claims/in/",
        "file_patterns": ["*.edi", "*.x12"],
        "validation": {
            "schema": "837.5010.X222.A1.json",
            "snip_level": 3
        },
        "acknowledgments": {
            "generate_ta1": true,
            "generate_999": false
        },
        "output": {
            "success_path": "/sftp/tenants/tenant-a/claims/out/",
            "error_path": "/sftp/tenants/tenant-a/claims/error/"
        }
    }
}
```

**Expected Response (Valid Configuration):**
```json
{
    "valid": true,
    "errors": [],
    "warnings": [
        {
            "field": "acknowledgments.generate_999",
            "message": "999 acknowledgments are recommended for production workflows",
            "severity": "low"
        }
    ],
    "recommendations": [
        {
            "field": "output.archive_path", 
            "message": "Consider adding archive path for processed files",
            "suggestion": "/sftp/tenants/tenant-a/claims/archive/"
        }
    ]
}
```

**Expected Response (Invalid Configuration):**
```json
{
    "valid": false,
    "errors": [
        {
            "field": "input_path",
            "message": "Path must start with /sftp/tenants/{tenant_id}/",
            "current_value": "/invalid/path/",
            "expected_pattern": "^/sftp/tenants/tenant-a/.+/$"
        },
        {
            "field": "validation.schema",
            "message": "Schema file does not exist",
            "current_value": "nonexistent.json",
            "available_schemas": ["837.5010.X222.A1.json", "835.5010.X221.A1.json"]
        }
    ],
    "warnings": [],
    "recommendations": []
}
```

**Current Status**: ❌ **Not Implemented**
**Implementation Required**:
- JSON Schema validation engine
- Template schema parsing
- Configuration constraint checking
- Path validation for tenant isolation
- Schema availability checking

---

### 5. System Health & Monitoring APIs

#### System Health Endpoint
```http
GET /api/v1/health
Authorization: Bearer {jwt_token}
```

**Current Response** (Basic implementation exists):
```json
{
    "status": "healthy",
    "timestamp": "2025-08-16T10:30:00Z",
    "version": "2.0.0"
}
```

**Required Enhanced Response:**
```json
{
    "status": "healthy",
    "timestamp": "2025-08-16T10:30:00Z",
    "version": "2.0.0",
    "services": {
        "database": {
            "status": "healthy",
            "response_time_ms": 12,
            "connections_active": 8,
            "connections_max": 20
        },
        "nifi": {
            "status": "healthy", 
            "response_time_ms": 45,
            "api_version": "1.18.0",
            "cluster_nodes": 3,
            "process_groups_active": 15
        },
        "nifi_registry": {
            "status": "healthy",
            "response_time_ms": 28,
            "flows_registered": 12,
            "buckets_count": 3
        },
        "keycloak": {
            "status": "healthy",
            "response_time_ms": 35,
            "realm": "edi-lens"
        },
        "storage": {
            "status": "healthy",
            "response_time_ms": 15,
            "provider": "MinIO",
            "buckets_accessible": 4
        }
    },
    "workflows": {
        "total_count": 47,
        "active_count": 42,
        "paused_count": 3,
        "error_count": 2
    },
    "system_metrics": {
        "cpu_usage_percent": 15.3,
        "memory_usage_percent": 42.7,
        "disk_usage_percent": 18.9
    }
}
```

**Current Status**: 🔶 **Basic Implementation Exists**
**Missing Components**:
- Service dependency health checks
- NiFi connectivity monitoring  
- Detailed system metrics
- Workflow status aggregation

---

## 🔧 Implementation Specifications

### 1. Workflow Execution Implementation

#### Required Components
```python
# New service class needed
class WorkflowExecutionService:
    """Service for executing workflows in real-time."""
    
    async def execute_workflow(
        self, 
        workflow_id: str,
        edi_content: str,
        processing_options: dict,
        auth_context: AuthContext
    ) -> WorkflowExecutionResult:
        """Execute workflow with EDI content."""
        
        # 1. Load workflow and template configuration
        workflow = await self._get_workflow(workflow_id)
        template = await self._get_template(workflow.template_id)
        
        # 2. Validate workflow is deployable
        await self._validate_workflow_status(workflow)
        
        # 3. Trigger NiFi process group with parameters
        execution_result = await self._trigger_nifi_execution(
            workflow, edi_content, processing_options
        )
        
        # 4. Process results and generate response
        return await self._format_execution_result(execution_result)

# New NiFi integration needed
class NiFiWorkflowExecutor:
    """Execute workflows via NiFi API."""
    
    async def trigger_process_group(
        self,
        process_group_id: str,
        input_data: str,
        parameters: dict
    ) -> ExecutionResult:
        """Trigger NiFi process group execution."""
        pass
```

#### Required API Endpoints
```python
# Add to src/api/endpoints/workflows.py
@router.post("/{workflow_id}/process", response_model=WorkflowExecutionResponse)
async def execute_workflow(
    workflow_id: UUID,
    execution_request: WorkflowExecutionRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:execute"))
) -> WorkflowExecutionResponse:
    """Execute workflow with provided EDI content."""
    
    execution_service = WorkflowExecutionService(session)
    result = await execution_service.execute_workflow(
        str(workflow_id),
        execution_request.edi_content,
        execution_request.processing_options,
        auth_context
    )
    
    return WorkflowExecutionResponse.from_result(result)

@router.get("/{workflow_id}/status", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: UUID,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
) -> WorkflowStatusResponse:
    """Get detailed workflow status including NiFi information."""
    
    status_service = WorkflowStatusService(session)
    status = await status_service.get_detailed_status(str(workflow_id))
    
    return WorkflowStatusResponse.from_status(status)
```

### 2. Configuration Validation Implementation

#### Required Components
```python
# New validation service
class ConfigurationValidationService:
    """Validate workflow configurations against template schemas."""
    
    async def validate_configuration(
        self,
        template_id: str,
        configuration: dict,
        auth_context: AuthContext
    ) -> ValidationResult:
        """Validate configuration against template schema."""
        
        # 1. Load template and schema
        template = await self._get_template(template_id)
        schema = template.configuration_schema
        
        # 2. Perform JSON schema validation
        json_validation = await self._validate_json_schema(configuration, schema)
        
        # 3. Perform business rule validation
        business_validation = await self._validate_business_rules(
            configuration, template, auth_context
        )
        
        # 4. Generate recommendations
        recommendations = await self._generate_recommendations(
            configuration, template
        )
        
        return ValidationResult(
            valid=json_validation.valid and business_validation.valid,
            errors=json_validation.errors + business_validation.errors,
            warnings=json_validation.warnings + business_validation.warnings,
            recommendations=recommendations
        )
    
    async def _validate_business_rules(
        self,
        configuration: dict,
        template: WorkflowTemplate,
        auth_context: AuthContext
    ) -> ValidationResult:
        """Validate business-specific rules."""
        
        errors = []
        warnings = []
        
        # Tenant path validation
        if 'input_path' in configuration:
            path = configuration['input_path']
            expected_prefix = f"/sftp/tenants/{auth_context.tenant_id}/"
            if not path.startswith(expected_prefix):
                errors.append(ValidationError(
                    field="input_path",
                    message=f"Path must start with {expected_prefix}",
                    current_value=path,
                    expected_pattern=f"^{expected_prefix}.+/$"
                ))
        
        # Schema file validation
        if 'validation' in configuration and 'schema' in configuration['validation']:
            schema_name = configuration['validation']['schema']
            if not await self._schema_exists(schema_name):
                available_schemas = await self._get_available_schemas()
                errors.append(ValidationError(
                    field="validation.schema",
                    message="Schema file does not exist",
                    current_value=schema_name,
                    available_schemas=available_schemas
                ))
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )
```

#### Required API Endpoint
```python
# Add to src/api/endpoints/workflow_templates.py
@router.post("/{template_id}/validate", response_model=ConfigurationValidationResponse)
async def validate_configuration(
    template_id: str,
    validation_request: ConfigurationValidationRequest,
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
) -> ConfigurationValidationResponse:
    """Validate workflow configuration against template schema."""
    
    validation_service = ConfigurationValidationService(session)
    result = await validation_service.validate_configuration(
        template_id,
        validation_request.configuration,
        auth_context
    )
    
    return ConfigurationValidationResponse.from_result(result)
```

### 3. Metrics Collection Implementation

#### Required Components
```python
# New metrics service
class WorkflowMetricsService:
    """Collect and aggregate workflow performance metrics."""
    
    async def collect_workflow_metrics(
        self,
        workflow_id: str,
        time_range: TimeRange,
        granularity: str = "hour"
    ) -> WorkflowMetrics:
        """Collect metrics for specific workflow."""
        
        # 1. Query execution logs from database
        execution_logs = await self._get_execution_logs(workflow_id, time_range)
        
        # 2. Query NiFi metrics via API
        nifi_metrics = await self._get_nifi_metrics(workflow_id, time_range)
        
        # 3. Aggregate metrics
        aggregated = await self._aggregate_metrics(
            execution_logs, nifi_metrics, granularity
        )
        
        # 4. Generate time series data
        time_series = await self._generate_time_series(
            aggregated, time_range, granularity
        )
        
        return WorkflowMetrics(
            workflow_id=workflow_id,
            period=time_range,
            metrics=aggregated,
            time_series=time_series
        )

# New database model for execution tracking
class WorkflowExecution(Base):
    """Track individual workflow executions for metrics."""
    __tablename__ = "workflow_executions"
    
    execution_id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id = Column(PG_UUID(as_uuid=True), nullable=False)
    tenant_id = Column(String, nullable=False)
    
    # Execution details
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_time_ms = Column(Integer, nullable=True)
    status = Column(String, nullable=False)  # SUCCESS, FAILED, TIMEOUT
    
    # Input/output details
    input_file_name = Column(String, nullable=True)
    input_file_size = Column(Integer, nullable=True)
    output_files_count = Column(Integer, nullable=False, default=0)
    
    # Processing results
    validation_errors_count = Column(Integer, nullable=False, default=0)
    validation_warnings_count = Column(Integer, nullable=False, default=0)
    ta1_generated = Column(Boolean, nullable=False, default=False)
    ack999_generated = Column(Boolean, nullable=False, default=False)
    
    # Error details
    error_message = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

#### Required API Endpoints
```python
# Add to src/api/endpoints/workflows.py
@router.get("/{workflow_id}/metrics", response_model=WorkflowMetricsResponse)
async def get_workflow_metrics(
    workflow_id: UUID,
    from_time: Optional[datetime] = Query(None),
    to_time: Optional[datetime] = Query(None),
    granularity: str = Query("hour", regex="^(hour|day|week)$"),
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
) -> WorkflowMetricsResponse:
    """Get workflow performance metrics."""
    
    # Default time range to last 24 hours
    if not to_time:
        to_time = datetime.utcnow()
    if not from_time:
        from_time = to_time - timedelta(hours=24)
    
    metrics_service = WorkflowMetricsService(session)
    metrics = await metrics_service.collect_workflow_metrics(
        str(workflow_id),
        TimeRange(from_time=from_time, to_time=to_time),
        granularity
    )
    
    return WorkflowMetricsResponse.from_metrics(metrics)

@router.get("/{workflow_id}/logs", response_model=WorkflowLogsResponse)
async def get_workflow_logs(
    workflow_id: UUID,
    level: Optional[str] = Query(None, regex="^(DEBUG|INFO|WARN|ERROR)$"),
    from_time: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
    auth_context: AuthContext = Depends(require_permission("workflow:read"))
) -> WorkflowLogsResponse:
    """Get workflow execution logs."""
    
    logs_service = WorkflowLogsService(session)
    logs = await logs_service.get_workflow_logs(
        str(workflow_id),
        level=level,
        from_time=from_time,
        limit=limit,
        offset=offset
    )
    
    return WorkflowLogsResponse.from_logs(logs)
```

## 📋 Required Schema Updates

### 1. New Request/Response Models

```python
# Add to src/api/schemas.py

# Workflow Execution Schemas
class WorkflowExecutionRequest(BaseModel):
    """Request schema for workflow execution."""
    edi_content: str = Field(..., description="EDI content to process")
    request_id: Optional[str] = Field(None, description="Client request ID")
    processing_options: Dict[str, Any] = Field(
        default_factory=dict,
        description="Processing options"
    )

class WorkflowExecutionResponse(BaseModel):
    """Response schema for workflow execution."""
    valid: bool = Field(..., description="Whether processing was successful")
    validation_results: List[ValidationFinding] = Field(
        default=[], 
        description="Validation findings"
    )
    ta1_acknowledgment: Optional[str] = Field(None, description="TA1 acknowledgment")
    ack999_acknowledgment: Optional[str] = Field(None, description="999 acknowledgment")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    request_id: Optional[str] = Field(None, description="Client request ID")
    workflow_id: str = Field(..., description="Workflow ID")

# Workflow Status Schemas
class WorkflowStatusResponse(BaseModel):
    """Response schema for detailed workflow status."""
    workflow_id: str = Field(..., description="Workflow ID")
    status: WorkflowStatus = Field(..., description="Workflow status")
    nifi_status: Optional[str] = Field(None, description="NiFi process group status")
    deployment_status: Optional[str] = Field(None, description="Deployment status")
    last_execution: Optional[datetime] = Field(None, description="Last execution time")
    execution_count: int = Field(0, description="Total execution count")
    error_count: int = Field(0, description="Total error count")
    success_rate: float = Field(0.0, description="Success rate")
    process_group_id: Optional[str] = Field(None, description="NiFi process group ID")
    parameter_context_id: Optional[str] = Field(None, description="Parameter context ID")
    flow_version: Optional[int] = Field(None, description="Flow version")
    health_check: Dict[str, Any] = Field(
        default_factory=dict,
        description="Health check results"
    )

# Configuration Validation Schemas
class ConfigurationValidationRequest(BaseModel):
    """Request schema for configuration validation."""
    configuration: Dict[str, Any] = Field(..., description="Configuration to validate")

class ValidationError(BaseModel):
    """Schema for validation error."""
    field: str = Field(..., description="Field with error")
    message: str = Field(..., description="Error message") 
    current_value: Optional[Any] = Field(None, description="Current value")
    expected_pattern: Optional[str] = Field(None, description="Expected pattern")
    available_options: Optional[List[str]] = Field(None, description="Available options")

class ValidationWarning(BaseModel):
    """Schema for validation warning."""
    field: str = Field(..., description="Field with warning")
    message: str = Field(..., description="Warning message")
    severity: str = Field(..., description="Warning severity")

class ValidationRecommendation(BaseModel):
    """Schema for validation recommendation."""
    field: str = Field(..., description="Field for recommendation")
    message: str = Field(..., description="Recommendation message")
    suggestion: Optional[str] = Field(None, description="Suggested value")

class ConfigurationValidationResponse(BaseModel):
    """Response schema for configuration validation."""
    valid: bool = Field(..., description="Whether configuration is valid")
    errors: List[ValidationError] = Field(default=[], description="Validation errors")
    warnings: List[ValidationWarning] = Field(default=[], description="Validation warnings")
    recommendations: List[ValidationRecommendation] = Field(
        default=[], 
        description="Recommendations"
    )

# Metrics Schemas
class WorkflowMetrics(BaseModel):
    """Schema for workflow metrics."""
    files_processed: int = Field(0, description="Total files processed")
    processing_time_avg_ms: float = Field(0.0, description="Average processing time")
    processing_time_p95_ms: float = Field(0.0, description="95th percentile processing time")
    processing_time_p99_ms: float = Field(0.0, description="99th percentile processing time")
    success_rate: float = Field(0.0, description="Success rate")
    error_rate: float = Field(0.0, description="Error rate") 
    throughput_files_per_hour: float = Field(0.0, description="Throughput")
    acknowledgments_generated: Dict[str, int] = Field(
        default_factory=dict,
        description="Acknowledgments generated"
    )

class TimeSeriesDataPoint(BaseModel):
    """Schema for time series data point."""
    timestamp: datetime = Field(..., description="Data point timestamp")
    files_processed: int = Field(0, description="Files processed in period")
    avg_processing_time_ms: float = Field(0.0, description="Average processing time")
    errors: int = Field(0, description="Errors in period")

class WorkflowMetricsResponse(BaseModel):
    """Response schema for workflow metrics."""
    workflow_id: str = Field(..., description="Workflow ID")
    period: Dict[str, Any] = Field(..., description="Time period")
    metrics: WorkflowMetrics = Field(..., description="Aggregated metrics")
    time_series: List[TimeSeriesDataPoint] = Field(
        default=[],
        description="Time series data"
    )

# Logs Schemas
class WorkflowLogEntry(BaseModel):
    """Schema for workflow log entry."""
    timestamp: datetime = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level")
    message: str = Field(..., description="Log message")
    component: str = Field(..., description="Component that generated log")
    processor_id: Optional[str] = Field(None, description="NiFi processor ID")
    file_name: Optional[str] = Field(None, description="File being processed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata"
    )

class WorkflowLogsResponse(BaseModel):
    """Response schema for workflow logs."""
    workflow_id: str = Field(..., description="Workflow ID")
    logs: List[WorkflowLogEntry] = Field(..., description="Log entries")
    total: int = Field(..., description="Total log entries")
    limit: int = Field(..., description="Limit used")
    offset: int = Field(..., description="Offset used")
    has_more: bool = Field(..., description="Whether more logs available")
```

## 🚀 Implementation Roadmap

### Phase 1: Core Execution APIs (Week 1)
1. **Workflow Execution Endpoint**: `POST /api/workflows/{workflow_id}/process`
2. **Workflow Status Endpoint**: `GET /api/v1/workflows/{workflow_id}/status`
3. **Dedicated Control Endpoints**: Pause, resume, restart, stop

### Phase 2: Configuration Validation (Week 2)
1. **Configuration Validation Endpoint**: `POST /api/v1/workflow-templates/{id}/validate`
2. **JSON Schema Validation Engine**
3. **Business Rules Validation**
4. **Tenant Path Validation**

### Phase 3: Metrics & Monitoring (Week 3-4)
1. **Workflow Metrics Endpoint**: `GET /api/v1/workflows/{workflow_id}/metrics`
2. **Workflow Logs Endpoint**: `GET /api/v1/workflows/{workflow_id}/logs`
3. **Enhanced Health Endpoint**: Extended system monitoring
4. **Execution Tracking Database Model**

### Phase 4: Testing & Documentation (Week 5)
1. **Comprehensive API Tests**: All new endpoints
2. **Integration Tests**: End-to-end workflow execution
3. **API Documentation**: OpenAPI specification updates
4. **Performance Testing**: Load and stress testing

This detailed specification provides the complete blueprint for implementing the missing API functionality. Each endpoint is fully specified with request/response schemas, implementation requirements, and database model changes needed.