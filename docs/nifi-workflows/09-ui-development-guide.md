# NiFi Workflow UI Development Guide

## Overview

This guide provides instructions for developers continuing the implementation of the NiFi workflow management UI components. It covers setup, development workflow, testing, and deployment considerations.

## Development Environment Setup

### Prerequisites
1. Node.js 16+ installed
2. npm or yarn package manager
3. Access to the EDI Lens backend API
4. Apache NiFi and NiFi Registry instances for testing

### Initial Setup
```bash
# Navigate to the admin UI directory
cd admin-ui

# Install dependencies
npm install

# Start the development server
npm run dev
```

### Environment Variables
Create a `.env` file in the `admin-ui` directory:
```env
VITE_API_URL=http://localhost:8000/api/v1
VITE_NIFI_URL=http://localhost:8080
VITE_NIFI_REGISTRY_URL=http://localhost:18080
```

## Project Structure

```
admin-ui/
├── src/
│   ├── components/
│   │   └── workflow/          # Shared workflow components
│   ├── pages/
│   │   ├── workflowTemplates/ # Workflow template management
│   │   └── workflows/         # Workflow management
│   ├── providers/             # Data and auth providers
│   └── hooks/                 # Custom React hooks
├── public/                   # Static assets
└── tests/                    # Test files
```

## Component Development Guidelines

### 1. Component Naming Convention
- Use PascalCase for component names
- Prefix with context (e.g., `WorkflowTemplateList`, `WorkflowControl`)
- Use descriptive names that indicate purpose

### 2. File Structure
```
ComponentName/
├── index.ts        # Export statements
├── ComponentName.tsx  # Main component
└── ComponentName.test.tsx  # Unit tests
```

### 3. TypeScript Interfaces
Define interfaces for props and state at the top of each component file:
```typescript
interface WorkflowTemplateProps {
  templateId: string;
  onEdit: (templateId: string) => void;
  onDelete: (templateId: string) => void;
}

interface WorkflowTemplateState {
  isLoading: boolean;
  error: string | null;
}
```

### 4. Styling
- Use Ant Design components for consistency
- Follow existing styling patterns
- Use inline styles for component-specific styling
- Use CSS modules for complex styling needs

## API Integration

### Using Refine Data Provider
The project uses Refine's data provider for API integration. Here's how to use it:

```typescript
import { useCustom, useList, useOne } from "@refinedev/core";

// For listing resources
const { data, isLoading, error } = useList({
  resource: "workflow-templates",
  filters: [
    { field: "category", operator: "eq", value: "BATCH" }
  ]
});

// For getting a single resource
const { data, isLoading, error } = useOne({
  resource: "workflows",
  id: workflowId
});

// For custom API calls
const { data, isLoading, error } = useCustom({
  url: `/workflows/${workflowId}/status`,
  method: "get"
});
```

### Error Handling
Always implement proper error handling:

```typescript
import { notification } from "antd";

try {
  const response = await fetch("/api/workflows", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${authToken}`
    },
    body: JSON.stringify(workflowData)
  });
  
  if (!response.ok) {
    const errorData = await response.json();
    throw new Error(errorData.detail || "Failed to create workflow");
  }
  
  const data = await response.json();
  notification.success({
    message: "Success",
    description: "Workflow created successfully"
  });
} catch (error: any) {
  notification.error({
    message: "Error",
    description: error.message || "Failed to create workflow"
  });
}
```

## Testing Strategy

### Unit Testing
Use Jest and React Testing Library for unit tests:

```typescript
import { render, screen, fireEvent } from "@testing-library/react";
import { WorkflowTemplateList } from "./list";

test("renders workflow template list", () => {
  render(<WorkflowTemplateList />);
  
  expect(screen.getByText("Workflow Templates")).toBeInTheDocument();
  expect(screen.getByText("Create Template")).toBeInTheDocument();
});
```

### Integration Testing
Test API integration with mock data:

```typescript
import { render, screen, waitFor } from "@testing-library/react";
import { TestWrapper } from "../../test-utils";
import { WorkflowTemplateList } from "./list";

test("fetches and displays templates", async () => {
  render(
    <TestWrapper>
      <WorkflowTemplateList />
    </TestWrapper>
  );
  
  await waitFor(() => {
    expect(screen.getByText("Sample Template")).toBeInTheDocument();
  });
});
```

### End-to-End Testing
Use Cypress for end-to-end tests:

```typescript
describe("Workflow Management", () => {
  it("should create a new workflow", () => {
    cy.visit("/workflows");
    cy.contains("Create Workflow").click();
    cy.get("[data-testid=template-select]").select("batch-processor");
    cy.get("[data-testid=name-input]").type("Test Workflow");
    cy.get("[data-testid=submit-button]").click();
    cy.contains("Workflow created successfully").should("be.visible");
  });
});
```

## Development Workflow

### 1. Feature Branch Development
```bash
# Create a new branch for your feature
git checkout -b feature/workflow-execution

# Make your changes
# ... code ...

# Commit your changes
git add .
git commit -m "Add workflow execution functionality"

# Push to remote
git push origin feature/workflow-execution
```

### 2. Code Review Process
1. Create a pull request
2. Request review from team members
3. Address feedback
4. Merge after approval

### 3. Continuous Integration
- All PRs must pass CI checks
- Tests must pass
- Code must be linted and formatted

## Component Implementation Checklist

### Workflow Template Components
- [ ] `WorkflowTemplateList` - Complete with filtering and sorting
- [ ] `WorkflowTemplateCreate` - Form with validation
- [ ] `WorkflowTemplateEdit` - Form with existing data
- [ ] `WorkflowTemplateShow` - Detailed view with all information
- [ ] `WorkflowTemplateClone` - Template cloning functionality

### Workflow Components
- [ ] `WorkflowList` - Complete with all actions
- [ ] `WorkflowCreate` - Form with template selection
- [ ] `WorkflowEdit` - Form with configuration editing
- [ ] `WorkflowShow` - Detailed view with monitoring
- [ ] `WorkflowExecute` - EDI content execution interface

### Shared Components
- [ ] `StatusBadges` - All badge types implemented
- [ ] `JsonEditor` - JSON editor with validation
- [ ] `ConfigurationForm` - Dynamic form generator
- [ ] `WorkflowControl` - All workflow actions implemented

## API Endpoint Implementation Status

### Workflow Templates
- [x] `GET /api/v1/workflow-templates/` - List templates
- [x] `POST /api/v1/workflow-templates/` - Create template
- [x] `GET /api/v1/workflow-templates/{template_id}` - Get template
- [x] `PUT /api/v1/workflow-templates/{template_id}` - Update template
- [x] `DELETE /api/v1/workflow-templates/{template_id}` - Delete template
- [x] `POST /api/v1/workflow-templates/{template_id}/clone` - Clone template

### Workflows
- [x] `GET /api/v1/workflows/` - List workflows
- [x] `POST /api/v1/workflows/` - Create workflow
- [x] `GET /api/v1/workflows/{workflow_id}` - Get workflow
- [x] `PUT /api/v1/workflows/{workflow_id}` - Update workflow
- [x] `DELETE /api/v1/workflows/{workflow_id}` - Delete workflow
- [x] `POST /api/v1/workflows/{workflow_id}/deploy` - Deploy workflow
- [x] `POST /api/v1/workflows/{workflow_id}/undeploy` - Undeploy workflow
- [x] `POST /api/v1/workflows/{workflow_id}/start` - Start workflow
- [x] `POST /api/v1/workflows/{workflow_id}/stop` - Stop workflow
- [x] `POST /api/v1/workflows/{workflow_id}/restart` - Restart workflow
- [x] `POST /api/v1/workflows/{workflow_id}/process` - Execute workflow
- [x] `GET /api/v1/workflows/{workflow_id}/status` - Get workflow status

## Common Development Tasks

### Adding a New Page
1. Create a new directory in `src/pages/`
2. Create `index.ts` with export statements
3. Create component files (`list.tsx`, `create.tsx`, etc.)
4. Update `App.tsx` with new routes
5. Add to `resources` array in Refine configuration

### Adding a New Component
1. Create component in appropriate directory
2. Export from `index.ts` file
3. Import and use in parent components
4. Add unit tests
5. Update documentation

### Adding API Integration
1. Identify required API endpoints
2. Use appropriate Refine hooks (`useList`, `useOne`, `useCustom`)
3. Handle loading and error states
4. Implement proper error handling
5. Add loading indicators

## Troubleshooting

### Common Issues

1. **API Connection Errors**
   - Check `.env` file for correct API URLs
   - Verify backend is running
   - Check browser console for CORS errors

2. **Component Not Rendering**
   - Check import statements
   - Verify component is exported correctly
   - Check for TypeScript errors

3. **Styling Issues**
   - Check Ant Design component usage
   - Verify CSS class names
   - Check for conflicting styles

### Debugging Tips

1. Use React Developer Tools browser extension
2. Add console.log statements for debugging
3. Use browser network tab to inspect API calls
4. Check Redux DevTools if using Redux

## Performance Optimization

### 1. Code Splitting
```typescript
import { lazy, Suspense } from "react";

const WorkflowTemplateList = lazy(() => import("./pages/workflowTemplates/list"));

function App() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <WorkflowTemplateList />
    </Suspense>
  );
}
```

### 2. Memoization
```typescript
import { useMemo } from "react";

const expensiveValue = useMemo(() => {
  // Expensive calculation
  return computeExpensiveValue(data);
}, [data]);
```

### 3. Virtualization
```typescript
import { Table } from "antd";

// For large datasets, use virtualization
<Table 
  virtual 
  scroll={{ y: 400 }}
  pagination={{ pageSize: 50 }}
  {...tableProps}
/>
```

## Security Considerations

### 1. Authentication
- Always check for authentication tokens
- Redirect to login when unauthenticated
- Handle token expiration gracefully

### 2. Authorization
- Check user permissions before rendering actions
- Hide actions user doesn't have permission for
- Display appropriate error messages

### 3. Data Protection
- Sanitize user input
- Validate data before API submission
- Protect sensitive configuration data

## Deployment

### Build Process
```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

### Environment Configuration
- Set production API URLs in environment variables
- Configure proper authentication settings
- Set up monitoring and error tracking

## Contributing

### Code Standards
1. Follow existing code style
2. Write clear, descriptive commit messages
3. Add tests for new functionality
4. Update documentation when making changes

### Pull Request Process
1. Create feature branch
2. Implement changes
3. Add tests
4. Update documentation
5. Create pull request
6. Request review
7. Address feedback
8. Merge after approval

---
*Document created: August 17, 2025*
*Author: EDI Lens Development Team*