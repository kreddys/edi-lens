# NiFi Workflow UI Component Implementation Plan

## Overview

This document provides a detailed implementation plan for the UI components needed to integrate NiFi workflow management into the EDI Lens admin UI. It builds upon the high-level UI integration plan and provides specific technical details for implementation.

## Component Structure

### 1. Workflow Templates Components

#### WorkflowTemplateList
**Location**: `admin-ui/src/pages/workflowTemplates/list.tsx`

**Features**:
- Display templates in a table with columns: Name, Category, Scope, Status, Version, Usage Count
- Filtering capabilities by category, scope, status, tags
- Sorting by usage count, creation date, featured status
- Action buttons: View Details, Edit, Create Workflow
- Create Template button in header

**API Integration**:
- Endpoint: `GET /api/v1/workflow-templates/`
- Parameters: 
  - `category` (optional): Filter by category (BATCH, REALTIME, TRANSFORMATION, INTEGRATION)
  - `scope` (optional): Filter by scope (GLOBAL, TENANT)
  - `status` (optional): Filter by status (ACTIVE, DEPRECATED, ARCHIVED)
  - `featured_only` (optional): boolean to show only featured templates
  - `tags` (optional): array of tags to filter by
  - `page` (default: 1): Page number
  - `page_size` (default: 20): Items per page

#### WorkflowTemplateShow
**Location**: `admin-ui/src/pages/workflowTemplates/show.tsx`

**Features**:
- Display template metadata (name, description, category, version, scope, status)
- Display tags and features
- Display configuration schema in a readable format
- Display NiFi flow definition
- Display usage statistics
- Action buttons: Create Workflow, Edit Template, Clone Template, Delete Template

**API Integration**:
- Endpoint: `GET /api/v1/workflow-templates/{template_id}`

#### WorkflowTemplateCreate
**Location**: `admin-ui/src/pages/workflowTemplates/create.tsx`

**Features**:
- Form with fields for all template properties
- JSON editors for flow definition and configuration schema
- Validation for required fields
- Preview of template structure
- Save and Cancel buttons

**API Integration**:
- Endpoint: `POST /api/v1/workflow-templates/`

#### WorkflowTemplateEdit
**Location**: `admin-ui/src/pages/workflowTemplates/edit.tsx`

**Features**:
- Pre-populated form with existing template data
- JSON editors for flow definition and configuration schema
- Validation for required fields
- Save, Cancel, and Delete buttons

**API Integration**:
- Endpoint: `PUT /api/v1/workflow-templates/{template_id}`

#### WorkflowTemplateClone (Future)
**Location**: `admin-ui/src/pages/workflowTemplates/clone.tsx`

**Features**:
- Pre-populated form with source template data
- Ability to modify template properties
- Customization options for flow definition
- Save as new template

**API Integration**:
- Endpoint: `POST /api/v1/workflow-templates/{template_id}/clone`

### 2. Workflows Components

#### WorkflowList
**Location**: `admin-ui/src/pages/workflows/list.tsx`

**Features**:
- Display workflows in a table with columns: Name, Template, Status, Deployment, NiFi Status
- Filtering capabilities by template, status, tags
- Sorting by creation date, status
- Action buttons based on workflow state:
  - Deployed: Pause, Restart, Undeploy, Execute
  - Not Deployed: Deploy, Execute
- Create Workflow button in header

**API Integration**:
- Endpoint: `GET /api/v1/workflows/`
- Parameters:
  - `template_id` (optional): Filter by template
  - `status` (optional): Filter by status (ACTIVE, PAUSED, ERROR, DELETED)
  - `tags` (optional): array of tags to filter by
  - `page` (default: 1): Page number
  - `page_size` (default: 20): Items per page

#### WorkflowShow
**Location**: `admin-ui/src/pages/workflows/show.tsx`

**Features**:
- Display workflow metadata (name, description, template, status)
- Display configuration in a readable format
- Display deployment information (NiFi process group ID, parameter context ID)
- Display monitoring information (last execution, execution count, success rate)
- Action buttons based on workflow state:
  - Deployed: Pause, Restart, Undeploy, Execute
  - Not Deployed: Deploy, Execute
- Configuration editing capabilities

**API Integration**:
- Endpoint: `GET /api/v1/workflows/{workflow_id}`
- Endpoint: `GET /api/v1/workflows/{workflow_id}/status`

#### WorkflowCreate
**Location**: `admin-ui/src/pages/workflows/create.tsx`

**Features**:
- Template selection interface
- Configuration form based on template's configuration schema
- Preview of workflow structure
- Create and Cancel buttons

**API Integration**:
- Endpoint: `POST /api/v1/workflows/`

#### WorkflowEdit
**Location**: `admin-ui/src/pages/workflows/edit.tsx`

**Features**:
- Pre-populated form with existing workflow data
- Configuration editing based on template's configuration schema
- Save, Cancel, and Delete buttons

**API Integration**:
- Endpoint: `PUT /api/v1/workflows/{workflow_id}`

#### WorkflowExecute
**Location**: `admin-ui/src/pages/workflows/execute.tsx`

**Features**:
- EDI content input (text area or file upload)
- Processing options configuration
- Execute button
- Results display with validation findings and acknowledgments

**API Integration**:
- Endpoint: `POST /api/v1/workflows/{workflow_id}/process`

#### WorkflowControl
**Location**: `admin-ui/src/components/workflow/WorkflowControl.tsx` (Shared component)

**Features**:
- Deploy button: `POST /api/v1/workflows/{workflow_id}/deploy`
- Undeploy button: `POST /api/v1/workflows/{workflow_id}/undeploy`
- Start button: `POST /api/v1/workflows/{workflow_id}/start`
- Stop button: `POST /api/v1/workflows/{workflow_id}/stop`
- Restart button: `POST /api/v1/workflows/{workflow_id}/restart`

## Shared Components

### 1. StatusBadges
**Location**: `admin-ui/src/components/workflow/StatusBadges.tsx`

**Purpose**: Reusable components for displaying status information with appropriate styling.

**Components**:
- `TemplateStatusBadge` - For template statuses (ACTIVE, DEPRECATED, ARCHIVED)
- `WorkflowStatusBadge` - For workflow statuses (ACTIVE, PAUSED, ERROR, DELETED)
- `ScopeBadge` - For template scopes (GLOBAL, TENANT)
- `CategoryBadge` - For template categories (BATCH, REALTIME, TRANSFORMATION, INTEGRATION)
- `DeploymentBadge` - For deployment status (Deployed, Not Deployed)

### 2. JsonEditor
**Location**: `admin-ui/src/components/workflow/JsonEditor.tsx`

**Purpose**: Reusable JSON editor component for flow definitions and configuration schemas.

**Features**:
- Syntax highlighting
- Validation
- Collapsible sections
- Copy to clipboard
- Format/Minify options

### 3. ConfigurationForm
**Location**: `admin-ui/src/components/workflow/ConfigurationForm.tsx`

**Purpose**: Dynamic form generator based on JSON schema.

**Features**:
- Generate form fields based on configuration schema
- Validation based on schema requirements
- Support for different data types (string, number, boolean, object, array)
- Conditional fields based on dependencies

## Implementation Phases

### Phase 1: Core List Views (Week 1)
**Deliverables**:
1. WorkflowTemplateList component with basic table display
2. WorkflowList component with basic table display
3. Status badge components
4. Basic API integration for data fetching
5. Navigation integration in App.tsx

### Phase 2: Detail Views (Week 2)
**Deliverables**:
1. WorkflowTemplateShow component with detailed template information
2. WorkflowShow component with detailed workflow information
3. Status display components
4. API integration for detail endpoints
5. Back navigation between list and detail views

### Phase 3: Creation and Editing (Week 3)
**Deliverables**:
1. WorkflowTemplateCreate/Edit components with forms
2. WorkflowCreate/Edit components with forms
3. JSON editor component
4. Configuration form component
5. API integration for create/update endpoints

### Phase 4: Workflow Control (Week 4)
**Deliverables**:
1. WorkflowControl component with all action buttons
2. WorkflowExecute component for running workflows
3. API integration for workflow control endpoints
4. Real-time status updates
5. Error handling and user feedback

## Data Models

### WorkflowTemplate
```typescript
interface WorkflowTemplate {
  template_id: string;
  name: string;
  description: string | null;
  category: "BATCH" | "REALTIME" | "TRANSFORMATION" | "INTEGRATION";
  scope: "GLOBAL" | "TENANT";
  tenant_id: string | null;
  maintainer: string | null;
  based_on: string | null;
  version: string;
  flow_definition: Record<string, any>;
  configuration_schema: Record<string, any>;
  deployment_method: "registry" | "xml";
  nifi_registry_flow_id: string | null;
  nifi_registry_bucket_id: string | null;
  status: "ACTIVE" | "DEPRECATED" | "ARCHIVED";
  is_featured: boolean;
  usage_count: number;
  tags: string[];
  features: string[];
  documentation: string | null;
  examples: Record<string, any> | null;
  created_at: string;
  updated_at: string;
  deprecated_at: string | null;
}
```

### Workflow
```typescript
interface Workflow {
  workflow_id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  tags: string[];
  template_id: string;
  configuration: Record<string, any>;
  status: "ACTIVE" | "PAUSED" | "ERROR" | "DELETED";
  nifi_process_group_id: string | null;
  nifi_parameter_context_id: string | null;
  deployment_method: "registry" | "xml" | null;
  flow_version: number | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  is_deployed: boolean;
}
```

### WorkflowStatus
```typescript
interface WorkflowStatus {
  workflow_id: string;
  status: "ACTIVE" | "PAUSED" | "ERROR" | "DELETED";
  nifi_status: string | null;
  deployment_status: string | null;
  last_execution: string | null;
  execution_count: number;
  error_count: number;
  success_rate: number;
  process_group_id: string | null;
  parameter_context_id: string | null;
  flow_version: number | null;
  health_check: Record<string, any>;
}
```

## Error Handling

### Common Error Scenarios
1. **API Connectivity Issues**
   - Display user-friendly error messages
   - Provide retry options
   - Log errors for debugging

2. **Validation Errors**
   - Highlight invalid form fields
   - Display specific error messages
   - Prevent submission until corrected

3. **NiFi Integration Errors**
   - Display NiFi-specific error information
   - Provide guidance for resolution
   - Log detailed error information

### Error Display Components
- `ErrorBanner` - For page-level errors
- `FieldError` - For form field errors
- `Notification` - For transient error messages

## Testing Strategy

### Unit Tests
- Test individual components with mock data
- Test form validation logic
- Test API integration functions

### Integration Tests
- Test API endpoints with real data
- Test workflow from template selection to execution
- Test error scenarios

### User Acceptance Tests
- Test end-to-end user workflows
- Test accessibility features
- Test responsive design

## Performance Considerations

### Data Loading
- Implement pagination for large datasets
- Use loading indicators for API calls
- Cache frequently accessed data

### Rendering Optimization
- Virtualize large tables
- Implement lazy loading for complex components
- Optimize re-renders with React.memo

### API Optimization
- Implement request caching
- Use efficient filtering and sorting on backend
- Batch related API calls when possible

## Security Considerations

### Authentication
- Ensure all API calls include authentication tokens
- Handle token expiration gracefully
- Redirect to login when authentication fails

### Authorization
- Implement role-based access control
- Hide actions user doesn't have permission for
- Display appropriate error messages for forbidden actions

### Data Protection
- Sanitize user input
- Validate data before API submission
- Protect sensitive configuration data

---
*Document created: August 17, 2025*
*Author: EDI Lens Development Team*