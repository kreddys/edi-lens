# NiFi Workflow UI Testing Guide

*Last Updated: August 17, 2025*

## Overview

This guide covers the comprehensive testing strategy for NiFi workflow UI components, integrated through the `run.sh` script for consistency with the project's testing approach.

## Test Structure

### Test Categories

#### 1. **UI Component Tests** (`src/__tests__/ui/`)
- **Purpose**: Validate UI rendering and interactions without backend dependencies
- **Technology**: Jest + React Testing Library
- **Isolation**: All API calls mocked

#### 2. **Integration Tests** (`src/__tests__/e2e/`)
- **Purpose**: Validate UI-Backend integration with real API calls
- **Technology**: Jest + Axios + Real Backend
- **Requirements**: Running backend services

#### 3. **Legacy Tests** (`src/__tests__/`)
- **Purpose**: Maintain existing test coverage for non-workflow components
- **Status**: Maintained for backward compatibility

## Running Tests

### Through run.sh Script (Recommended)

```bash
# All UI tests
./run.sh dev:test ui

# Workflow component tests only
./run.sh dev:test ui:workflows

# UI-Backend integration tests
./run.sh dev:test ui:integration

# Legacy component tests
./run.sh dev:test ui:legacy

# Setup verification
./run.sh dev:test ui --testNamePattern="Setup Verification"
```

### Direct npm Commands (Development)

```bash
cd admin-ui

# All tests
npm run test

# Watch mode
npm run test:watch

# Coverage report
npm run test:coverage

# Specific test files
npm run test -- WorkflowComponents.test.tsx

# Test patterns
npm run test -- --testNamePattern="Workflow"
```

## Test Files & Coverage

### Core Workflow Tests

#### `WorkflowComponents.test.tsx`
- **Coverage**: All workflow UI components
- **Components**:
  - `WorkflowTemplateList` - Template listing
  - `WorkflowList` - Workflow management
  - `WorkflowCreate` - Workflow creation
  - `WorkflowEdit` - Workflow editing
  - `WorkflowShow` - Workflow details
  - `WorkflowControl` - Action controls
  - `WorkflowExecute` - EDI execution
  - `StatusBadges` - All status displays

#### `NiFiWorkflowIntegration.test.tsx`
- **Coverage**: UI-Backend integration
- **Focus Areas**:
  - API endpoint integration
  - Authentication handling
  - Data structure validation
  - Error scenario testing
  - URL encoding verification

### Test Scenarios Covered

#### ✅ **Component Rendering**
- All components render without errors
- Proper data display and formatting
- Correct button and action availability
- Status badge colors and text

#### ✅ **User Interactions**
- Form input and validation
- Button clicks and navigation
- Template selection and configuration loading
- EDI content input and execution
- File upload simulation

#### ✅ **Data Integration**
- Mock data provider integration
- API call patterns (Refine hooks)
- Data transformation and display
- Error handling and fallbacks

#### ✅ **Authentication & Security**
- JWT token handling
- Tenant isolation
- Permission-based UI rendering
- Secure API communication

#### ✅ **Error Scenarios**
- Network failures
- Invalid data responses
- Authentication errors
- Validation failures
- Template loading errors

## Test Configuration

### TestWrapper Configuration

The `TestWrapper` component provides a consistent test environment:

```typescript
<TestWrapper
  dataProvider={mockDataProvider}
  authProvider={mockAuthProvider}
  navigation={mockNavigation}
>
  <YourComponent />
</TestWrapper>
```

### Mock Data Providers

#### Default Mock Provider
```typescript
const mockDataProvider = {
  getList: jest.fn().mockResolvedValue({ data: [], total: 0 }),
  getOne: jest.fn().mockResolvedValue({ data: { id: 1 } }),
  create: jest.fn().mockResolvedValue({ data: { id: 1 } }),
  update: jest.fn().mockResolvedValue({ data: { id: 1 } }),
  deleteOne: jest.fn().mockResolvedValue({ data: { id: 1 } }),
  custom: jest.fn().mockResolvedValue({ data: {} }),
};
```

#### Custom Mock Data
```typescript
const customMockProvider = {
  ...mockDataProvider,
  getList: jest.fn().mockResolvedValue({
    data: [
      {
        template_id: 'test-template',
        name: 'Test Template',
        status: 'ACTIVE'
      }
    ],
    total: 1
  })
};
```

## Test Data Patterns

### Workflow Templates
```typescript
const mockTemplate = {
  template_id: 'global-batch-edi-processor-v1.0',
  name: 'EDI Batch Processor',
  category: 'BATCH',
  scope: 'GLOBAL',
  status: 'ACTIVE',
  version: '1.0.0',
  usage_count: 5,
  description: 'Processes EDI files in batch mode',
  configuration_schema: {
    type: 'object',
    properties: {
      input_path: { type: 'string' },
      output_path: { type: 'string' }
    }
  },
  default_configuration: {
    input_path: '/input',
    output_path: '/output'
  }
};
```

### Workflows
```typescript
const mockWorkflow = {
  workflow_id: 'workflow-123',
  name: 'Test Workflow',
  description: 'Test workflow description',
  template_id: 'global-batch-edi-processor-v1.0',
  status: 'ACTIVE',
  is_deployed: true,
  nifi_status: 'RUNNING',
  configuration: {
    input_path: '/custom/input',
    output_path: '/custom/output'
  },
  tags: ['test', 'batch'],
  created_at: '2025-08-17T10:00:00Z',
  updated_at: '2025-08-17T10:30:00Z'
};
```

## Development Workflow

### Adding New Tests

1. **Create test file** in appropriate directory:
   ```
   src/__tests__/ui/NewComponent.test.tsx
   src/__tests__/e2e/NewIntegration.test.tsx
   ```

2. **Use consistent naming**:
   ```typescript
   describe('🔄 Component Name - Test Type', () => {
     // tests here
   });
   ```

3. **Follow test patterns**:
   - Setup mock data
   - Render with TestWrapper
   - Test user interactions
   - Verify expected outcomes
   - Test error scenarios

### Running Tests During Development

```bash
# Quick component test
./run.sh dev:test ui:workflows

# Full integration test (requires backend)
./run.sh dev:test ui:integration

# Watch mode for development
cd admin-ui && npm run test:watch
```

## Continuous Integration

### CI Pipeline Integration

The tests are designed to run in Docker environments:

```bash
# In CI pipeline
./run.sh dev:test ui --coverage
./run.sh dev:test ui:workflows
./run.sh dev:test ui:integration
```

### Coverage Requirements

- **Component Tests**: 90%+ coverage
- **Integration Tests**: Key user flows covered
- **Error Scenarios**: All error paths tested

### Test Performance

- **Component Tests**: < 30 seconds
- **Integration Tests**: < 2 minutes
- **Full Test Suite**: < 5 minutes

## Debugging Tests

### Common Issues

1. **Component Not Rendering**
   ```typescript
   // Check TestWrapper setup
   await waitFor(() => {
     expect(screen.getByText('Expected Text')).toBeInTheDocument();
   });
   ```

2. **Mock Provider Not Working**
   ```typescript
   // Verify mock setup
   expect(mockDataProvider.getList).toHaveBeenCalledWith(
     expect.objectContaining({
       resource: 'workflows'
     })
   );
   ```

3. **Async Operations**
   ```typescript
   // Use waitFor for async operations
   await waitFor(() => {
     expect(screen.queryByText('Loading...')).not.toBeInTheDocument();
   });
   ```

### Debug Commands

```bash
# Run specific test with debug output
./run.sh dev:test ui --testNamePattern="Component Name" --verbose

# Check test coverage
./run.sh dev:test ui --coverage

# Run tests with watch mode for debugging
cd admin-ui && npm run test:watch -- --testNamePattern="Component Name"
```

## Best Practices

### Test Organization
- Group related tests in describe blocks
- Use descriptive test names
- Test one concept per test case
- Include positive and negative scenarios

### Mock Data
- Use realistic data structures
- Test with empty states
- Include error scenarios
- Match backend response formats

### Assertions
- Be specific with expectations
- Test user-visible behavior
- Verify API call patterns
- Check error handling

### Performance
- Use efficient selectors
- Minimize DOM queries
- Clean up after tests
- Avoid unnecessary renders

## Troubleshooting

### Test Failures

1. **Backend Connection Issues**
   ```bash
   # Ensure backend is running
   ./run.sh dev:start
   
   # Check backend health
   curl http://localhost:8000/health
   ```

2. **Docker Issues**
   ```bash
   # Rebuild containers
   ./run.sh dev:clean
   ./run.sh dev:build
   ```

3. **Test Data Issues**
   ```bash
   # Reset test database
   ./run.sh dev:setup:seed
   ```

### Getting Help

- Check test output for specific error messages
- Review component props and mock data
- Verify TestWrapper configuration
- Check console for runtime errors
- Review backend logs for integration tests

---

This testing strategy ensures comprehensive coverage of all NiFi workflow UI functionality while maintaining consistency with the project's testing infrastructure.