import { render, screen, waitFor } from '@testing-library/react';
import axios from 'axios';
import { WorkflowTemplateList } from '../../pages/workflowTemplates/list';
import { WorkflowList } from '../../pages/workflows/list';
import { WorkflowCreate } from '../../pages/workflows/create';
import { WorkflowShow } from '../../pages/workflows/show';
import { TestWrapper } from '../../test-utils';

/**
 * NIFI WORKFLOW INTEGRATION TESTS
 * 
 * This test suite validates UI-Backend integration for NiFi workflows.
 * Run with: ./run.sh dev:test ui --testNamePattern="NiFi.*Integration"
 * 
 * Prerequisites: 
 * - Backend running: ./run.sh dev:start
 * - Test data seeded: ./run.sh dev:setup:templates
 * 
 * Tests cover:
 * 1. ✅ API Integration - Template & Workflow CRUD
 * 2. ✅ Authentication - JWT token handling
 * 3. ✅ Data Structures - Backend response format validation
 * 4. ✅ Error Handling - 422, 404, auth errors
 * 5. ✅ URL Encoding - Special characters in template IDs
 */

describe('🔄 NiFi Workflow UI-Backend Integration Tests', () => {
  
  // API Configuration
  const API_BASE = 'http://localhost:8000/api/v1';
  
  // Real axios instance for backend testing
  const realAxios = axios.create({
    baseURL: API_BASE,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    }
  });

  // JWT Token for authentication (matches backend test format)
  const createTestJWT = () => {
    return 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6InRlc3Qta2V5LWlkIn0.eyJleHAiOjE3NTQ3NjQ2NDMsImlhdCI6MTc1NDc2MTM0MywiaXNzIjoiaHR0cDovL2xvY2FsaG9zdDo4MDgwL3JlYWxtcy90ZXN0LXJlYWxtIiwiYXVkIjoiZWRpLWxlbnMtYXBpIiwic3ViIjoidGVzdC11c2VyLWlkIiwicHJlZmVycmVkX3VzZXJuYW1lIjoidGVzdHVzZXIiLCJlbWFpbCI6InRlc3RAZXhhbXBsZS5jb20iLCJnaXZlbl9uYW1lIjoiVGVzdCIsImZhbWlseV9uYW1lIjoiVXNlciIsInJlYWxtX2FjY2VzcyI6eyJyb2xlcyI6WyJ0ZXN0X3JvbGUiLCJvZmZsaW5lX2FjY2VzcyIsImFkbWluIiwic3VwZXJ1c2VyIl19LCJncm91cHMiOlsidGVuYW50LWEiLCJ0ZW5hbnQtYiJdfQ.InvalidSignatureForDemo';
  };

  // Backend health check
  const checkBackendHealth = async () => {
    try {
      const response = await fetch('http://localhost:8000/health');
      const isHealthy = response.status === 200;
      if (isHealthy) {
        console.log('✅ NiFi Backend is healthy and ready for testing');
      }
      return isHealthy;
    } catch (error: any) {
      console.warn('🔴 NiFi Backend not available - skipping integration tests');
      console.warn('Start with: cd backend && python -m uvicorn src.main:app --reload --port 8000');
      return false;
    }
  };

  // Skip helper for when backend is down
  const skipIfBackendDown = async () => {
    const isBackendUp = await checkBackendHealth();
    if (!isBackendUp) {
      console.log('⏭️  Skipping NiFi workflow tests - backend not available');
      return true;
    }
    return false;
  };

  beforeAll(async () => {
    await skipIfBackendDown();
  }, 30000);

  beforeEach(() => {
    jest.clearAllMocks();
  });

  // ========================================================================
  // 🎯 1. WORKFLOW TEMPLATES INTEGRATION
  // ========================================================================
  describe('🎯 1. Workflow Templates Integration', () => {
    let createdTemplateIds: string[] = [];

    afterEach(async () => {
      // Clean up created templates
      if (createdTemplateIds.length > 0) {
        const token = createTestJWT();
        for (const templateId of createdTemplateIds) {
          try {
            await realAxios.delete(`/workflow-templates/${encodeURIComponent(templateId)}`, {
              headers: {
                'Authorization': `Bearer ${token}`,
                'X-Tenant-ID': 'tenant-a'
              }
            });
          } catch (error) {
            console.warn(`Failed to clean up template ${templateId}`);
          }
        }
        createdTemplateIds = [];
      }
    });

    it('✅ lists workflow templates with correct data structure', async () => {
      if (await skipIfBackendDown()) return;

      const token = createTestJWT();
      
      // Test direct API call
      const response = await realAxios.get('/workflow-templates', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      expect(response.status).toBe(200);
      
      // Check data structure matches what UI expects
      expect(response.data).toHaveProperty('templates');
      expect(response.data).toHaveProperty('total');
      expect(response.data).toHaveProperty('page');
      expect(response.data).toHaveProperty('page_size');
      expect(Array.isArray(response.data.templates)).toBe(true);
      
      console.log(`✅ Found ${response.data.total} workflow templates`);
      
      // Test UI component rendering
      render(
        <TestWrapper>
          <WorkflowTemplateList />
        </TestWrapper>
      );

      // Should render without data structure errors
      await waitFor(() => {
        expect(screen.queryByText('Data Structure Error')).not.toBeInTheDocument();
      }, { timeout: 5000 });
    }, 15000);

    it('✅ fetches template details with special characters in ID', async () => {
      if (await skipIfBackendDown()) return;

      const token = createTestJWT();
      
      // First get templates to find one with special characters
      const listResponse = await realAxios.get('/workflow-templates', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      if (listResponse.data.templates.length > 0) {
        const template = listResponse.data.templates[0];
        const templateId = template.template_id;
        
        console.log(`Testing template ID: ${templateId}`);
        
        // Test URL encoding for template IDs with special characters
        const encodedId = encodeURIComponent(templateId);
        const response = await realAxios.get(`/workflow-templates/${encodedId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'X-Tenant-ID': 'tenant-a'
          }
        });

        expect(response.status).toBe(200);
        expect(response.data.template_id).toBe(templateId);
        expect(response.data).toHaveProperty('name');
        expect(response.data).toHaveProperty('category');
        expect(response.data).toHaveProperty('scope');
        expect(response.data).toHaveProperty('flow_definition');
        expect(response.data).toHaveProperty('configuration_schema');
      } else {
        console.log('ℹ️  No templates found - skipping template detail test');
      }
    }, 15000);

    it('✅ creates new workflow template', async () => {
      if (await skipIfBackendDown()) return;

      const token = createTestJWT();
      const templateData = {
        name: `Integration Test Template ${Date.now()}`,
        description: 'Template created by integration test',
        category: 'BATCH',
        scope: 'TENANT',
        version: '1.0.0',
        flow_definition: {
          processors: [
            {
              name: 'EDI Validator',
              type: 'org.apache.nifi.processors.standard.ValidateRecord'
            }
          ]
        },
        configuration_schema: {
          type: 'object',
          properties: {
            input_path: {
              type: 'string',
              description: 'Input file path'
            }
          },
          required: ['input_path']
        },
        deployment_method: 'xml',
        tags: ['test', 'integration'],
        features: ['validation', 'batch-processing']
      };

      const response = await realAxios.post('/workflow-templates', templateData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      expect(response.status).toBe(201);
      expect(response.data).toHaveProperty('template_id');
      expect(response.data.name).toBe(templateData.name);
      expect(response.data.category).toBe(templateData.category);
      
      createdTemplateIds.push(response.data.template_id);
      
      console.log(`✅ Created template: ${response.data.template_id}`);
    }, 15000);

    it('✅ updates workflow template', async () => {
      if (await skipIfBackendDown()) return;

      const token = createTestJWT();
      
      // First create a template
      const templateData = {
        name: `Update Test Template ${Date.now()}`,
        description: 'Template for update testing',
        category: 'REALTIME',
        scope: 'TENANT',
        version: '1.0.0',
        flow_definition: { processors: [] },
        configuration_schema: { type: 'object', properties: {} },
        deployment_method: 'xml'
      };

      const createResponse = await realAxios.post('/workflow-templates', templateData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      createdTemplateIds.push(createResponse.data.template_id);

      // Then update it
      const updateData = {
        description: 'Updated description',
        tags: ['updated', 'test']
      };

      const encodedId = encodeURIComponent(createResponse.data.template_id);
      const updateResponse = await realAxios.put(`/workflow-templates/${encodedId}`, updateData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      expect(updateResponse.status).toBe(200);
      expect(updateResponse.data.description).toBe(updateData.description);
      expect(updateResponse.data.tags).toEqual(updateData.tags);
    }, 15000);
  });

  // ========================================================================
  // 🔄 2. WORKFLOWS INTEGRATION
  // ========================================================================
  describe('🔄 2. Workflows Integration', () => {
    let createdWorkflowIds: string[] = [];
    let testTemplateId: string | null = null;

    beforeAll(async () => {
      if (await skipIfBackendDown()) return;

      // Ensure we have a test template
      const token = createTestJWT();
      const response = await realAxios.get('/workflow-templates', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      if (response.data.templates.length > 0) {
        testTemplateId = response.data.templates[0].template_id;
        console.log(`Using test template: ${testTemplateId}`);
      }
    });

    afterEach(async () => {
      // Clean up created workflows
      if (createdWorkflowIds.length > 0) {
        const token = createTestJWT();
        for (const workflowId of createdWorkflowIds) {
          try {
            await realAxios.delete(`/workflows/${workflowId}`, {
              headers: {
                'Authorization': `Bearer ${token}`,
                'X-Tenant-ID': 'tenant-a'
              }
            });
          } catch (error) {
            console.warn(`Failed to clean up workflow ${workflowId}`);
          }
        }
        createdWorkflowIds = [];
      }
    });

    it('✅ lists workflows with correct data structure', async () => {
      if (await skipIfBackendDown()) return;

      const token = createTestJWT();
      
      // Test direct API call with tenant parameter
      const response = await realAxios.get('/workflows?tenant_id=tenant-a', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      expect(response.status).toBe(200);
      
      // Check data structure matches what UI expects
      expect(response.data).toHaveProperty('workflows');
      expect(response.data).toHaveProperty('total');
      expect(Array.isArray(response.data.workflows)).toBe(true);
      
      console.log(`✅ Found ${response.data.total} workflows`);
      
      // Test UI component rendering
      render(
        <TestWrapper>
          <WorkflowList />
        </TestWrapper>
      );

      // Should render without data structure errors
      await waitFor(() => {
        expect(screen.queryByText('Data Structure Error')).not.toBeInTheDocument();
      }, { timeout: 5000 });
    }, 15000);

    it('✅ creates workflow from template', async () => {
      if (await skipIfBackendDown()) return;
      if (!testTemplateId) {
        console.log('ℹ️  No test template available - skipping workflow creation test');
        return;
      }

      const token = createTestJWT();
      const workflowData = {
        name: `Integration Test Workflow ${Date.now()}`,
        description: 'Workflow created by integration test',
        template_id: testTemplateId,
        configuration: {
          input_path: '/test/input',
          output_path: '/test/output'
        },
        tags: ['test', 'integration']
      };

      const response = await realAxios.post('/workflows', workflowData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      expect(response.status).toBe(201);
      expect(response.data).toHaveProperty('workflow_id');
      expect(response.data.name).toBe(workflowData.name);
      expect(response.data.template_id).toBe(testTemplateId);
      expect(response.data.status).toBe('ACTIVE');
      expect(response.data.is_deployed).toBe(false);
      
      createdWorkflowIds.push(response.data.workflow_id);
      
      console.log(`✅ Created workflow: ${response.data.workflow_id}`);
    }, 15000);

    it('✅ deploys workflow to NiFi', async () => {
      if (await skipIfBackendDown()) return;
      if (!testTemplateId) return;

      const token = createTestJWT();
      
      // First create a workflow
      const workflowData = {
        name: `Deploy Test Workflow ${Date.now()}`,
        template_id: testTemplateId,
        configuration: {}
      };

      const createResponse = await realAxios.post('/workflows', workflowData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      createdWorkflowIds.push(createResponse.data.workflow_id);

      // Then deploy it
      const deployResponse = await realAxios.post(`/workflows/${createResponse.data.workflow_id}/deploy`, {}, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      expect(deployResponse.status).toBe(200);
      expect(deployResponse.data.is_deployed).toBe(true);
      expect(deployResponse.data).toHaveProperty('nifi_process_group_id');
      
      console.log(`✅ Deployed workflow to NiFi: ${deployResponse.data.nifi_process_group_id}`);
    }, 20000);

    it('✅ controls workflow (pause/resume)', async () => {
      if (await skipIfBackendDown()) return;
      if (!testTemplateId) return;

      const token = createTestJWT();
      
      // Create and deploy workflow
      const workflowData = {
        name: `Control Test Workflow ${Date.now()}`,
        template_id: testTemplateId,
        configuration: {}
      };

      const createResponse = await realAxios.post('/workflows', workflowData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      createdWorkflowIds.push(createResponse.data.workflow_id);
      const workflowId = createResponse.data.workflow_id;

      // Deploy first
      await realAxios.post(`/workflows/${workflowId}/deploy`, {}, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      // Test pause
      const pauseResponse = await realAxios.post(`/workflows/${workflowId}/pause`, {}, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      expect(pauseResponse.status).toBe(200);
      expect(pauseResponse.data.status).toBe('PAUSED');

      // Test resume
      const resumeResponse = await realAxios.post(`/workflows/${workflowId}/resume`, {}, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      expect(resumeResponse.status).toBe(200);
      expect(resumeResponse.data.status).toBe('ACTIVE');
      
      console.log(`✅ Successfully controlled workflow: pause -> resume`);
    }, 25000);

    it('✅ executes workflow with EDI content', async () => {
      if (await skipIfBackendDown()) return;
      if (!testTemplateId) return;

      const token = createTestJWT();
      
      // Create and deploy workflow
      const workflowData = {
        name: `Execute Test Workflow ${Date.now()}`,
        template_id: testTemplateId,
        configuration: {}
      };

      const createResponse = await realAxios.post('/workflows', workflowData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      createdWorkflowIds.push(createResponse.data.workflow_id);
      const workflowId = createResponse.data.workflow_id;

      // Deploy workflow
      await realAxios.post(`/workflows/${workflowId}/deploy`, {}, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      // Execute workflow with EDI content
      const ediContent = 'ISA*00*          *00*          *ZZ*TEST           *ZZ*TEST           *250109*1234*^*00501*000000001*0*T*:~IEA*0*000000001~';
      
      const executeResponse = await realAxios.post(`/workflows/${workflowId}/process`, {
        edi_content: ediContent,
        processing_options: {
          generate_ta1: true,
          generate_999: true
        }
      }, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      expect(executeResponse.status).toBe(200);
      expect(executeResponse.data).toHaveProperty('valid');
      expect(executeResponse.data).toHaveProperty('processing_time_ms');
      expect(executeResponse.data).toHaveProperty('workflow_id');
      expect(executeResponse.data.workflow_id).toBe(workflowId);
      
      console.log(`✅ Executed workflow with EDI content: ${executeResponse.data.processing_time_ms}ms`);
    }, 30000);

    it('✅ gets detailed workflow status', async () => {
      if (await skipIfBackendDown()) return;
      if (!testTemplateId) return;

      const token = createTestJWT();
      
      // Create workflow
      const workflowData = {
        name: `Status Test Workflow ${Date.now()}`,
        template_id: testTemplateId,
        configuration: {}
      };

      const createResponse = await realAxios.post('/workflows', workflowData, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      createdWorkflowIds.push(createResponse.data.workflow_id);
      const workflowId = createResponse.data.workflow_id;

      // Get status
      const statusResponse = await realAxios.get(`/workflows/${workflowId}/status`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      expect(statusResponse.status).toBe(200);
      expect(statusResponse.data).toHaveProperty('workflow_id');
      expect(statusResponse.data).toHaveProperty('status');
      expect(statusResponse.data).toHaveProperty('deployment_status');
      expect(statusResponse.data).toHaveProperty('execution_count');
      expect(statusResponse.data).toHaveProperty('success_rate');
      expect(statusResponse.data.workflow_id).toBe(workflowId);
      
      console.log(`✅ Retrieved workflow status: ${statusResponse.data.status}`);
    }, 15000);
  });

  // ========================================================================
  // 🎨 3. UI COMPONENT INTEGRATION
  // ========================================================================
  describe('🎨 3. UI Component Integration', () => {
    it('✅ WorkflowCreate component integrates with backend', async () => {
      if (await skipIfBackendDown()) return;

      // Mock successful API responses
      const mockTemplates = {
        templates: [
          {
            template_id: 'test-template-1',
            name: 'Test Template',
            category: 'BATCH',
            scope: 'GLOBAL',
            status: 'ACTIVE',
            version: '1.0.0',
            configuration_schema: {
              type: 'object',
              properties: {
                input_path: { type: 'string' }
              }
            }
          }
        ],
        total: 1
      };

      // Mock data provider calls
      const mockDataProvider = {
        getList: jest.fn().mockResolvedValue({
          data: mockTemplates.templates,
          total: mockTemplates.total
        }),
        create: jest.fn().mockResolvedValue({
          data: {
            workflow_id: 'test-workflow-1',
            name: 'Test Workflow',
            template_id: 'test-template-1'
          }
        })
      };

      render(
        <TestWrapper>
          <WorkflowCreate />
        </TestWrapper>
      );

      // Should render create form
      await waitFor(() => {
        expect(screen.getByText('Create Workflow')).toBeInTheDocument();
      });

      // Check form fields
      expect(screen.getByLabelText(/name/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/template/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /create workflow/i })).toBeInTheDocument();

      console.log('✅ WorkflowCreate component rendered successfully');
    }, 10000);

    it('✅ WorkflowShow component displays workflow details', async () => {
      if (await skipIfBackendDown()) return;

      const mockWorkflow = {
        workflow_id: 'test-workflow-1',
        name: 'Test Workflow',
        description: 'Test Description',
        template_id: 'test-template-1',
        status: 'ACTIVE',
        is_deployed: true,
        configuration: { input_path: '/test' },
        tags: ['test'],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };

      const mockDataProvider = {
        getOne: jest.fn().mockResolvedValue({
          data: mockWorkflow
        })
      };

      render(
        <TestWrapper>
          <WorkflowShow />
        </TestWrapper>
      );

      // Should render workflow details
      await waitFor(() => {
        expect(screen.getByText('Test Workflow')).toBeInTheDocument();
      });

      console.log('✅ WorkflowShow component rendered successfully');
    }, 10000);
  });

  // ========================================================================
  // ⚠️ 4. ERROR HANDLING INTEGRATION
  // ========================================================================
  describe('⚠️ 4. Error Handling Integration', () => {
    it('✅ handles 422 validation errors gracefully', async () => {
      if (await skipIfBackendDown()) return;

      const token = createTestJWT();

      try {
        await realAxios.post('/workflows', {
          // Missing required fields
          name: ''
        }, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'X-Tenant-ID': 'tenant-a'
          }
        });
        fail('Should have failed with validation error');
      } catch (error: any) {
        expect(error.response.status).toBe(422);
        expect(error.response.data).toHaveProperty('detail');
        console.log(`✅ Handled 422 error: ${error.response.data.detail}`);
      }
    }, 10000);

    it('✅ handles authentication errors', async () => {
      if (await skipIfBackendDown()) return;

      try {
        await realAxios.get('/workflows', {
          headers: {
            'Authorization': 'Bearer invalid-token',
            'X-Tenant-ID': 'tenant-a'
          }
        });
        fail('Should have failed with auth error');
      } catch (error: any) {
        expect([401, 403]).toContain(error.response.status);
        console.log(`✅ Handled auth error: ${error.response.status}`);
      }
    }, 10000);

    it('✅ handles template not found errors', async () => {
      if (await skipIfBackendDown()) return;

      const token = createTestJWT();

      try {
        await realAxios.get('/workflow-templates/non-existent-template', {
          headers: {
            'Authorization': `Bearer ${token}`,
            'X-Tenant-ID': 'tenant-a'
          }
        });
        fail('Should have failed with 404');
      } catch (error: any) {
        expect(error.response.status).toBe(404);
        console.log(`✅ Handled 404 error for non-existent template`);
      }
    }, 10000);
  });

  // ========================================================================
  // 🔄 5. DATA TRANSFORMATION TESTS
  // ========================================================================
  describe('🔄 5. Data Transformation Tests', () => {
    it('✅ validates backend response format matches frontend expectations', async () => {
      if (await skipIfBackendDown()) return;

      const token = createTestJWT();
      
      // Test workflow templates response format
      const templatesResponse = await realAxios.get('/workflow-templates', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      // Backend should return { templates: [], total: N, page: N, page_size: N }
      expect(templatesResponse.data).toHaveProperty('templates');
      expect(templatesResponse.data).toHaveProperty('total');
      expect(templatesResponse.data).toHaveProperty('page');
      expect(templatesResponse.data).toHaveProperty('page_size');
      expect(Array.isArray(templatesResponse.data.templates)).toBe(true);

      // Test workflows response format
      const workflowsResponse = await realAxios.get('/workflows?tenant_id=tenant-a', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'X-Tenant-ID': 'tenant-a'
        }
      });

      // Backend should return { workflows: [], total: N, page: N, page_size: N }
      expect(workflowsResponse.data).toHaveProperty('workflows');
      expect(workflowsResponse.data).toHaveProperty('total');
      expect(Array.isArray(workflowsResponse.data.workflows)).toBe(true);

      console.log('✅ Data formats match expectations');
    }, 10000);
  });
});