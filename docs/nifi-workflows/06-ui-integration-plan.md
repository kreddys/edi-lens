# NiFi Workflow UI Integration Plan

## Overview

This document outlines the plan for integrating NiFi workflow management capabilities into the EDI Lens admin UI. The goal is to provide users with a comprehensive interface for managing workflow templates and workflows through the NiFi integration.

## Current UI vs. Backend Reality

### Current UI Navigation
```
Trading Partners | Schema Editor | Processing History | Validation
```

### Backend Capabilities (NiFi Integration)
1. **Workflow Templates** - Reusable templates for different workflow types
2. **Workflows** - Instances of templates with specific configurations
3. **NiFi Integration** - Full deployment, management, and control of workflows
4. **API Endpoints** - Complete REST API for all workflow operations

### UI Gap Analysis
The current UI does not expose the NiFi workflow capabilities that are fully implemented in the backend. We need to add dedicated sections for workflow template and workflow management.

## Proposed UI Structure

### New Navigation Structure
```
Workflow Templates | Workflows | Schema Editor | Processing History | Validation
```

Note: Trading Partners will be removed as it's no longer part of the backend.

## Workflow Templates Section

### Purpose
Manage reusable workflow templates that define the structure and behavior of workflows.

### Key Features
1. **Template Listing**
   - View all available templates (global and tenant-specific)
   - Filter by category, scope, status, tags
   - Sort by usage, creation date, featured status

2. **Template Details**
   - View template metadata (name, description, category, version)
   - View NiFi flow definition
   - View configuration schema
   - View usage statistics

3. **Template Creation/Editing**
   - Create new templates from scratch
   - Edit existing templates
   - Clone templates with customizations
   - Validate flow definitions and schemas

### Template Categories
- **BATCH** - SFTP file monitoring and processing
- **REALTIME** - HTTP endpoint processing
- **TRANSFORMATION** - Data format conversion
- **INTEGRATION** - System integration workflows

### Template Scopes
- **GLOBAL** - Platform-managed templates available to all tenants
- **TENANT** - Tenant-specific templates

## Workflows Section

### Purpose
Manage deployed workflow instances based on templates.

### Key Features
1. **Workflow Listing**
   - View all workflows for the current tenant
   - Filter by template, status, tags
   - Sort by creation date, status

2. **Workflow Details**
   - View workflow configuration
   - View deployment status
   - View NiFi integration details
   - View monitoring information

3. **Workflow Management**
   - Create workflows from templates
   - Deploy/undeploy workflows to NiFi
   - Start/stop/restart workflows
   - Update workflow configurations

4. **Workflow Execution**
   - Execute workflows with EDI content
   - View execution results
   - View generated acknowledgments

### Workflow Statuses
- **ACTIVE** - Workflow is running and processing
- **PAUSED** - Workflow is deployed but not processing
- **ERROR** - Workflow has encountered an error
- **DELETED** - Workflow has been undeployed

### Workflow Actions
- **Deploy** - Deploy workflow to NiFi
- **Undeploy** - Remove workflow from NiFi
- **Start** - Start processing
- **Stop** - Pause processing
- **Restart** - Stop and start processing
- **Execute** - Run workflow with EDI content

## UI Component Structure

### 1. Workflow Templates Components
- `WorkflowTemplateList` - List all templates with filtering
- `WorkflowTemplateCreate` - Create new templates
- `WorkflowTemplateEdit` - Edit existing templates
- `WorkflowTemplateShow` - View template details
- `WorkflowTemplateClone` - Clone templates with customizations

### 2. Workflows Components
- `WorkflowList` - List all workflows with filtering
- `WorkflowCreate` - Create workflows from templates
- `WorkflowEdit` - Edit workflow configurations
- `WorkflowShow` - View workflow details and status
- `WorkflowExecute` - Execute workflows with EDI content
- `WorkflowStatus` - View detailed workflow status
- `WorkflowControl` - Deploy/undeploy/start/stop/restart controls

## API Integration Points

### Workflow Templates API Endpoints
- `GET /api/v1/workflow-templates/` - List templates
- `POST /api/v1/workflow-templates/` - Create template
- `GET /api/v1/workflow-templates/{template_id}` - Get template
- `PUT /api/v1/workflow-templates/{template_id}` - Update template
- `DELETE /api/v1/workflow-templates/{template_id}` - Delete template
- `POST /api/v1/workflow-templates/{template_id}/clone` - Clone template

### Workflows API Endpoints
- `GET /api/v1/workflows/` - List workflows
- `POST /api/v1/workflows/` - Create workflow
- `GET /api/v1/workflows/{workflow_id}` - Get workflow
- `PUT /api/v1/workflows/{workflow_id}` - Update workflow
- `DELETE /api/v1/workflows/{workflow_id}` - Delete workflow
- `POST /api/v1/workflows/{workflow_id}/deploy` - Deploy workflow
- `POST /api/v1/workflows/{workflow_id}/undeploy` - Undeploy workflow
- `POST /api/v1/workflows/{workflow_id}/start` - Start workflow
- `POST /api/v1/workflows/{workflow_id}/stop` - Stop workflow
- `POST /api/v1/workflows/{workflow_id}/restart` - Restart workflow
- `POST /api/v1/workflows/{workflow_id}/process` - Execute workflow
- `GET /api/v1/workflows/{workflow_id}/status` - Get workflow status

## User Experience Considerations

### 1. Workflow Creation Flow
1. User selects "Create Workflow" from Workflows section
2. User chooses a template from the available templates
3. User configures the workflow based on the template's configuration schema
4. User reviews and confirms workflow creation
5. Workflow is created in the database (not yet deployed)

### 2. Workflow Deployment Flow
1. User navigates to an existing workflow
2. User clicks "Deploy" button
3. System deploys the workflow to NiFi
4. User can monitor deployment progress
5. Workflow status updates to ACTIVE

### 3. Workflow Execution Flow
1. User navigates to a deployed workflow
2. User clicks "Execute" button
3. User provides EDI content and processing options
4. System executes the workflow through NiFi
5. User views results including validation findings and acknowledgments

## Security Considerations

### Role-Based Access Control
- **workflow:read** - View templates and workflows
- **workflow:write** - Create, edit, deploy, undeploy workflows
- **workflow:execute** - Execute workflows
- **workflow:admin** - Advanced template management

### Tenant Isolation
- Users can only see templates and workflows for their tenant
- Global templates are visible to all tenants but can only be modified by admins
- All operations are scoped to the user's tenant

## Implementation Phases

### Phase 1: Core UI Structure (Week 1)
1. Update navigation to include Workflow Templates and Workflows
2. Remove Trading Partners section
3. Implement basic list views for templates and workflows
4. Set up API integration for data fetching

### Phase 2: Template Management (Week 2)
1. Implement template creation, editing, and cloning
2. Add template detail views
3. Implement template filtering and search
4. Add validation for template definitions

### Phase 3: Workflow Management (Week 3)
1. Implement workflow creation from templates
2. Add workflow deployment controls
3. Implement workflow status monitoring
4. Add workflow execution interface

### Phase 4: Advanced Features (Week 4)
1. Add workflow monitoring and analytics
2. Implement bulk operations
3. Add export/import functionality
4. Implement advanced filtering and reporting

## Success Metrics

### User Experience Metrics
- Time to create first workflow: < 5 minutes
- Time to deploy workflow: < 1 minute
- Template reuse rate: > 80%
- User satisfaction score: > 4.5/5

### Technical Metrics
- API response time: < 200ms for most operations
- UI load time: < 2 seconds
- Error rate: < 1%
- Test coverage: > 90%

## Dependencies

### Frontend Dependencies
- React with TypeScript
- Ant Design components
- Refine framework
- Axios for API calls

### Backend Dependencies
- Apache NiFi 1.23+
- Apache NiFi Registry 1.23+
- PostgreSQL database
- Keycloak identity provider

## Risks and Mitigation

### Technical Risks
1. **NiFi connectivity issues**
   - Mitigation: Implement proper error handling and retry logic
   - Mitigation: Provide clear error messages to users

2. **Performance with large numbers of workflows**
   - Mitigation: Implement pagination and filtering
   - Mitigation: Optimize database queries

### User Experience Risks
1. **Complexity of workflow configuration**
   - Mitigation: Provide clear documentation and examples
   - Mitigation: Implement guided setup wizards

2. **Confusion between templates and workflows**
   - Mitigation: Clear UI distinction and terminology
   - Mitigation: Provide tooltips and help text

## Future Enhancements

### Advanced Features
1. **Workflow Versioning** - Manage multiple versions of templates and workflows
2. **Workflow Scheduling** - Schedule workflows to run at specific times
3. **Workflow Dependencies** - Define dependencies between workflows
4. **Workflow Marketplace** - Share and discover templates
5. **Advanced Monitoring** - Real-time metrics and alerts
6. **Workflow Testing** - Test workflows with sample data

### Integration Features
1. **Third-party System Integration** - Connect to external systems
2. **Custom Processor Support** - Upload and use custom NiFi processors
3. **Advanced Routing** - Complex routing based on content
4. **Machine Learning** - AI-powered workflow optimization

---
*Document created: August 17, 2025*
*Author: EDI Lens Development Team*