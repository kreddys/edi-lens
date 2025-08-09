import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TradingPartnerWizard } from '../TradingPartnerWizard';
import { TestWrapper, mockTradingPartner, mockProfile, mockSftpConfiguration } from '../../../test-utils';

// Mock the SFTP configuration hook
const mockUseSftpConfiguration = {
  createConfiguration: jest.fn(),
  updateConfiguration: jest.fn(),
  isLoading: false,
  error: null
};

jest.mock('../../../hooks/useSftpConfiguration', () => ({
  useSftpConfiguration: () => mockUseSftpConfiguration
}));

// Mock Refine hooks
const mockCreate = jest.fn();
const mockUpdate = jest.fn();
const mockCustom = jest.fn();

jest.mock('@refinedev/core', () => ({
  ...jest.requireActual('@refinedev/core'),
  useCreate: () => ({ mutate: mockCreate }),
  useUpdate: () => ({ mutate: mockUpdate }),
  useCustom: () => ({ data: { data: [] }, isLoading: false })
}));

describe('TradingPartnerWizard', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Step 1: Basic Information', () => {
    it('renders basic information form', () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      expect(screen.getByText('Basic Info')).toBeInTheDocument();
      expect(screen.getByLabelText('Partner Name')).toBeInTheDocument();
      expect(screen.getByText('Next')).toBeInTheDocument();
      expect(screen.getByText('Cancel')).toBeInTheDocument();
    });

    it('validates required partner name', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Please enter a partner name')).toBeInTheDocument();
      });
    });

    it('advances to step 2 with valid partner name', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Test Partner Corp');

      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Profiles')).toBeInTheDocument();
      });
    });
  });

  describe('Step 2: Profiles Configuration', () => {
    beforeEach(async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Navigate to step 2
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Test Partner Corp');
      const nextButton = screen.getByText('Next');
      await user.click(nextButton);
    });

    it('renders profiles configuration step', async () => {
      await waitFor(() => {
        expect(screen.getByText('Profiles')).toBeInTheDocument();
        expect(screen.getByText('Add Profile')).toBeInTheDocument();
      });
    });

    it('can add a new profile', async () => {
      const addProfileButton = screen.getByText('Add Profile');
      await user.click(addProfileButton);

      await waitFor(() => {
        expect(screen.getByLabelText('Profile Name')).toBeInTheDocument();
        expect(screen.getByLabelText('Schema')).toBeInTheDocument();
        expect(screen.getByLabelText('SNIP Level')).toBeInTheDocument();
      });
    });

    it('validates profile form fields', async () => {
      const addProfileButton = screen.getByText('Add Profile');
      await user.click(addProfileButton);

      await waitFor(() => {
        const saveButton = screen.getByText('Save Profile');
        fireEvent.click(saveButton);
      });

      await waitFor(() => {
        expect(screen.getByText('Please enter a profile name')).toBeInTheDocument();
      });
    });

    it('creates profile with validation criteria', async () => {
      const addProfileButton = screen.getByText('Add Profile');
      await user.click(addProfileButton);

      await waitFor(async () => {
        // Fill profile form
        const profileNameInput = screen.getByLabelText('Profile Name');
        await user.type(profileNameInput, 'Standard Claims Profile');

        const snipLevelSelect = screen.getByLabelText('SNIP Level');
        await user.click(snipLevelSelect);
        await user.click(screen.getByText('SNIP3'));

        // Add validation criteria
        const addCriteriaButton = screen.getByText('Add Criteria');
        await user.click(addCriteriaButton);

        const fieldIdSelect = screen.getByLabelText('Field ID');
        await user.click(fieldIdSelect);
        await user.click(screen.getByText('ISA06 - Interchange Receiver ID'));

        const operatorSelect = screen.getByLabelText('Operator');
        await user.click(operatorSelect);
        await user.click(screen.getByText('Equals'));

        const expectedValueInput = screen.getByLabelText('Expected Value');
        await user.type(expectedValueInput, 'TEST123');

        // Enable TA1 generation
        const ta1Switch = screen.getByLabelText('Generate TA1');
        await user.click(ta1Switch);

        const saveButton = screen.getByText('Save Profile');
        await user.click(saveButton);
      });

      await waitFor(() => {
        expect(screen.getByText('Standard Claims Profile')).toBeInTheDocument();
      });
    });
  });

  describe('Step 3: Integration Methods', () => {
    beforeEach(async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Navigate to step 3
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Test Partner Corp');
      let nextButton = screen.getByText('Next');
      await user.click(nextButton);

      // Skip profile configuration
      await waitFor(() => {
        nextButton = screen.getByText('Next');
        fireEvent.click(nextButton);
      });
    });

    it('renders integration methods step', async () => {
      await waitFor(() => {
        expect(screen.getByText('Integration')).toBeInTheDocument();
        expect(screen.getByText('API Integration')).toBeInTheDocument();
        expect(screen.getByText('SFTP Integration')).toBeInTheDocument();
      });
    });

    it('shows SFTP configuration when SFTP is selected', async () => {
      const sftpCheckbox = screen.getByLabelText('SFTP Integration');
      await user.click(sftpCheckbox);

      await waitFor(() => {
        expect(screen.getByText('SFTP Configuration')).toBeInTheDocument();
        expect(screen.getByLabelText('Username')).toBeInTheDocument();
        expect(screen.getByLabelText('Authentication Type')).toBeInTheDocument();
      });
    });

    it('validates SFTP configuration fields', async () => {
      const sftpCheckbox = screen.getByLabelText('SFTP Integration');
      await user.click(sftpCheckbox);

      await waitFor(() => {
        const finishButton = screen.getByText('Finish');
        fireEvent.click(finishButton);
      });

      await waitFor(() => {
        expect(screen.getByText('Please enter a username')).toBeInTheDocument();
      });
    });

    it('completes wizard with API integration only', async () => {
      const apiCheckbox = screen.getByLabelText('API Integration');
      await user.click(apiCheckbox);

      const finishButton = screen.getByText('Finish');
      await user.click(finishButton);

      await waitFor(() => {
        expect(mockCreate).toHaveBeenCalledWith({
          resource: 'trading-partners',
          values: expect.objectContaining({
            name: 'Test Partner Corp'
          })
        });
      });
    });

    it('completes wizard with SFTP configuration', async () => {
      const sftpCheckbox = screen.getByLabelText('SFTP Integration');
      await user.click(sftpCheckbox);

      await waitFor(async () => {
        const usernameInput = screen.getByLabelText('Username');
        await user.type(usernameInput, 'test-sftp-user');

        const authTypeSelect = screen.getByLabelText('Authentication Type');
        await user.click(authTypeSelect);
        await user.click(screen.getByText('Password'));

        const passwordInput = screen.getByLabelText('Password');
        await user.type(passwordInput, 'secure-password');

        const filePatternsInput = screen.getByLabelText('File Patterns');
        await user.type(filePatternsInput, '*.edi,*.txt');

        const finishButton = screen.getByText('Finish');
        await user.click(finishButton);
      });

      await waitFor(() => {
        expect(mockCreate).toHaveBeenCalled();
        expect(mockUseSftpConfiguration.createConfiguration).toHaveBeenCalledWith(
          expect.objectContaining({
            username: 'test-sftp-user',
            authentication_type: 'PASSWORD',
            password: 'secure-password',
            file_patterns: ['*.edi', '*.txt']
          })
        );
      });
    });
  });

  describe('Navigation and State Management', () => {
    it('allows navigation between steps', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Step 1 -> 2
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Test Partner Corp');
      let nextButton = screen.getByText('Next');
      await user.click(nextButton);

      await waitFor(() => {
        expect(screen.getByText('Profiles')).toBeInTheDocument();
      });

      // Step 2 -> 1 (back)
      const backButton = screen.getByText('Back');
      await user.click(backButton);

      await waitFor(() => {
        expect(screen.getByText('Basic Info')).toBeInTheDocument();
        expect(screen.getByDisplayValue('Test Partner Corp')).toBeInTheDocument();
      });
    });

    it('preserves form data between steps', async () => {
      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Fill step 1
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Test Partner Corp');
      let nextButton = screen.getByText('Next');
      await user.click(nextButton);

      // Go to step 3
      await waitFor(() => {
        nextButton = screen.getByText('Next');
        fireEvent.click(nextButton);
      });

      // Go back to step 1
      await waitFor(() => {
        const backButton = screen.getByText('Back');
        fireEvent.click(backButton);
      });

      await waitFor(() => {
        const backButton = screen.getByText('Back');
        fireEvent.click(backButton);
      });

      // Verify data is preserved
      await waitFor(() => {
        expect(screen.getByDisplayValue('Test Partner Corp')).toBeInTheDocument();
      });
    });

    it('handles cancellation properly', async () => {
      const onCancel = jest.fn();
      
      render(
        <TestWrapper>
          <TradingPartnerWizard onCancel={onCancel} />
        </TestWrapper>
      );

      const cancelButton = screen.getByText('Cancel');
      await user.click(cancelButton);

      expect(onCancel).toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    it('handles SFTP configuration creation errors', async () => {
      mockUseSftpConfiguration.createConfiguration.mockRejectedValueOnce(
        new Error('SFTP user already exists')
      );
      mockUseSftpConfiguration.error = 'SFTP user already exists';

      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      // Navigate to step 3 and configure SFTP
      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Test Partner Corp');
      let nextButton = screen.getByText('Next');
      await user.click(nextButton);

      await waitFor(() => {
        nextButton = screen.getByText('Next');
        fireEvent.click(nextButton);
      });

      const sftpCheckbox = screen.getByLabelText('SFTP Integration');
      await user.click(sftpCheckbox);

      await waitFor(async () => {
        const usernameInput = screen.getByLabelText('Username');
        await user.type(usernameInput, 'existing-user');

        const authTypeSelect = screen.getByLabelText('Authentication Type');
        await user.click(authTypeSelect);
        await user.click(screen.getByText('Password'));

        const passwordInput = screen.getByLabelText('Password');
        await user.type(passwordInput, 'password');

        const finishButton = screen.getByText('Finish');
        await user.click(finishButton);
      });

      await waitFor(() => {
        expect(screen.getByText(/SFTP user already exists/)).toBeInTheDocument();
      });
    });

    it('handles trading partner creation errors', async () => {
      mockCreate.mockImplementationOnce((params) => {
        params.onError?.({ message: 'Partner name already exists' });
      });

      render(
        <TestWrapper>
          <TradingPartnerWizard mode="create" onCancel={() => {}} />
        </TestWrapper>
      );

      const nameInput = screen.getByLabelText('Partner Name');
      await user.type(nameInput, 'Existing Partner');
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
        expect(screen.getByText(/Partner name already exists/)).toBeInTheDocument();
      });
    });
  });
});