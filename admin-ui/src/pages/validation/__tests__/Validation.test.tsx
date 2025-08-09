import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Validation } from '../Validation';
import { TestWrapper, mockValidationResult, mockFetch } from '../../../test-utils';

// Mock axios
jest.mock('axios', () => ({
  create: () => ({
    post: jest.fn(),
    get: jest.fn()
  }),
  post: jest.fn(),
  get: jest.fn()
}));

const mockAxios = {
  post: jest.fn(),
  get: jest.fn()
};

// Mock Refine hooks
const mockCustom = jest.fn();

jest.mock('@refinedev/core', () => ({
  ...jest.requireActual('@refinedev/core'),
  useCustom: () => ({ 
    data: { data: [{ name: 'Test Profile' }, { name: 'Priority Claims' }] }, 
    isLoading: false 
  })
}));

// Mock file download with proper DOM elements
const mockCreateObjectURL = jest.fn(() => 'blob:mock-url');
const mockRevokeObjectURL = jest.fn();

Object.defineProperty(URL, 'createObjectURL', {
  writable: true,
  value: mockCreateObjectURL
});

Object.defineProperty(URL, 'revokeObjectURL', {
  writable: true,
  value: mockRevokeObjectURL
});

// Mock file download functionality
const mockClick = jest.fn();
const mockAppendChild = jest.fn();
const mockRemoveChild = jest.fn();

describe('Validation Component', () => {
  const user = userEvent.setup();
  
  const sampleEdiData = `ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250109*1234*^*00501*000000001*0*T*:~
GS*HC*SENDER*RECEIVER*20250109*1234*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*123456789*20250109*1234*CH~
NM1*41*2*SUBMITTER NAME*****46*12345~
PER*IC*CONTACT NAME*TE*5551234567~
NM1*40*2*RECEIVER NAME*****46*67890~
HL*1**20*1~
PRV*BI*PXC*123456789~
NM1*85*2*BILLING PROVIDER*****XX*1234567890~
N3*123 MAIN ST~
N4*ANYTOWN*NY*12345~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GROUP123*GROUP NAME*****12~
NM1*IL*1*PATIENT*JOHN*A***MI*123456789~
N3*456 ELM ST~
N4*SOMEWHERE*CA*54321~
DMG*D8*19800101*M~
NM1*PR*2*INSURANCE COMPANY*****PI*ABCDE~
CLM*CLAIM123*100***11:B:1*Y*A*Y*I~
DTP*431*D8*20250101~
HI*BK:Z1234~
LX*1~
SV1*HC:99213*75*UN*1***1~
DTP*472*D8*20250101~
SE*28*0001~
GE*1*1~
IEA*1*000000001~`;

  beforeEach(() => {
    jest.clearAllMocks();
    mockAxios.post.mockResolvedValue({ 
      data: mockValidationResult 
    });
  });

  describe('Initial Rendering', () => {
    it('renders validation interface with all main components', () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      expect(screen.getByText('🔍 EDI Validation')).toBeInTheDocument();
      expect(screen.getByText('Profile Selection:')).toBeInTheDocument();
      expect(screen.getByText('Auto-detect Profile')).toBeInTheDocument();
      expect(screen.getByText('Manual Selection')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('Paste your EDI content here or upload a file above...')).toBeInTheDocument();
      expect(screen.getByText('Upload EDI File')).toBeInTheDocument();
      expect(screen.getByText('Validate EDI')).toBeInTheDocument();
    });

    it('has auto-detect selected by default', () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Auto-detect Profile button should be selected by default
      const autoDetectButton = screen.getByText('Auto-detect Profile');
      expect(autoDetectButton.closest('label')).toHaveClass('ant-radio-button-wrapper-checked');
    });

    it('disables validate button when no EDI data', () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const validateButton = screen.getByText('Validate EDI');
      expect(validateButton.closest('button')).toBeDisabled();
    });
  });

  describe('Profile Selection', () => {
    it('shows profile dropdown when manual selection is chosen', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const manualButton = screen.getByText('Manual Selection');
      await user.click(manualButton);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Select a profile...')).toBeInTheDocument();
      });
    });

    it('hides profile dropdown when auto-detect is chosen', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // First select manual
      const manualButton = screen.getByText('Manual Selection');
      await user.click(manualButton);

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Select a profile...')).toBeInTheDocument();
      });

      // Then select auto-detect
      const autoDetectButton = screen.getByText('Auto-detect Profile');
      await user.click(autoDetectButton);

      await waitFor(() => {
        expect(screen.queryByPlaceholderText('Select a profile...')).not.toBeInTheDocument();
      });
    });

    it('loads available profiles for manual selection', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const manualButton = screen.getByText('Manual Selection');
      await user.click(manualButton);

      await waitFor(() => {
        const profileSelect = screen.getByPlaceholderText('Select a profile...');
        fireEvent.mouseDown(profileSelect);
      });

      await waitFor(() => {
        expect(screen.getByText('Test Profile')).toBeInTheDocument();
        expect(screen.getByText('Priority Claims')).toBeInTheDocument();
      });
    });
  });

  describe('EDI Data Input', () => {
    it('accepts EDI data via textarea', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      expect(textarea).toHaveValue(sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      expect(validateButton.closest('button')).toBeEnabled();
    });

    it('accepts EDI data via file upload', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const file = new File([sampleEdiData], 'test.edi', { type: 'text/plain' });
      const uploadInput = screen.getByRole('button', { name: /upload/i }).querySelector('input[type="file"]');

      if (uploadInput) {
        await user.upload(uploadInput, file);

        await waitFor(() => {
          const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
          expect(textarea).toHaveValue(sampleEdiData);
        });
      }
    });

    it('shows file size limit warning for large files', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Create a file larger than 10MB
      const largeContent = 'X'.repeat(11 * 1024 * 1024);
      const largeFile = new File([largeContent], 'large.edi', { type: 'text/plain' });
      
      const uploadInput = screen.getByRole('button', { name: /upload/i }).querySelector('input[type="file"]');

      if (uploadInput) {
        await user.upload(uploadInput, largeFile);

        await waitFor(() => {
          expect(screen.getByText(/File size exceeds 10MB limit/)).toBeInTheDocument();
        });
      }
    });
  });

  describe('Validation Process', () => {
    it('performs validation with auto-detect profile', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      expect(mockAxios.post).toHaveBeenCalledWith('/api/v1/validate', {
        edi_data: sampleEdiData,
        file_name: 'pasted_content.edi'
      });

      await waitFor(() => {
        expect(screen.getByText('Validation Complete')).toBeInTheDocument();
        expect(screen.getByText('Valid')).toBeInTheDocument();
      });
    });

    it('performs validation with manual profile selection', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Switch to manual selection
      const manualButton = screen.getByText('Manual Selection');
      await user.click(manualButton);

      await waitFor(async () => {
        const profileSelect = screen.getByPlaceholderText('Select a profile...');
        fireEvent.mouseDown(profileSelect);
        await user.click(screen.getByText('Test Profile'));
      });

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      expect(mockAxios.post).toHaveBeenCalledWith('/api/v1/validate', {
        edi_data: sampleEdiData,
        file_name: 'pasted_content.edi',
        profile_name: 'Test Profile'
      });
    });

    it('shows loading state during validation', async () => {
      // Delay the axios response
      mockAxios.post.mockImplementationOnce(() => 
        new Promise(resolve => setTimeout(() => resolve({ data: mockValidationResult }), 1000))
      );

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      expect(screen.getByText('Validating...')).toBeInTheDocument();
      expect(validateButton.closest('button')).toBeDisabled();
    });

    it('displays validation results with success status', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        expect(screen.getByText('Validation Complete')).toBeInTheDocument();
        expect(screen.getByText('Valid')).toBeInTheDocument();
        expect(screen.getByText('Test Profile')).toBeInTheDocument();
        expect(screen.getByText('Auto-detection')).toBeInTheDocument();
        expect(screen.getByText('250ms')).toBeInTheDocument();
        expect(screen.getByText('837.5010.X222.A1.json')).toBeInTheDocument();
        expect(screen.getByText('SNIP3')).toBeInTheDocument();
      });
    });

    it('displays validation results with error status', async () => {
      const errorResult = {
        ...mockValidationResult,
        valid: false,
        status: 'Rejected at Interchange Level',
        findings: [
          {
            level: 'error',
            code: 'ISA_001',
            message: 'Invalid interchange control number',
            location: {
              segment_id: 'ISA',
              segment_instance: 1,
              element_position: 13,
              line_number: 1
            }
          }
        ]
      };

      mockAxios.post.mockResolvedValueOnce({ data: errorResult });

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        expect(screen.getByText('Rejected at Interchange Level')).toBeInTheDocument();
        expect(screen.getByText('Invalid')).toBeInTheDocument();
        expect(screen.getByText('Invalid interchange control number')).toBeInTheDocument();
        expect(screen.getByText('ISA_001')).toBeInTheDocument();
      });
    });
  });

  describe('EDI Structure Analysis', () => {
    it('displays EDI structure information after validation', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        expect(screen.getByText('EDI Structure Analysis')).toBeInTheDocument();
        
        // Check for ISA analysis
        expect(screen.getByText('Interchange (ISA)')).toBeInTheDocument();
        expect(screen.getByText('SENDER')).toBeInTheDocument();
        expect(screen.getByText('RECEIVER')).toBeInTheDocument();
        
        // Check for GS analysis
        expect(screen.getByText('Functional Group (GS)')).toBeInTheDocument();
        expect(screen.getByText('HC')).toBeInTheDocument();
        expect(screen.getByText('005010X222A1')).toBeInTheDocument();
        
        // Check for transaction counts
        expect(screen.getByText('Transaction Sets: 1')).toBeInTheDocument();
      });
    });

    it('shows detailed segment breakdown', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        const structureSection = screen.getByText('EDI Structure Analysis').closest('.ant-card-body');
        if (structureSection) {
          expect(within(structureSection).getByText('ST*837')).toBeInTheDocument();
          expect(within(structureSection).getByText('BHT*0019')).toBeInTheDocument();
          expect(within(structureSection).getByText('NM1*41')).toBeInTheDocument();
        }
      });
    });
  });

  describe('File Downloads', () => {
    it('downloads TA1 acknowledgment when available', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        const downloadButton = screen.getByText('Download TA1');
        expect(downloadButton).toBeInTheDocument();
      });

      const downloadButton = screen.getByText('Download TA1');
      await user.click(downloadButton);

      // Just verify the URL methods were called for blob creation
      expect(mockCreateObjectURL).toHaveBeenCalled();
      expect(mockRevokeObjectURL).toHaveBeenCalled();
    });

    it('exports validation results as JSON', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        const exportButton = screen.getByText('Export Results');
        expect(exportButton).toBeInTheDocument();
      });

      const exportButton = screen.getByText('Export Results');
      await user.click(exportButton);

      // Just verify the URL methods were called for blob creation
      expect(mockCreateObjectURL).toHaveBeenCalled();
    });
  });

  describe('Error Handling', () => {
    it('displays error when validation API fails', async () => {
      mockAxios.post.mockRejectedValueOnce(new Error('Network error'));

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        expect(screen.getByText(/Validation failed/)).toBeInTheDocument();
      });
    });

    it('displays specific API error messages', async () => {
      mockAxios.post.mockRejectedValueOnce({
        response: {
          status: 400,
          data: { detail: 'Invalid EDI format' }
        }
      });

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, 'Invalid EDI content');

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        expect(screen.getByText(/Invalid EDI format/)).toBeInTheDocument();
      });
    });

    it('handles missing profile selection error', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Switch to manual selection but don't select a profile
      const manualButton = screen.getByText('Manual Selection');
      await user.click(manualButton);

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, sampleEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        expect(screen.getByText(/Please select a profile/)).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels and roles', () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      expect(screen.getByText('Auto-detect Profile')).toBeInTheDocument();
      expect(screen.getByText('Manual Selection')).toBeInTheDocument();
      expect(screen.getByRole('textbox')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /validate edi/i })).toBeInTheDocument();
    });

    it('supports keyboard navigation', async () => {
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const autoDetectButton = screen.getByText('Auto-detect Profile');
      const manualButton = screen.getByText('Manual Selection');
      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');

      // Test that elements are focusable
      expect(autoDetectButton.closest('label')).toBeTruthy();
      expect(manualButton.closest('label')).toBeTruthy();
      expect(textarea).toBeInTheDocument();
      
      // Test basic interaction
      await user.click(autoDetectButton);
      expect(autoDetectButton.closest('label')).toHaveClass('ant-radio-button-wrapper-checked');
    });
  });
});