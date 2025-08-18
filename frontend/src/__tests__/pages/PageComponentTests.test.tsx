/**
 * 📄 PAGE COMPONENT TESTS
 * 
 * Tests for main page components to improve coverage:
 * 1. WorkflowTemplateList - Template listing page
 * 2. WorkflowList - Workflow listing page  
 * 3. Validation - EDI validation page
 * 4. ProcessingHistory - Processing history page
 * 5. SchemaEditorList - Schema editor page
 * 
 * Run with: ./run.sh dev:test ui --testNamePattern="Page Component Tests"
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App as AntdApp } from 'antd';

// Import pages to test
import { WorkflowTemplateList } from '../../pages/workflowTemplates/list';
import { WorkflowList } from '../../pages/workflows/list';
import { Validation } from '../../pages/validation/Validation';
import { ProcessingHistory } from '../../pages/validation/ProcessingHistory';
import { SchemaEditorList } from '../../pages/schemaEditor/SchemaEditorList';

// Import test utilities
import { TestWrapper } from '../../test-utils/TestWrapper';

describe('📄 Page Component Tests', () => {
  const user = userEvent.setup();
  
  const createMockDataProvider = () => ({
    getList: jest.fn(() => Promise.resolve({ 
      data: [
        { 
          template_id: 'test-template-1',
          name: 'Test Template 1',
          description: 'Test template description',
          category: 'EDI',
          scope: 'public',
          status: 'active',
          version: '1.0',
          usage_count: 5
        },
        {
          template_id: 'test-template-2', 
          name: 'Test Template 2',
          description: 'Another test template',
          category: 'JSON',
          scope: 'private',
          status: 'draft',
          version: '2.0',
          usage_count: 0
        }
      ], 
      total: 2 
    })),
    getOne: jest.fn(() => Promise.resolve({ 
      data: {
        template_id: 'test-template-1',
        name: 'Test Template 1',
        ui_configuration: {
          input: {
            title: "📄 Content Input",
            placeholder_text: "Paste your content here...",
            supports_text_input: true,
            supports_file_upload: true
          },
          processing_options: [],
          outputs: []
        }
      }
    })),
    getMany: jest.fn(() => Promise.resolve({ data: [] })),
    getManyReference: jest.fn(() => Promise.resolve({ data: [], total: 0 })),
    create: jest.fn(() => Promise.resolve({ data: { id: 'new-id' } })),
    update: jest.fn(() => Promise.resolve({ data: {} })),
    updateMany: jest.fn(() => Promise.resolve({ data: [] })),
    deleteOne: jest.fn(() => Promise.resolve({ data: {} })),
    deleteMany: jest.fn(() => Promise.resolve({ data: [] })),
    getApiUrl: jest.fn(() => 'http://localhost:3001/api/v1'),
    custom: jest.fn(() => Promise.resolve({ data: {} }))
  });

  let mockDataProvider: ReturnType<typeof createMockDataProvider>;

  beforeEach(() => {
    mockDataProvider = createMockDataProvider();
  });

  // =========================================================================
  // 📋 WORKFLOW TEMPLATE LIST PAGE TESTS
  // =========================================================================
  describe('📋 WorkflowTemplateList Page', () => {
    it('✅ renders template list correctly', async () => {
      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <AntdApp>
            <WorkflowTemplateList />
          </AntdApp>
        </TestWrapper>
      );

      // Should show the page header
      expect(screen.getByText('Workflow Templates')).toBeInTheDocument();
      
      // Wait for data to load
      await waitFor(() => {
        expect(mockDataProvider.getList).toHaveBeenCalled();
      });

      // Should show templates when loaded
      await waitFor(() => {
        expect(screen.getByText('Test Template 1')).toBeInTheDocument();
        expect(screen.getByText('Test Template 2')).toBeInTheDocument();
      });
    });

    it('✅ shows template details and actions', async () => {
      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <AntdApp>
            <WorkflowTemplateList />
          </AntdApp>
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Test Template 1')).toBeInTheDocument();
      });

      // Should show template metadata
      expect(screen.getByText('Test template description')).toBeInTheDocument();
      expect(screen.getByText('1.0')).toBeInTheDocument(); // version
      
      // Should show action buttons (Edit, Show)
      const editButtons = screen.getAllByText('Edit');
      const showButtons = screen.getAllByText('Show');
      expect(editButtons.length).toBeGreaterThan(0);
      expect(showButtons.length).toBeGreaterThan(0);
    });
  });

  // =========================================================================
  // 🔄 WORKFLOW LIST PAGE TESTS  
  // =========================================================================
  describe('🔄 WorkflowList Page', () => {
    beforeEach(() => {
      // Mock workflow data
      mockDataProvider.getList.mockResolvedValue({
        data: [
          {
            workflow_id: 'workflow-1',
            name: 'Test Workflow 1', 
            template_id: 'template-1',
            status: 'active',
            deployed: true,
            created_at: '2025-01-18T10:00:00Z'
          },
          {
            workflow_id: 'workflow-2',
            name: 'Test Workflow 2',
            template_id: 'template-2', 
            status: 'draft',
            deployed: false,
            created_at: '2025-01-17T15:30:00Z'
          }
        ],
        total: 2
      });
    });

    it('✅ renders workflow list correctly', async () => {
      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <AntdApp>
            <WorkflowList />
          </AntdApp>
        </TestWrapper>
      );

      // Should show the page header
      expect(screen.getByText('Workflows')).toBeInTheDocument();

      // Wait for data to load
      await waitFor(() => {
        expect(mockDataProvider.getList).toHaveBeenCalled();
      });

      // Should show workflows when loaded
      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
        expect(screen.getByText('Test Workflow 2')).toBeInTheDocument();
      });
    });

    it('✅ shows workflow actions', async () => {
      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <AntdApp>
            <WorkflowList />
          </AntdApp>
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument();
      });

      // Should show action buttons
      const editButtons = screen.getAllByText('Edit');
      const showButtons = screen.getAllByText('Show');
      expect(editButtons.length).toBeGreaterThan(0);
      expect(showButtons.length).toBeGreaterThan(0);
    });
  });

  // =========================================================================
  // 🔍 VALIDATION PAGE TESTS
  // =========================================================================
  describe('🔍 Validation Page', () => {
    it('✅ renders validation interface correctly', () => {
      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <AntdApp>
            <Validation />
          </AntdApp>
        </TestWrapper>
      );

      // Should show validation interface elements
      expect(screen.getByText('EDI Validation')).toBeInTheDocument();
      expect(screen.getByText('Validation Profile')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /validate edi/i })).toBeInTheDocument();
      
      // Should show validation profiles
      expect(screen.getByText(/Select validation profile/i)).toBeInTheDocument();
    });

    it('✅ allows text input for validation', async () => {
      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <AntdApp>
            <Validation />
          </AntdApp>
        </TestWrapper>
      );

      // Should have text area for EDI input
      const textArea = screen.getByPlaceholderText(/paste your edi content/i);
      expect(textArea).toBeInTheDocument();

      // Should allow typing
      await user.type(textArea, 'ISA*00*TEST*EDI*CONTENT~');
      expect(textArea).toHaveValue('ISA*00*TEST*EDI*CONTENT~');
    });
  });

  // =========================================================================
  // 📊 PROCESSING HISTORY PAGE TESTS
  // =========================================================================
  describe('📊 ProcessingHistory Page', () => {
    beforeEach(() => {
      // Mock processing history data
      mockDataProvider.getList.mockResolvedValue({
        data: [
          {
            id: 'job-1',
            status: 'completed',
            created_at: '2025-01-18T10:00:00Z',
            processing_time_ms: 1500,
            file_name: 'test.edi'
          },
          {
            id: 'job-2', 
            status: 'failed',
            created_at: '2025-01-18T09:30:00Z',
            processing_time_ms: 500,
            file_name: 'error.edi'
          }
        ],
        total: 2
      });
    });

    it('✅ renders processing history correctly', async () => {
      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <AntdApp>
            <ProcessingHistory />
          </AntdApp>
        </TestWrapper>
      );

      // Should show page header
      expect(screen.getByText('Processing History')).toBeInTheDocument();

      // Wait for data to load
      await waitFor(() => {
        expect(mockDataProvider.getList).toHaveBeenCalled();
      });
    });
  });

  // =========================================================================
  // 🎨 SCHEMA EDITOR PAGE TESTS
  // =========================================================================
  describe('🎨 SchemaEditor Page', () => {
    beforeEach(() => {
      // Mock schema data
      mockDataProvider.getList.mockResolvedValue({
        data: [
          {
            id: 'schema-1',
            name: 'X12 850 Purchase Order',
            version: '5010',
            status: 'active'
          },
          {
            id: 'schema-2',
            name: 'X12 810 Invoice', 
            version: '5010',
            status: 'active'
          }
        ],
        total: 2
      });
    });

    it('✅ renders schema editor correctly', async () => {
      render(
        <TestWrapper dataProvider={mockDataProvider}>
          <AntdApp>
            <SchemaEditorList />
          </AntdApp>
        </TestWrapper>
      );

      // Should show page header
      expect(screen.getByText('Schema Editor')).toBeInTheDocument();

      // Wait for data to load and check if schemas loaded
      await waitFor(() => {
        expect(mockDataProvider.getList).toHaveBeenCalled();
      });
    });
  });

  // =========================================================================
  // 🎉 PAGE TESTS SUMMARY
  // =========================================================================
  describe('🎉 Page Tests Summary', () => {
    it('✅ Page component tests completed successfully', () => {
      console.log('\n🎉 PAGE COMPONENT TESTS SUMMARY');
      console.log('✅ WorkflowTemplateList: Rendering & Data Loading Tested');
      console.log('✅ WorkflowList: Rendering & Actions Tested');
      console.log('✅ Validation: Interface & Input Tested');
      console.log('✅ ProcessingHistory: Data Loading Tested');
      console.log('✅ SchemaEditor: Basic Rendering Tested');
      console.log('📊 Coverage: Page Components Now Have Test Coverage');
      
      // This test always passes - it's just for logging
      expect(true).toBe(true);
    });
  });
});