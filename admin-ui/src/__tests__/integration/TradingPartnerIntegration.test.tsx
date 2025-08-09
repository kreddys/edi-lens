import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { BrowserRouter } from 'react-router-dom';
import { Create } from '../../pages/tradingPartners/create';
import { Edit } from '../../pages/tradingPartners/edit';
import { TradingPartnerWizard } from '../../pages/tradingPartners/TradingPartnerWizard';
import { TestWrapper, mockTradingPartner, mockProfile, mockSftpConfiguration } from '../../test-utils';

// Mock Refine hooks
const mockCreate = jest.fn();
const mockUpdate = jest.fn();
const mockGetOne = jest.fn();
const mockCustom = jest.fn();

jest.mock('@refinedev/core', () => ({
  ...jest.requireActual('@refinedev/core'),
  useCreate: () => ({ mutate: mockCreate, isLoading: false }),
  useUpdate: () => ({ mutate: mockUpdate, isLoading: false }),
  useOne: () => ({ 
    data: { data: mockTradingPartner }, 
    isLoading: false 
  }),
  useCustom: () => ({ 
    data: { data: [] }, 
    isLoading: false 
  }),
  useShow: () => ({ 
    queryResult: { 
      data: { data: mockTradingPartner }, 
      isLoading: false 
    } 
  })
}));

// Mock SFTP configuration hook
const mockUseSftpConfiguration = {
  createConfiguration: jest.fn(),
  updateConfiguration: jest.fn(),
  getConfiguration: jest.fn(),
  testConnection: jest.fn(),
  isLoading: false,
  error: null
};

jest.mock('../../hooks/useSftpConfiguration', () => ({
  useSftpConfiguration: () => mockUseSftpConfiguration
}));

// Mock axios for API calls
jest.mock('axios', () => ({
  create: () => ({
    post: jest.fn(),
    put: jest.fn(),
    get: jest.fn()
  }),
  post: jest.fn(),
  put: jest.fn(),
  get: jest.fn()
}));

const mockAxios = {
  post: jest.fn(),
  put: jest.fn(),
  get: jest.fn()
};

describe('Trading Partner Integration Tests', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    jest.clearAllMocks();
    mockUseSftpConfiguration.createConfiguration.mockResolvedValue(mockSftpConfiguration);
    mockUseSftpConfiguration.updateConfiguration.mockResolvedValue(mockSftpConfiguration);
    mockUseSftpConfiguration.getConfiguration.mockResolvedValue(mockSftpConfiguration);
    mockUseSftpConfiguration.testConnection.mockResolvedValue({ 
      success: true, 
      message: 'Connection successful' 
    });
  });

  describe('End-to-End Trading Partner Creation', () => {
    it('creates trading partner with API integration only', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Step 1: Basic Information
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'ACME Healthcare Corp');

      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      // Step 2: Add Profile
      await waitFor(() => {
        expect(screen.getByText('Profiles Configuration')).toBeInTheDocument();
      });

      const addProfileButton = screen.getByText('Add Profile');
      await user.click(addProfileButton);

      const profileNameInput = screen.getByLabelText('Profile Name');
      await user.type(profileNameInput, 'Standard 837P Claims');

      // Configure SNIP level
      const snipSelect = screen.getByLabelText('SNIP Level');
      await user.click(snipSelect);
      await user.click(screen.getByText('SNIP3'));

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
      await user.type(expectedValueInput, 'ACMEHC');

      // Enable TA1
      const ta1Switch = screen.getByLabelText('Generate TA1');
      await user.click(ta1Switch);

      const saveProfileButton = screen.getByText('Save Profile');
      await user.click(saveProfileButton);

      // Move to integration step
      const nextButton2 = screen.getByText('Next');
      await user.click(nextButton2);

      // Step 3: Integration - Select API only
      await waitFor(() => {
        expect(screen.getByText('Integration Methods')).toBeInTheDocument();
      });

      const apiCheckbox = screen.getByLabelText('API Integration');
      await user.click(apiCheckbox);

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      await waitFor(() => {
        expect(mockCreate).toHaveBeenCalledWith({
          resource: 'trading-partners',
          values: expect.objectContaining({
            name: 'ACME Healthcare Corp',
            profiles: expect.arrayContaining([
              expect.objectContaining({
                name: 'Standard 837P Claims',
                snip_level: 'SNIP3',
                generate_ta1: true,
                criteria: expect.arrayContaining([
                  expect.objectContaining({
                    field_source: 'ISA',
                    field_identifier: 'ISA06',
                    operator: 'EQUALS',
                    expected_value: 'ACMEHC'
                  })
                ])
              })
            ])
          })
        });
      });
    });

    it('creates trading partner with SFTP integration', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Step 1: Basic Information
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Regional Medical Center');

      let nextButton = screen.getByText('Next');
      await user.click(nextButton);

      // Step 2: Skip profiles for this test
      await waitFor(() => {
        nextButton = screen.getByText('Next');
        fireEvent.click(nextButton);
      });

      // Step 3: Integration - Configure SFTP
      await waitFor(() => {
        expect(screen.getByText('Integration Methods')).toBeInTheDocument();
      });

      const sftpCheckbox = screen.getByLabelText('SFTP Integration');
      await user.click(sftpCheckbox);

      await waitFor(() => {
        expect(screen.getByText('SFTP Configuration')).toBeInTheDocument();
      });

      const usernameInput = screen.getByLabelText('Username');
      await user.type(usernameInput, 'rmc-partner');

      const authTypeSelect = screen.getByLabelText('Authentication Type');
      await user.click(authTypeSelect);
      await user.click(screen.getByText('Password'));

      const passwordInput = screen.getByLabelText('Password');
      await user.type(passwordInput, 'secure-password-123');

      const filePatternsInput = screen.getByLabelText('File Patterns');
      await user.type(filePatternsInput, '*.edi,*.x12');

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      await waitFor(() => {
        expect(mockCreate).toHaveBeenCalledWith({
          resource: 'trading-partners',
          values: expect.objectContaining({
            name: 'Regional Medical Center'
          })
        });

        expect(mockUseSftpConfiguration.createConfiguration).toHaveBeenCalledWith(
          expect.objectContaining({
            username: 'rmc-partner',
            authentication_type: 'PASSWORD',
            password: 'secure-password-123',
            file_patterns: ['*.edi', '*.x12']
          })
        );
      });
    });

    it('creates trading partner with both API and SFTP integration', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Complete wizard with both integrations
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Comprehensive Health System');

      let nextButton = screen.getByText('Next');
      await user.click(nextButton);

      // Skip profiles
      await waitFor(() => {
        nextButton = screen.getByText('Next');
        fireEvent.click(nextButton);
      });

      // Select both integration methods
      await waitFor(() => {
        expect(screen.getByText('Integration Methods')).toBeInTheDocument();
      });

      const apiCheckbox = screen.getByLabelText('API Integration');
      const sftpCheckbox = screen.getByLabelText('SFTP Integration');
      
      await user.click(apiCheckbox);
      await user.click(sftpCheckbox);

      // Configure SFTP
      await waitFor(() => {
        expect(screen.getByText('SFTP Configuration')).toBeInTheDocument();
      });

      const usernameInput = screen.getByLabelText('Username');
      await user.type(usernameInput, 'chs-hybrid');

      const authTypeSelect = screen.getByLabelText('Authentication Type');
      await user.click(authTypeSelect);
      await user.click(screen.getByText('SSH Key'));

      const sshKeyInput = screen.getByLabelText('SSH Private Key');
      await user.type(sshKeyInput, '-----BEGIN OPENSSH PRIVATE KEY-----\ntest-key-content\n-----END OPENSSH PRIVATE KEY-----');

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      await waitFor(() => {
        expect(mockCreate).toHaveBeenCalled();
        expect(mockUseSftpConfiguration.createConfiguration).toHaveBeenCalledWith(
          expect.objectContaining({
            authentication_type: 'SSH_KEY',
            ssh_private_key: '-----BEGIN OPENSSH PRIVATE KEY-----\ntest-key-content\n-----END OPENSSH PRIVATE KEY-----'
          })
        );
      });
    });
  });

  describe('Profile Management Integration', () => {
    it('manages multiple profiles for a single partner', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Basic info
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Multi-Profile Partner');

      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Profiles Configuration')).toBeInTheDocument();
      });

      // Add first profile
      const addProfileButton = screen.getByText('Add Profile');
      await user.click(addProfileButton);

      let profileNameInput = screen.getByLabelText('Profile Name');
      await user.type(profileNameInput, 'Inbound Claims');

      let saveButton = screen.getByText('Save Profile');
      await user.click(saveButton);

      // Add second profile
      await user.click(addProfileButton);

      // Wait for modal to open again
      await waitFor(() => {
        profileNameInput = screen.getByLabelText('Profile Name');
      });

      await user.clear(profileNameInput);
      await user.type(profileNameInput, 'Outbound Remittances');

      const snipSelect = screen.getByLabelText('SNIP Level');
      await user.click(snipSelect);
      await user.click(screen.getByText('SNIP5'));

      saveButton = screen.getByText('Save Profile');
      await user.click(saveButton);

      // Verify both profiles are listed
      await waitFor(() => {
        expect(screen.getByText('Inbound Claims')).toBeInTheDocument();
        expect(screen.getByText('Outbound Remittances')).toBeInTheDocument();
      });

      // Continue and finish
      const nextButton2 = screen.getByText('Next');
      await user.click(nextButton2);

      const apiCheckbox = screen.getByLabelText('API Integration');
      await user.click(apiCheckbox);

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      await waitFor(() => {
        expect(mockCreate).toHaveBeenCalledWith({
          resource: 'trading-partners',
          values: expect.objectContaining({
            name: 'Multi-Profile Partner',
            profiles: expect.arrayContaining([
              expect.objectContaining({ name: 'Inbound Claims' }),
              expect.objectContaining({ name: 'Outbound Remittances', snip_level: 'SNIP5' })
            ])
          })
        });
      });
    });

    it('edits and deletes profiles within wizard', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Basic setup
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Edit Test Partner');

      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      // Add a profile
      const addProfileButton = screen.getByText('Add Profile');
      await user.click(addProfileButton);

      const profileNameInput = screen.getByLabelText('Profile Name');
      await user.type(profileNameInput, 'Initial Profile');

      const saveButton = screen.getByText('Save Profile');
      await user.click(saveButton);

      // Verify profile appears in table
      await waitFor(() => {
        expect(screen.getByText('Initial Profile')).toBeInTheDocument();
      });

      // Edit the profile
      const editButton = screen.getByTitle('Edit');
      await user.click(editButton);

      await waitFor(async () => {
        const profileNameInput = screen.getByLabelText('Profile Name');
        await user.clear(profileNameInput);
        await user.type(profileNameInput, 'Updated Profile Name');

        const saveButton = screen.getByText('Save Profile');
        await user.click(saveButton);
      });

      // Verify updated name
      await waitFor(() => {
        expect(screen.getByText('Updated Profile Name')).toBeInTheDocument();
        expect(screen.queryByText('Initial Profile')).not.toBeInTheDocument();
      });

      // Delete the profile
      const deleteButton = screen.getByTitle('Delete');
      await user.click(deleteButton);

      // Verify profile is removed
      await waitFor(() => {
        expect(screen.queryByText('Updated Profile Name')).not.toBeInTheDocument();
      });
    });
  });

  describe('Error Handling Integration', () => {
    it('handles SFTP configuration errors gracefully', async () => {
      mockUseSftpConfiguration.createConfiguration.mockRejectedValueOnce(
        new Error('SFTP username already exists')
      );

      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Complete form with SFTP
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Error Test Partner');

      let nextButton = screen.getByText('Next');
      await user.click(nextButton);

      await waitFor(() => {
        nextButton = screen.getByText('Next');
        fireEvent.click(nextButton);
      });

      const sftpCheckbox = screen.getByLabelText('SFTP Integration');
      await user.click(sftpCheckbox);

      const usernameInput = screen.getByLabelText('Username');
      await user.type(usernameInput, 'existing-user');

      const authTypeSelect = screen.getByLabelText('Authentication Type');
      await user.click(authTypeSelect);
      await user.click(screen.getByText('Password'));

      const passwordInput = screen.getByLabelText('Password');
      await user.type(passwordInput, 'password');

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      await waitFor(() => {
        expect(screen.getByText(/SFTP username already exists/)).toBeInTheDocument();
      });

      // Trading partner should not be created if SFTP fails
      expect(mockCreate).not.toHaveBeenCalled();
    });

    it('handles backend API errors during creation', async () => {
      mockCreate.mockImplementationOnce((params) => {
        params.onError?.({ 
          message: 'Partner with this name already exists',
          statusCode: 409
        });
      });

      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Duplicate Partner');

      let nextButton = screen.getByText('Next');
      await user.click(nextButton);

      await waitFor(() => {
        nextButton = screen.getByText('Next');
        fireEvent.click(nextButton);
      });

      const apiCheckbox = screen.getByLabelText('API Integration');
      await user.click(apiCheckbox);

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      await waitFor(() => {
        expect(screen.getByText(/Partner with this name already exists/)).toBeInTheDocument();
      });
    });
  });

  describe('SFTP Connection Testing Integration', () => {
    it('tests SFTP connection during configuration', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Navigate to SFTP configuration
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Connection Test Partner');

      let nextButton = screen.getByText('Next');
      await user.click(nextButton);

      await waitFor(() => {
        nextButton = screen.getByText('Next');
        fireEvent.click(nextButton);
      });

      const sftpCheckbox = screen.getByLabelText('SFTP Integration');
      await user.click(sftpCheckbox);

      // Fill SFTP configuration
      const usernameInput = screen.getByLabelText('Username');
      await user.type(usernameInput, 'test-connection');

      const authTypeSelect = screen.getByLabelText('Authentication Type');
      await user.click(authTypeSelect);
      await user.click(screen.getByText('Password'));

      const passwordInput = screen.getByLabelText('Password');
      await user.type(passwordInput, 'test-password');

      // Test connection (if test button exists)
      const testButton = screen.queryByText('Test Connection');
      if (testButton) {
        await user.click(testButton);

        await waitFor(() => {
          expect(mockUseSftpConfiguration.testConnection).toHaveBeenCalled();
          expect(screen.getByText(/Connection successful/)).toBeInTheDocument();
        });
      }

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      await waitFor(() => {
        expect(mockCreate).toHaveBeenCalled();
      });
    });

    it('handles failed connection tests', async () => {
      mockUseSftpConfiguration.testConnection.mockResolvedValueOnce({
        success: false,
        message: 'Authentication failed: Invalid credentials'
      });

      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Set up SFTP with invalid credentials
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Failed Connection Partner');

      let nextButton = screen.getByText('Next');
      await user.click(nextButton);

      await waitFor(() => {
        nextButton = screen.getByText('Next');
        fireEvent.click(nextButton);
      });

      const sftpCheckbox = screen.getByLabelText('SFTP Integration');
      await user.click(sftpCheckbox);

      const usernameInput = screen.getByLabelText('Username');
      await user.type(usernameInput, 'invalid-user');

      const authTypeSelect = screen.getByLabelText('Authentication Type');
      await user.click(authTypeSelect);
      await user.click(screen.getByText('Password'));

      const passwordInput = screen.getByLabelText('Password');
      await user.type(passwordInput, 'wrong-password');

      // Test connection
      const testButton = screen.queryByText('Test Connection');
      if (testButton) {
        await user.click(testButton);

        await waitFor(() => {
          expect(screen.getByText(/Authentication failed/)).toBeInTheDocument();
        });
      }
    });
  });

  describe('Form Validation Integration', () => {
    it('prevents submission with invalid data across all steps', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Try to proceed without partner name
      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Please enter a partner name')).toBeInTheDocument();
      });

      // Add partner name and proceed
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Validation Test Partner');
      await user.click(nextButton);

      // Skip profiles and go to integration
      await waitFor(() => {
        const nextButton2 = screen.getByText('Next');
        fireEvent.click(nextButton2);
      });

      // Try to finish without selecting any integration method
      await waitFor(() => {
        const finishButton = screen.getByText('Finish');
        fireEvent.click(finishButton);
      });

      await waitFor(() => {
        expect(screen.getByText(/Please select at least one integration method/)).toBeInTheDocument();
      });

      // Select SFTP but don't configure it
      const sftpCheckbox = screen.getByLabelText('SFTP Integration');
      await user.click(sftpCheckbox);

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      await waitFor(() => {
        expect(screen.getByText(/Please enter a username/)).toBeInTheDocument();
      });
    });
  });
});