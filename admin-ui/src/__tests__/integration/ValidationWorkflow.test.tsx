import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Validation } from '../../pages/validation/Validation';
import { ProcessingHistory } from '../../pages/validation/ProcessingHistory';
import { TestWrapper, mockValidationResult, mockFetch } from '../../test-utils';

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

// Mock Refine hooks for profiles and history
const mockCustom = jest.fn();

jest.mock('@refinedev/core', () => ({
  ...jest.requireActual('@refinedev/core'),
  useCustom: (params: any) => {
    if (params?.url?.includes('/profiles')) {
      return { 
        data: { data: [
          { name: 'Standard Claims' },
          { name: 'Priority Claims' },
          { name: 'Dental Claims' }
        ] }, 
        isLoading: false 
      };
    }
    if (params?.url?.includes('/processing-logs')) {
      return {
        data: {
          data: [
            {
              id: 1,
              file_name: 'claim_001.edi',
              validation_result: 'VALID',
              processing_time_ms: 250,
              created_at: '2025-01-09T10:30:00Z',
              schema_name: '837.5010.X222.A1.json',
              snip_level_used: 'SNIP3',
              matched_profile: 'Standard Claims'
            },
            {
              id: 2,
              file_name: 'claim_002.edi',
              validation_result: 'INVALID',
              processing_time_ms: 180,
              created_at: '2025-01-09T10:25:00Z',
              schema_name: '837.5010.X222.A1.json',
              snip_level_used: 'SNIP3',
              matched_profile: 'Priority Claims',
              error_count: 3
            }
          ]
        },
        isLoading: false
      };
    }
    return { data: { data: [] }, isLoading: false };
  }
}));

describe('End-to-End Validation Workflow', () => {
  const user = userEvent.setup();

  const validEdiData = `ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250109*1234*^*00501*000000001*0*T*:~
GS*HC*SENDER*RECEIVER*20250109*1234*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*123456789*20250109*1234*CH~
NM1*41*2*SUBMITTER*****46*12345~
SE*5*0001~
GE*1*1~
IEA*1*000000001~`;

  const invalidEdiData = `ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250109*INVALID*^*00501*000000001*0*T*:~
GS*HC*SENDER*RECEIVER*20250109*1234*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*123456789*20250109*1234*CH~
SE*4*0001~
GE*1*1~
IEA*1*MISMATCH~`;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Complete Validation Workflow with Auto-Detection', () => {
    it('validates EDI with auto-detection and downloads results', async () => {
      const successResult = {
        ...mockValidationResult,
        valid: true,
        matched_profile: 'Standard Claims',
        detection_method: 'auto'
      };

      mockAxios.post.mockResolvedValueOnce({ data: successResult });

      // Mock file download functionality
      const mockCreateObjectURL = jest.fn(() => 'blob:mock-url');
      const mockRevokeObjectURL = jest.fn();
      global.URL.createObjectURL = mockCreateObjectURL;
      global.URL.revokeObjectURL = mockRevokeObjectURL;

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Input EDI data
      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, validEdiData);

      // Validate with auto-detection (default)
      const validateButton = screen.getByText('Validate EDI');
      expect(validateButton.closest('button')).toBeEnabled();
      await user.click(validateButton);

      // Verify API call
      await waitFor(() => {
        expect(mockAxios.post).toHaveBeenCalledWith('/api/v1/validate', {
          edi_data: validEdiData,
          file_name: 'pasted_content.edi'
        });
      });

      // Verify results display
      await waitFor(() => {
        expect(screen.getByText('Validation Complete')).toBeInTheDocument();
        expect(screen.getByText('Valid')).toBeInTheDocument();
        expect(screen.getByText('Standard Claims')).toBeInTheDocument();
        expect(screen.getByText('Auto-detection')).toBeInTheDocument();
      });

      // Test TA1 download
      const ta1DownloadButton = screen.getByText('Download TA1');
      await user.click(ta1DownloadButton);

      expect(mockCreateObjectURL).toHaveBeenCalled();

      // Test results export
      const exportButton = screen.getByText('Export Results');
      await user.click(exportButton);

      expect(mockCreateObjectURL).toHaveBeenCalledTimes(2);
    });

    it('validates EDI with manual profile selection', async () => {
      const manualResult = {
        ...mockValidationResult,
        valid: true,
        matched_profile: 'Priority Claims',
        detection_method: 'manual'
      };

      mockAxios.post.mockResolvedValueOnce({ data: manualResult });

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Switch to manual profile selection
      const manualButton = screen.getByText('Manual Selection');
      await user.click(manualButton);

      // Select profile
      await waitFor(() => {
        const profileSelect = screen.getByPlaceholderText('Select a profile...');
        fireEvent.mouseDown(profileSelect);
      });

      await waitFor(() => {
        const priorityOption = screen.getByText('Priority Claims');
        fireEvent.click(priorityOption);
      });

      // Input EDI data
      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, validEdiData);

      // Validate
      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      // Verify API call with profile name
      await waitFor(() => {
        expect(mockAxios.post).toHaveBeenCalledWith('/api/v1/validate', {
          edi_data: validEdiData,
          file_name: 'pasted_content.edi',
          profile_name: 'Priority Claims'
        });
      });

      // Verify results show manual detection
      await waitFor(() => {
        expect(screen.getByText('Priority Claims')).toBeInTheDocument();
        expect(screen.getByText('Manual selection')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling Workflow', () => {
    it('handles validation errors and shows findings', async () => {
      const errorResult = {
        valid: false,
        status: 'Rejected at Interchange Level',
        matched_profile: 'Standard Claims',
        detection_method: 'auto',
        processing_time_ms: 120,
        schema_used: '837.5010.X222.A1.json',
        snip_level_used: 'SNIP3',
        findings: [
          {
            level: 'error',
            code: 'ISA_013',
            message: 'Invalid interchange control number format',
            location: {
              segment_id: 'ISA',
              segment_instance: 1,
              element_position: 13,
              line_number: 1
            }
          },
          {
            level: 'error',
            code: 'IEA_001',
            message: 'Interchange control number mismatch',
            location: {
              segment_id: 'IEA',
              segment_instance: 1,
              element_position: 2,
              line_number: 7
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
      await user.type(textarea, invalidEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      // Verify error status display
      await waitFor(() => {
        expect(screen.getByText('Rejected at Interchange Level')).toBeInTheDocument();
        expect(screen.getByText('Invalid')).toBeInTheDocument();
        expect(screen.getByText('2 issues found')).toBeInTheDocument();
      });

      // Verify error details
      expect(screen.getByText('Invalid interchange control number format')).toBeInTheDocument();
      expect(screen.getByText('Interchange control number mismatch')).toBeInTheDocument();
      expect(screen.getByText('ISA_013')).toBeInTheDocument();
      expect(screen.getByText('IEA_001')).toBeInTheDocument();
    });

    it('handles API errors gracefully', async () => {
      mockAxios.post.mockRejectedValueOnce({
        response: {
          status: 400,
          data: { detail: 'Invalid EDI format: Missing ISA segment' }
        }
      });

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, 'INVALID EDI CONTENT');

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        expect(screen.getByText(/Invalid EDI format: Missing ISA segment/)).toBeInTheDocument();
      });
    });

    it('handles network errors', async () => {
      mockAxios.post.mockRejectedValueOnce(new Error('Network Error'));

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, validEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        expect(screen.getByText(/Validation failed/)).toBeInTheDocument();
        expect(screen.getByText(/Please try again/)).toBeInTheDocument();
      });
    });
  });

  describe('File Upload Workflow', () => {
    it('validates uploaded EDI file', async () => {
      mockAxios.post.mockResolvedValueOnce({ data: mockValidationResult });

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const file = new File([validEdiData], 'test_claim.edi', { type: 'text/plain' });
      const uploadInput = screen.getByRole('button', { name: /upload/i }).querySelector('input[type="file"]');

      if (uploadInput) {
        await user.upload(uploadInput, file);

        // Verify file content is loaded
        await waitFor(() => {
          const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
          expect(textarea).toHaveValue(validEdiData);
        });

        // Validate the uploaded file
        const validateButton = screen.getByText('Validate EDI');
        await user.click(validateButton);

        // Verify API call uses uploaded filename
        await waitFor(() => {
          expect(mockAxios.post).toHaveBeenCalledWith('/api/v1/validate', {
            edi_data: validEdiData,
            file_name: 'test_claim.edi'
          });
        });
      }
    });

    it('rejects files that are too large', async () => {
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

        // Validate button should remain disabled
        const validateButton = screen.getByText('Validate EDI');
        expect(validateButton.closest('button')).toBeDisabled();
      }
    });
  });

  describe('EDI Structure Analysis Workflow', () => {
    it('displays comprehensive EDI structure analysis', async () => {
      const detailedResult = {
        ...mockValidationResult,
        edi_structure: {
          interchange: {
            sender: 'SENDER',
            receiver: 'RECEIVER',
            control_number: '000000001',
            date: '250109',
            time: '1234'
          },
          functional_groups: [{
            functional_id: 'HC',
            application_sender: 'SENDER',
            application_receiver: 'RECEIVER',
            version: '005010X222A1',
            control_number: '1'
          }],
          transaction_sets: [{
            transaction_code: '837',
            control_number: '0001',
            segment_count: 5
          }],
          segment_breakdown: {
            'ISA': 1,
            'GS': 1,
            'ST': 1,
            'BHT': 1,
            'NM1': 1,
            'SE': 1,
            'GE': 1,
            'IEA': 1
          }
        }
      };

      mockAxios.post.mockResolvedValueOnce({ data: detailedResult });

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, validEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        expect(screen.getByText('EDI Structure Analysis')).toBeInTheDocument();
        
        // Interchange details
        expect(screen.getByText('SENDER')).toBeInTheDocument();
        expect(screen.getByText('RECEIVER')).toBeInTheDocument();
        expect(screen.getByText('000000001')).toBeInTheDocument();
        
        // Functional group details
        expect(screen.getByText('HC')).toBeInTheDocument();
        expect(screen.getByText('005010X222A1')).toBeInTheDocument();
        
        // Transaction details
        expect(screen.getByText('837')).toBeInTheDocument();
        expect(screen.getByText('Transaction Sets: 1')).toBeInTheDocument();
      });
    });
  });

  describe('Processing History Integration', () => {
    it('displays processing history with filtering', async () => {
      render(
        <TestWrapper>
          <ProcessingHistory />
        </TestWrapper>
      );

      // Verify history is loaded
      await waitFor(() => {
        expect(screen.getByText('Processing History')).toBeInTheDocument();
        expect(screen.getByText('claim_001.edi')).toBeInTheDocument();
        expect(screen.getByText('claim_002.edi')).toBeInTheDocument();
      });

      // Verify success/failure indicators
      expect(screen.getByText('VALID')).toBeInTheDocument();
      expect(screen.getByText('INVALID')).toBeInTheDocument();

      // Test filtering by result
      const resultFilter = screen.getByPlaceholderText('Filter by result');
      await user.click(resultFilter);
      await user.click(screen.getByText('Valid Only'));

      // Should filter out invalid entries
      await waitFor(() => {
        expect(screen.getByText('claim_001.edi')).toBeInTheDocument();
        expect(screen.queryByText('claim_002.edi')).not.toBeInTheDocument();
      });
    });

    it('allows detailed view of processing history entry', async () => {
      render(
        <TestWrapper>
          <ProcessingHistory />
        </TestWrapper>
      );

      await waitFor(() => {
        expect(screen.getByText('claim_001.edi')).toBeInTheDocument();
      });

      // Click on a history entry to view details
      const viewButton = screen.getAllByText('View')[0];
      await user.click(viewButton);

      await waitFor(() => {
        expect(screen.getByText('Processing Details')).toBeInTheDocument();
        expect(screen.getByText('250ms')).toBeInTheDocument();
        expect(screen.getByText('SNIP3')).toBeInTheDocument();
        expect(screen.getByText('Standard Claims')).toBeInTheDocument();
      });
    });
  });

  describe('Cross-Component Data Flow', () => {
    it('validates EDI, then views in processing history', async () => {
      // Mock successful validation
      mockAxios.post.mockResolvedValueOnce({ data: mockValidationResult });
      
      // Mock updated processing history that includes new entry
      const updatedHistory = {
        data: [
          {
            id: 3,
            file_name: 'new_validation.edi',
            validation_result: 'VALID',
            processing_time_ms: 200,
            created_at: new Date().toISOString(),
            schema_name: '837.5010.X222.A1.json',
            snip_level_used: 'SNIP3',
            matched_profile: 'Test Profile'
          }
        ]
      };

      // First render validation component
      const { rerender } = render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Perform validation
      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, validEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        expect(screen.getByText('Validation Complete')).toBeInTheDocument();
      });

      // Now switch to processing history
      rerender(
        <TestWrapper>
          <ProcessingHistory />
        </TestWrapper>
      );

      // Verify original entries are still there
      await waitFor(() => {
        expect(screen.getByText('claim_001.edi')).toBeInTheDocument();
        expect(screen.getByText('claim_002.edi')).toBeInTheDocument();
      });
    });
  });

  describe('Performance and User Experience', () => {
    it('maintains responsive UI during long validations', async () => {
      // Simulate slow API response
      mockAxios.post.mockImplementationOnce(() =>
        new Promise(resolve => 
          setTimeout(() => resolve({ data: mockValidationResult }), 2000)
        )
      );

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, validEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      // Verify loading state
      expect(screen.getByText('Validating...')).toBeInTheDocument();
      expect(validateButton.closest('button')).toBeDisabled();

      // User should still be able to interact with other elements
      const profileButton = screen.getByText('Manual Selection');
      await user.click(profileButton);

      expect(screen.getByPlaceholderText('Select a profile...')).toBeInTheDocument();

      // Wait for validation to complete
      await waitFor(() => {
        expect(screen.getByText('Validation Complete')).toBeInTheDocument();
      }, { timeout: 3000 });
    });

    it('provides clear feedback for user actions', async () => {
      mockAxios.post.mockResolvedValueOnce({ data: mockValidationResult });

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Initially validation should be disabled
      const validateButton = screen.getByText('Validate EDI');
      expect(validateButton.closest('button')).toBeDisabled();

      // Adding content should enable validation
      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, 'ISA');

      expect(validateButton.closest('button')).toBeEnabled();

      // Clearing content should disable again
      await user.clear(textarea);
      expect(validateButton.closest('button')).toBeDisabled();

      // Re-add content and validate
      await user.type(textarea, validEdiData);
      await user.click(validateButton);

      // Success feedback
      await waitFor(() => {
        expect(screen.getByText('Validation Complete')).toBeInTheDocument();
        const successTag = screen.getByText('Valid');
        expect(successTag).toHaveClass('ant-tag-success');
      });
    });
  });
});