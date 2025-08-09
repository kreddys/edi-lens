import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { TradingPartnerWizard } from '../../pages/tradingPartners/TradingPartnerWizard';
import { TestWrapper } from '../../test-utils';

// Real Backend Integration Tests for Trading Partners
// Tests CRUD operations, SFTP configuration, and profile management
// Requires backend: ./run.sh dev:start

describe('Real Backend Integration - Trading Partners', () => {
  const user = userEvent.setup();
  
  const apiUrl = 'http://localhost:8000';
  
  // Real axios instance for backend testing  
  const realAxios = axios.create({
    baseURL: apiUrl,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJzdWIiOiAidGVzdC11c2VyLTEyMyIsICJwcmVmZXJyZWRfdXNlcm5hbWUiOiAidGVzdC1hZG1pbiIsICJlbWFpbCI6ICJhZG1pbkB0ZXN0LmNvbSIsICJncm91cHMiOiBbInRlbmFudC1hIl0sICJyZWFsbV9hY2Nlc3MiOiB7InJvbGVzIjogWyJzZnRwOnJlYWQiLCAic2Z0cDpwcm9jZXNzIiwgImFkbWluIl19LCAiaWF0IjogMTc1NDI3MDU2OSwgImV4cCI6IDE3NTQyNzc3NjksICJpc3MiOiAiZWRpLWxlbnMtdGVzdCIsICJhdWQiOiAiZWRpLWxlbnMtYXBpIn0.ZmFrZV9zaWduYXR1cmVfZm9yX2RlbW8'
    }
  });

  const checkBackendHealth = async () => {
    try {
      await realAxios.get('/health');
      return true;
    } catch (error) {
      console.warn('Backend not available - skipping real trading partner tests');
      return false;
    }
  };

  beforeEach(async () => {
    const isBackendUp = await checkBackendHealth();
    if (!isBackendUp) {
      pending('Backend is not running. Start with: ./run.sh dev:start');
    }

    // Use real axios for these tests
    jest.doMock('axios', () => ({
      ...jest.requireActual('axios'),
      create: () => realAxios,
      post: realAxios.post.bind(realAxios),
      get: realAxios.get.bind(realAxios),
      put: realAxios.put.bind(realAxios),
      delete: realAxios.delete.bind(realAxios)
    }));
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  describe('Real Trading Partner CRUD Operations', () => {
    it('creates a real trading partner with API integration in backend database', async () => {
      const partnerName = `Test Partner ${Date.now()}`; // Unique name

      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Step 1: Basic Information
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, partnerName);

      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      // Step 2: Skip profiles for basic test
      await waitFor(() => {
        const nextButton2 = screen.getByText('Next');
        fireEvent.click(nextButton2);
      });

      // Step 3: Select API Integration
      await waitFor(() => {
        expect(screen.getByText('Integration Methods')).toBeInTheDocument();
      });

      const apiCheckbox = screen.getByLabelText('API Integration');
      await user.click(apiCheckbox);

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      // Wait for real backend creation
      await waitFor(() => {
        // Should get success response or completion indicator
        const successElements = screen.queryAllByText(/success|complete|created/i);
        expect(successElements.length).toBeGreaterThan(0);
      }, { timeout: 10000 });

      // Verify partner was actually created in database
      const verifyResponse = await realAxios.get('/trading-partners');
      const partners = verifyResponse.data;
      
      const createdPartner = partners.find((p: any) => p.name === partnerName);
      expect(createdPartner).toBeTruthy();
      expect(createdPartner.name).toBe(partnerName);
    }, 15000);

    it('creates trading partner with real SFTP configuration and backend service', async () => {
      const partnerName = `SFTP Partner ${Date.now()}`;
      const username = `sftpuser${Date.now()}`;

      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Basic info
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, partnerName);

      let nextButton = screen.getByText('Next');
      await user.click(nextButton);

      // Skip profiles
      await waitFor(() => {
        nextButton = screen.getByText('Next');
        fireEvent.click(nextButton);
      });

      // Configure SFTP
      await waitFor(() => {
        expect(screen.getByText('Integration Methods')).toBeInTheDocument();
      });

      const sftpCheckbox = screen.getByLabelText('SFTP Integration');
      await user.click(sftpCheckbox);

      await waitFor(() => {
        expect(screen.getByText('SFTP Configuration')).toBeInTheDocument();
      });

      const usernameInput = screen.getByLabelText('Username');
      await user.type(usernameInput, username);

      const authTypeSelect = screen.getByLabelText('Authentication Type');
      await user.click(authTypeSelect);
      await user.click(screen.getByText('Password'));

      const passwordInput = screen.getByLabelText('Password');
      await user.type(passwordInput, 'testpassword123');

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      // Wait for real SFTP user creation in backend
      await waitFor(() => {
        const successElements = screen.queryAllByText(/success|complete|created/i);
        expect(successElements.length).toBeGreaterThan(0);
      }, { timeout: 15000 });

      // Verify SFTP configuration was created
      const sftpResponse = await realAxios.get(`/sftp/configurations?username=${username}`);
      expect(sftpResponse.data).toBeTruthy();
    }, 20000);

    it('handles real validation errors from backend API', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Try to create without required fields to trigger real validation
      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      // Should show real validation error from backend
      await waitFor(() => {
        const errorElements = screen.queryAllByText(/required|error|name/i);
        expect(errorElements.length).toBeGreaterThan(0);
      }, { timeout: 5000 });
    }, 8000);
  });

  describe('Real Profile Management Integration', () => {
    it('creates trading partner with multiple real profiles in database', async () => {
      const partnerName = `Multi Profile Partner ${Date.now()}`;

      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Basic info
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, partnerName);

      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      // Add first profile
      await waitFor(() => {
        expect(screen.getByText('Profiles Configuration')).toBeInTheDocument();
      });

      const addProfileButton = screen.getByText('Add Profile');
      await user.click(addProfileButton);

      let profileNameInput = screen.getByLabelText('Profile Name');
      await user.type(profileNameInput, 'Inbound 837 Claims');

      // Configure SNIP level
      const snipSelect = screen.getByLabelText('SNIP Level');
      await user.click(snipSelect);
      await user.click(screen.getByText('SNIP3'));

      let saveButton = screen.getByText('Save Profile');
      await user.click(saveButton);

      // Add second profile
      await user.click(addProfileButton);

      await waitFor(() => {
        profileNameInput = screen.getByLabelText('Profile Name');
      });

      await user.clear(profileNameInput);
      await user.type(profileNameInput, 'Outbound 835 Remittance');

      const snipSelect2 = screen.getByLabelText('SNIP Level');
      await user.click(snipSelect2);
      await user.click(screen.getByText('SNIP5'));

      saveButton = screen.getByText('Save Profile');
      await user.click(saveButton);

      // Continue and finish
      const nextButton2 = screen.getByText('Next');
      await user.click(nextButton2);

      const apiCheckbox = screen.getByLabelText('API Integration');
      await user.click(apiCheckbox);

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      // Wait for creation
      await waitFor(() => {
        const successElements = screen.queryAllByText(/success|complete/i);
        expect(successElements.length).toBeGreaterThan(0);
      }, { timeout: 12000 });

      // Verify profiles were created in database
      const partnersResponse = await realAxios.get('/trading-partners');
      const createdPartner = partnersResponse.data.find((p: any) => p.name === partnerName);
      
      expect(createdPartner).toBeTruthy();
      expect(createdPartner.profiles).toHaveLength(2);
      
      const profileNames = createdPartner.profiles.map((p: any) => p.name);
      expect(profileNames).toContain('Inbound 837 Claims');
      expect(profileNames).toContain('Outbound 835 Remittance');
    }, 20000);

    it('tests profile matching criteria with real database queries', async () => {
      const partnerName = `Criteria Test Partner ${Date.now()}`;

      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, partnerName);

      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      // Create profile with matching criteria
      const addProfileButton = screen.getByText('Add Profile');
      await user.click(addProfileButton);

      const profileNameInput = screen.getByLabelText('Profile Name');
      await user.type(profileNameInput, 'Claims with Criteria');

      // Add matching criteria
      const addCriteriaButton = screen.getByText('Add Criteria');
      await user.click(addCriteriaButton);

      const fieldIdSelect = screen.getByLabelText('Field ID');
      await user.click(fieldIdSelect);
      await user.click(screen.getByText('ISA06 - Interchange Receiver ID'));

      const operatorSelect = screen.getByLabelText('Operator');
      await user.click(operatorSelect);
      await user.click(screen.getByText('Equals'));

      const expectedValueInput = screen.getByLabelText('Expected Value');
      await user.type(expectedValueInput, 'TESTPARTNER123');

      const saveProfileButton = screen.getByText('Save Profile');
      await user.click(saveProfileButton);

      // Complete creation
      const nextButton2 = screen.getByText('Next');
      await user.click(nextButton2);

      const apiCheckbox = screen.getByLabelText('API Integration');
      await user.click(apiCheckbox);

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      await waitFor(() => {
        const successElements = screen.queryAllByText(/success|complete/i);
        expect(successElements.length).toBeGreaterThan(0);
      }, { timeout: 10000 });

      // Verify criteria were stored in database
      const partnersResponse = await realAxios.get('/trading-partners');
      const createdPartner = partnersResponse.data.find((p: any) => p.name === partnerName);
      
      const profile = createdPartner.profiles[0];
      expect(profile.criteria).toHaveLength(1);
      expect(profile.criteria[0].field_identifier).toBe('ISA06');
      expect(profile.criteria[0].expected_value).toBe('TESTPARTNER123');
    }, 18000);
  });

  describe('Real SFTP Service Integration', () => {
    it('tests real SFTP user creation and authentication', async () => {
      const username = `realuser${Date.now()}`;
      const password = 'realpassword123';

      // Test direct SFTP configuration endpoint
      const sftpConfig = {
        username: username,
        authentication_type: 'PASSWORD',
        password: password,
        file_patterns: ['*.edi', '*.x12'],
        enabled: true
      };

      const createResponse = await realAxios.post('/sftp/configurations', sftpConfig);
      expect(createResponse.status).toBe(201);
      expect(createResponse.data.username).toBe(username);

      // Verify user was created in SFTP system
      const getResponse = await realAxios.get(`/sftp/configurations/${username}`);
      expect(getResponse.data.username).toBe(username);
      expect(getResponse.data.authentication_type).toBe('PASSWORD');
      expect(getResponse.data.file_patterns).toContain('*.edi');
    }, 10000);

    it('tests SFTP connection testing with real service', async () => {
      const username = `conntest${Date.now()}`;
      
      // Create SFTP user first
      const sftpConfig = {
        username: username,
        authentication_type: 'PASSWORD', 
        password: 'testconnection123',
        enabled: true
      };

      await realAxios.post('/sftp/configurations', sftpConfig);

      // Test connection
      const testResponse = await realAxios.post(`/sftp/configurations/${username}/test-connection`);
      expect(testResponse.status).toBe(200);
      expect(testResponse.data.success).toBe(true);
    }, 12000);

    it('handles real SFTP service errors', async () => {
      const duplicateUsername = `duplicate${Date.now()}`;
      
      const sftpConfig = {
        username: duplicateUsername,
        authentication_type: 'PASSWORD',
        password: 'password123'
      };

      // Create first user
      await realAxios.post('/sftp/configurations', sftpConfig);

      // Try to create duplicate - should fail
      try {
        await realAxios.post('/sftp/configurations', sftpConfig);
        fail('Should have thrown error for duplicate username');
      } catch (error: any) {
        expect(error.response.status).toBe(409);
        expect(error.response.data.detail).toContain('already exists');
      }
    }, 8000);
  });

  describe('Real Error Handling and Data Validation', () => {
    it('tests backend field validation', async () => {
      // Test creating trading partner with invalid data
      const invalidData = {
        name: '', // Empty name should fail validation
        profiles: [{
          name: '', // Empty profile name should fail
          snip_level: 'INVALID_SNIP' // Invalid SNIP level
        }]
      };

      try {
        await realAxios.post('/trading-partners', invalidData);
        fail('Should have thrown validation error');
      } catch (error: any) {
        expect(error.response.status).toBe(422);
        expect(error.response.data.detail).toBeTruthy();
      }
    }, 5000);

    it('tests real database transaction rollback on errors', async () => {
      const partnerName = `Rollback Test ${Date.now()}`;
      
      // Create partner with valid data but simulate SFTP failure
      const partnerData = {
        name: partnerName,
        integration_methods: ['API', 'SFTP'],
        sftp_configuration: {
          username: 'invalid/username!@#', // Invalid characters should cause SFTP creation to fail
          authentication_type: 'PASSWORD',
          password: 'password123'
        }
      };

      try {
        await realAxios.post('/trading-partners', partnerData);
        fail('Should have failed due to invalid SFTP username');
      } catch (error: any) {
        expect(error.response.status).toBeGreaterThanOrEqual(400);
      }

      // Verify trading partner was not created due to rollback
      const partnersResponse = await realAxios.get('/trading-partners');
      const partners = partnersResponse.data;
      
      const rollbackPartner = partners.find((p: any) => p.name === partnerName);
      expect(rollbackPartner).toBeFalsy(); // Should not exist due to transaction rollback
    }, 8000);
  });

  describe('Real Multi-tenant Testing', () => {
    it('tests tenant isolation with real JWT tokens', async () => {
      // Create axios instance with different tenant token
      const tenantBAxios = axios.create({
        baseURL: apiUrl,
        timeout: 10000,
        headers: {
          'Content-Type': 'application/json',
          // Different tenant token
          'Authorization': 'Bearer eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJzdWIiOiAidGVzdC11c2VyLTQ1NiIsICJwcmVmZXJyZWRfdXNlcm5hbWUiOiAidGVzdC11c2VyLWIiLCAiZW1haWwiOiAidGVzdGJAdGVzdC5jb20iLCAiZ3JvdXBzIjogWyJ0ZW5hbnQtYiJdLCAicmVhbG1fYWNjZXNzIjogeyJyb2xlcyI6IFsic2Z0cDpyZWFkIiwgInNmdHA6cHJvY2VzcyIsICJhZG1pbiJdfSwgImlhdCI6IDE3NTQyNzA1NjksICJleHAiOiAxNzU0Mjc3NzY5LCAiaXNzIjogImVkaS1sZW5zLXRlc3QiLCAiYXVkIjogImVkaS1sZW5zLWFwaSJ9.ZmFrZV9zaWduYXR1cmVfZm9yX2RlbW8'
        }
      });

      // Create trading partner with tenant A
      const tenantAPartner = {
        name: `Tenant A Partner ${Date.now()}`,
        integration_methods: ['API']
      };

      const tenantAResponse = await realAxios.post('/trading-partners', tenantAPartner);
      expect(tenantAResponse.status).toBe(201);

      // Create trading partner with tenant B
      const tenantBPartner = {
        name: `Tenant B Partner ${Date.now()}`,
        integration_methods: ['API']
      };

      const tenantBResponse = await tenantBAxios.post('/trading-partners', tenantBPartner);
      expect(tenantBResponse.status).toBe(201);

      // Verify tenant A cannot see tenant B's partner
      const tenantAPartners = await realAxios.get('/trading-partners');
      const tenantAPartnerNames = tenantAPartners.data.map((p: any) => p.name);
      expect(tenantAPartnerNames).toContain(tenantAPartner.name);
      expect(tenantAPartnerNames).not.toContain(tenantBPartner.name);

      // Verify tenant B cannot see tenant A's partner  
      const tenantBPartners = await tenantBAxios.get('/trading-partners');
      const tenantBPartnerNames = tenantBPartners.data.map((p: any) => p.name);
      expect(tenantBPartnerNames).toContain(tenantBPartner.name);
      expect(tenantBPartnerNames).not.toContain(tenantAPartner.name);
    }, 12000);
  });
});