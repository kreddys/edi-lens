/**
 * 🔄 WORKFLOW COMPONENTS UI TESTS
 * 
 * This test suite validates the NiFi workflow UI components work correctly.
 * Tests are designed to run through run.sh and cover all workflow functionality.
 * 
 * Coverage:
 * ✅ WorkflowTemplateList - Template listing and data handling
 * ✅ WorkflowList - Workflow listing with actions
 * ✅ WorkflowCreate - Workflow creation flow
 * ✅ WorkflowEdit - Workflow editing functionality
 * ✅ WorkflowShow - Workflow details and execution
 * ✅ WorkflowControl - Action buttons and controls
 * ✅ WorkflowExecute - EDI execution interface
 * ✅ StatusBadges - Status display components
 * 
 * Run with: ./run.sh dev:test ui --testNamePattern="Workflow"
 */

import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TestWrapper } from '../../test-utils';

// Import workflow components
import { WorkflowTemplateList } from '../../pages/workflowTemplates/list';
import { WorkflowList } from '../../pages/workflows/list';
import { WorkflowCreate } from '../../pages/workflows/create';
import { WorkflowEdit } from '../../pages/workflows/edit';
import { WorkflowShow } from '../../pages/workflows/show';
import { WorkflowControl } from '../../components/workflow/WorkflowControl';
import { WorkflowExecute } from '../../components/workflow/WorkflowExecute';
import { 
  WorkflowStatusBadge, 
  DeploymentBadge, 
  TemplateStatusBadge,
  ScopeBadge,
  CategoryBadge 
} from '../../components/workflow/StatusBadges';

// Mock the data provider to avoid actual API calls
const mockDataProvider = {
  getList: jest.fn(),
  getOne: jest.fn(),
  create: jest.fn(),
  update: jest.fn(),
  deleteOne: jest.fn(),
  custom: jest.fn(),
};

// Mock navigation
const mockNavigation = {
  show: jest.fn(),
  list: jest.fn(),
  edit: jest.fn(),
  create: jest.fn(),
  clone: jest.fn(),
};

// Mock auth provider
const mockAuthProvider = {
  login: jest.fn(),
  logout: jest.fn(),
  check: jest.fn().mockResolvedValue({ authenticated: true }),
  getPermissions: jest.fn(),
  getIdentity: jest.fn(),
};

describe('🔄 NiFi Workflow Components UI Tests', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Setup default mock responses
    mockDataProvider.getList.mockResolvedValue({
      data: [],
      total: 0,
    });
    
    mockDataProvider.getOne.mockResolvedValue({
      data: {
        workflow_id: 'test-workflow-1',
        name: 'Test Workflow',
        template_id: 'test-template-1',
        status: 'ACTIVE',
        is_deployed: false,
        configuration: {},
        tags: ['test'],
      },
    });
    
    mockDataProvider.create.mockResolvedValue({
      data: { workflow_id: 'new-workflow-1' },
    });
    
    mockDataProvider.update.mockResolvedValue({
      data: { workflow_id: 'test-workflow-1' },
    });
    
    mockDataProvider.custom.mockResolvedValue({
      data: {
        template_id: 'test-template-1',
        name: 'Test Template',
        configuration_schema: {
          type: 'object',
          properties: {
            input_path: { type: 'string' }
          }
        },
        default_configuration: {
          input_path: '/default/path'
        }
      },
    });
  });

  // ========================================================================
  // 📋 WORKFLOW TEMPLATE COMPONENTS
  // ========================================================================
  describe('📋 Workflow Template Components', () => {
    it('renders WorkflowTemplateList without errors', async () => {
      mockDataProvider.getList.mockResolvedValue({
        data: [
          {
            template_id: 'template-1',
            name: 'EDI Batch Processor',
            category: 'BATCH',
            scope: 'GLOBAL',
            status: 'ACTIVE',
            version: '1.0.0',
            usage_count: 5,
            description: 'Test template'
          }
        ],
        total: 1,
      });

      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowTemplateList />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('EDI Batch Processor')).toBeInTheDocument();
      });

      expect(screen.getByText('Test template')).toBeInTheDocument();
      expect(screen.getByText('5 workflows')).toBeInTheDocument();
    });

    it('handles empty template list gracefully', async () => {
      mockDataProvider.getList.mockResolvedValue({
        data: [],
        total: 0,
      });

      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowTemplateList />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.queryByText('Data Structure Error')).not.toBeInTheDocument();
      });
    });

    it('renders template status badges correctly', () => {
      render(
        <div>
          <TemplateStatusBadge status="ACTIVE" />
          <TemplateStatusBadge status="DEPRECATED" />
          <ScopeBadge scope="GLOBAL" />
          <ScopeBadge scope="TENANT" />
          <CategoryBadge category="BATCH" />
          <CategoryBadge category="REALTIME" />
        </div>
      );

      expect(screen.getByText('Active')).toBeInTheDocument();
      expect(screen.getByText('Deprecated')).toBeInTheDocument();
      expect(screen.getByText('Global')).toBeInTheDocument();
      expect(screen.getByText('Tenant')).toBeInTheDocument();
      expect(screen.getByText('Batch')).toBeInTheDocument();
      expect(screen.getByText('Real-time')).toBeInTheDocument();
    });
  });

  // ========================================================================
  // ⚙️ WORKFLOW MANAGEMENT COMPONENTS
  // ========================================================================
  describe('⚙️ Workflow Management Components', () => {
    it('renders WorkflowList with actions', async () => {
      mockDataProvider.getList.mockResolvedValue({
        data: [
          {
            workflow_id: 'workflow-1',
            name: 'Test Workflow',
            description: 'Test workflow description',
            template_id: 'template-1',
            status: 'ACTIVE',
            is_deployed: true,
            nifi_status: 'RUNNING',
            tags: ['test'],
          }
        ],
        total: 1,
      });

      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowList />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Test Workflow')).toBeInTheDocument();
      });

      expect(screen.getByText('Test workflow description')).toBeInTheDocument();
      expect(screen.getByText('RUNNING')).toBeInTheDocument();
      
      // Check for action buttons
      expect(screen.getByTitle('Pause')).toBeInTheDocument();
      expect(screen.getByTitle('Restart')).toBeInTheDocument();
      expect(screen.getByTitle('Undeploy')).toBeInTheDocument();
    });

    it('shows deploy button for undeployed workflows', async () => {
      mockDataProvider.getList.mockResolvedValue({
        data: [
          {
            workflow_id: 'workflow-1',
            name: 'Undeployed Workflow',
            status: 'ACTIVE',
            is_deployed: false,
          }
        ],
        total: 1,
      });

      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowList />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByTitle('Deploy')).toBeInTheDocument();
      });
    });

    it('renders workflow status badges correctly', () => {
      render(
        <div>
          <WorkflowStatusBadge status="ACTIVE" />
          <WorkflowStatusBadge status="PAUSED" />
          <WorkflowStatusBadge status="ERROR" />
          <DeploymentBadge isDeployed={true} />
          <DeploymentBadge isDeployed={false} />
        </div>
      );

      expect(screen.getByText('Active')).toBeInTheDocument();
      expect(screen.getByText('Paused')).toBeInTheDocument();
      expect(screen.getByText('Error')).toBeInTheDocument();
      expect(screen.getByText('Deployed')).toBeInTheDocument();
      expect(screen.getByText('Not Deployed')).toBeInTheDocument();
    });
  });

  // ========================================================================
  // 📝 WORKFLOW CREATION & EDITING
  // ========================================================================
  describe('📝 Workflow Creation & Editing', () => {
    it('renders WorkflowCreate form', async () => {
      // Mock template selection data
      mockDataProvider.getList.mockResolvedValue({
        data: [
          {
            template_id: 'template-1',
            name: 'Test Template',
            status: 'ACTIVE',
          }
        ],
        total: 1,
      });

      render(
        <TestWrapper dataProvider={mockDataProvider} navigation={mockNavigation}>
          <WorkflowCreate />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Create Workflow')).toBeInTheDocument();
      });

      expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/template/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /create workflow/i })).toBeInTheDocument();
    });

    it('loads template configuration when template is selected', async () => {
      mockDataProvider.getList.mockResolvedValue({
        data: [
          {
            template_id: 'template-1',
            name: 'Test Template',
            status: 'ACTIVE',
          }
        ],
        total: 1,
      });

      render(
        <TestWrapper dataProvider={mockDataProvider} navigation={mockNavigation}>
          <WorkflowCreate />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/template/i)).toBeInTheDocument();
      });

      // Simulate template selection
      const templateSelect = screen.getByLabelText(/template/i);
      fireEvent.mouseDown(templateSelect);
      
      await waitFor(() => {
        if (screen.queryByText('Test Template')) {
          fireEvent.click(screen.getByText('Test Template'));
        }
      });

      // Should call custom hook to fetch template config
      expect(mockDataProvider.custom).toHaveBeenCalledWith(
        expect.objectContaining({
          url: expect.stringContaining('/workflow-templates/'),
          method: 'get'
        })
      );
    });

    it('renders WorkflowEdit form with existing data', async () => {
      render(
        <TestWrapper dataProvider={mockDataProvider} navigation={mockNavigation}>
          <WorkflowEdit />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Edit Workflow')).toBeInTheDocument();
      });

      expect(screen.getByRole('button', { name: /update workflow/i })).toBeInTheDocument();
    });
  });

  // ========================================================================
  // 👁️ WORKFLOW DETAILS & EXECUTION
  // ========================================================================
  describe('👁️ Workflow Details & Execution', () => {
    it('renders WorkflowShow with tabs', async () => {
      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowShow />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Test Workflow')).toBeInTheDocument();
      });

      expect(screen.getByText('Details')).toBeInTheDocument();
      expect(screen.getByText('Execute')).toBeInTheDocument();
    });

    it('renders WorkflowControl with correct buttons for deployed workflow', () => {
      const mockOnActionComplete = jest.fn();

      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowControl
            workflowId="test-workflow-1"
            isDeployed={true}
            status="ACTIVE"
            onActionComplete={mockOnActionComplete}
          />
        </TestWrapper>
      );

      expect(screen.getByText('Pause')).toBeInTheDocument();
      expect(screen.getByText('Restart')).toBeInTheDocument();
      expect(screen.getByText('Undeploy')).toBeInTheDocument();
    });

    it('renders WorkflowControl with deploy button for undeployed workflow', () => {
      const mockOnActionComplete = jest.fn();

      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowControl
            workflowId="test-workflow-1"
            isDeployed={false}
            status="ACTIVE"
            onActionComplete={mockOnActionComplete}
          />
        </TestWrapper>
      );

      expect(screen.getByText('Deploy')).toBeInTheDocument();
    });

    it('renders WorkflowExecute interface', () => {
      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowExecute workflowId="test-workflow-1" />
        </TestWrapper>
      );

      expect(screen.getByText('Execute Workflow')).toBeInTheDocument();
      expect(screen.getByText('EDI Input')).toBeInTheDocument();
      expect(screen.getByText('Execution Results')).toBeInTheDocument();
      expect(screen.getByPlaceholderText(/paste your edi content/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /execute workflow/i })).toBeInTheDocument();
    });

    it('handles EDI content input in WorkflowExecute', async () => {
      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowExecute workflowId="test-workflow-1" />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText(/paste your edi content/i);
      
      await user.type(textarea, 'ISA*00*TEST*EDI*CONTENT~');
      
      expect(textarea).toHaveValue('ISA*00*TEST*EDI*CONTENT~');
    });
  });

  // ========================================================================
  // 🔄 COMPONENT INTERACTIONS
  // ========================================================================
  describe('🔄 Component Interactions', () => {
    it('handles workflow action execution', async () => {
      const mockOnActionComplete = jest.fn();
      mockDataProvider.custom.mockResolvedValue({ data: { success: true } });

      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowControl
            workflowId="test-workflow-1"
            isDeployed={false}
            status="ACTIVE"
            onActionComplete={mockOnActionComplete}
          />
        </TestWrapper>
      );

      const deployButton = screen.getByText('Deploy');
      fireEvent.click(deployButton);

      await waitFor(() => {
        expect(mockDataProvider.custom).toHaveBeenCalledWith(
          expect.objectContaining({
            url: '/workflows/test-workflow-1/deploy',
            method: 'post'
          })
        );
      });
    });

    it('handles workflow execution', async () => {
      mockDataProvider.custom.mockResolvedValue({
        data: {
          valid: true,
          processing_time_ms: 150,
          workflow_id: 'test-workflow-1',
          status: 'completed'
        }
      });

      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowExecute workflowId="test-workflow-1" />
        </TestWrapper>
      );

      // Input EDI content
      const textarea = screen.getByPlaceholderText(/paste your edi content/i);
      await user.type(textarea, 'ISA*00*TEST*EDI*CONTENT~');

      // Execute workflow
      const executeButton = screen.getByRole('button', { name: /execute workflow/i });
      fireEvent.click(executeButton);

      await waitFor(() => {
        expect(mockDataProvider.custom).toHaveBeenCalledWith(
          expect.objectContaining({
            url: '/workflows/test-workflow-1/process',
            method: 'post',
            values: expect.objectContaining({
              edi_content: 'ISA*00*TEST*EDI*CONTENT~'
            })
          })
        );
      });
    });

    it('handles form submission in WorkflowCreate', async () => {
      mockDataProvider.getList.mockResolvedValue({
        data: [
          {
            template_id: 'template-1',
            name: 'Test Template',
            status: 'ACTIVE',
          }
        ],
        total: 1,
      });

      render(
        <TestWrapper dataProvider={mockDataProvider} navigation={mockNavigation}>
          <WorkflowCreate />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      });

      // Fill form
      await user.type(screen.getByLabelText(/name/i), 'New Test Workflow');
      
      // Submit form
      const createButton = screen.getByRole('button', { name: /create workflow/i });
      fireEvent.click(createButton);

      await waitFor(() => {
        expect(mockDataProvider.create).toHaveBeenCalledWith(
          expect.objectContaining({
            resource: 'workflows',
            values: expect.objectContaining({
              name: 'New Test Workflow'
            })
          })
        );
      });
    });
  });

  // ========================================================================
  // ⚠️ ERROR HANDLING
  // ========================================================================
  describe('⚠️ Error Handling', () => {
    it('handles data provider errors gracefully', async () => {
      mockDataProvider.getList.mockRejectedValue(new Error('API Error'));

      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <WorkflowList />
        </TestWrapper>
      );

      // Should not crash and should handle error gracefully
      await waitFor(() => {
        expect(screen.queryByText('Data Structure Error')).not.toBeInTheDocument();
      });
    });

    it('handles template loading errors in creation flow', async () => {
      mockDataProvider.getList.mockResolvedValue({
        data: [{ template_id: 'template-1', name: 'Test Template', status: 'ACTIVE' }],
        total: 1,
      });
      
      mockDataProvider.custom.mockRejectedValue(new Error('Template not found'));

      render(
        <TestWrapper dataProvider={mockDataProvider} navigation={mockNavigation}>
          <WorkflowCreate />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByLabelText(/template/i)).toBeInTheDocument();
      });

      // Should handle template loading error gracefully
      const templateSelect = screen.getByLabelText(/template/i);
      fireEvent.mouseDown(templateSelect);
      
      // The component should handle the error without crashing
      expect(screen.getByText('Create Workflow')).toBeInTheDocument();
    });
  });
});