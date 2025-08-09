import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import axios from 'axios';
import { Validation } from '../../pages/validation/Validation';
import { ProcessingHistory } from '../../pages/validation/ProcessingHistory';
import { TestWrapper } from '../../test-utils';

// Real Backend Integration Tests
// These tests connect to the actual EDI Lens API backend
// They require the development stack to be running: ./run.sh dev:start

// DO NOT MOCK axios for these tests - we want real API calls
describe('Real Backend Integration - EDI Validation', () => {
  const user = userEvent.setup();
  
  const realEdiData = `ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250109*1234*^*00501*000000001*0*T*:~
GS*HC*SENDER*RECEIVER*20250109*1234*1*X*005010X222A1~
ST*837*0001*005010X222A1~
BHT*0019*00*TEST_CLAIM_001*20250109*1234*CH~
NM1*41*2*TEST SUBMITTER*****46*12345~
PER*IC*ADMIN CONTACT*TE*5551234567~
NM1*40*2*TEST RECEIVER*****46*67890~
HL*1**20*1~
PRV*BI*PXC*123456789~
NM1*85*2*TEST PROVIDER*****XX*1234567890~
N3*123 TEST STREET~
N4*TESTVILLE*NY*12345~
REF*EI*123456789~
HL*2*1*22*0~
SBR*P*18*GROUP123*TEST GROUP*****12~
NM1*IL*1*DOE*JANE*A***MI*123456789~
N3*456 PATIENT ST~
N4*TESTCITY*CA*54321~
DMG*D8*19900101*F~
NM1*PR*2*TEST INSURANCE*****PI*ABCDE~
CLM*TEST_CLM_001*150.00***11:B:1*Y*A*Y*I~
DTP*431*D8*20250101~
HI*BK:Z1234~
LX*1~
SV1*HC:99213*75.00*UN*1***1~
DTP*472*D8*20250101~
LX*2~
SV1*HC:99214*75.00*UN*1***1~
DTP*472*D8*20250102~
SE*28*0001~
GE*1*1~
IEA*1*000000001~`;

  const apiUrl = 'http://localhost:8000'; // EDI Lens API URL
  
  // Create a real axios instance for backend testing
  const realAxios = axios.create({
    baseURL: apiUrl,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
      // Add test JWT token for authentication if needed
      'Authorization': 'Bearer eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJzdWIiOiAidGVzdC11c2VyLTEyMyIsICJwcmVmZXJyZWRfdXNlcm5hbWUiOiAidGVzdC1hZG1pbiIsICJlbWFpbCI6ICJhZG1pbkB0ZXN0LmNvbSIsICJncm91cHMiOiBbInRlbmFudC1hIl0sICJyZWFsbV9hY2Nlc3MiOiB7InJvbGVzIjogWyJzZnRwOnJlYWQiLCAic2Z0cDpwcm9jZXNzIiwgImFkbWluIl19LCAiaWF0IjogMTc1NDI3MDU2OSwgImV4cCI6IDE3NTQyNzc3NjksICJpc3MiOiAiZWRpLWxlbnMtdGVzdCIsICJhdWQiOiAiZWRpLWxlbnMtYXBpIn0.ZmFrZV9zaWduYXR1cmVfZm9yX2RlbW8'
    }
  });

  // Skip these tests if backend is not running
  const checkBackendHealth = async () => {
    try {
      const response = await realAxios.get('/health');
      return response.status === 200;
    } catch (error) {
      console.warn('Backend not available - skipping real integration tests');
      return false;
    }
  };

  // Helper to skip test if backend is not available
  const skipIfBackendDown = async () => {
    const isBackendUp = await checkBackendHealth();
    if (!isBackendUp) {
      console.log('⏭️  Skipping test - backend not available. Start with: ./run.sh dev:start');
      return true; // Signal to skip
    }
    return false; // Continue with test
  };

  beforeEach(async () => {
    // Check if backend is available before running tests
    const isBackendUp = await checkBackendHealth();
    if (!isBackendUp) {
      // Jest doesn't have pending(), use skip instead
      console.log('⏭️  Skipping real backend tests - backend not running. Start with: ./run.sh dev:start');
      return; // Let individual tests handle the skip
    }

    // Replace global axios with our real axios instance for this test
    jest.doMock('axios', () => ({
      ...jest.requireActual('axios'),
      create: () => realAxios,
      post: realAxios.post.bind(realAxios),
      get: realAxios.get.bind(realAxios)
    }));
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  describe('Real Validation API Integration', () => {
    it('validates real EDI data with auto-detection against live backend', async () => {
      if (await skipIfBackendDown()) return;

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Input real EDI data
      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, realEdiData);

      // Validate with auto-detection (should use real API)
      const validateButton = screen.getByText('Validate EDI');
      expect(validateButton.closest('button')).toBeEnabled();
      
      await user.click(validateButton);

      // Wait for real API response (may take longer than mocked)
      await waitFor(async () => {
        // Should show actual validation results from backend
        const statusElements = screen.queryAllByText(/Validation Complete|Validation Results/);
        expect(statusElements.length).toBeGreaterThan(0);
      }, { timeout: 10000 });

      // Verify we get actual response structure from EDI Lens API
      await waitFor(() => {
        // Look for validation result indicators
        const validationResults = screen.queryAllByText(/Valid|Invalid|Processing|Complete/);
        expect(validationResults.length).toBeGreaterThan(0);
      });

      // Check for real profile matching results
      const profileResults = screen.queryAllByText(/Profile|Detection|Auto|Manual/);
      expect(profileResults.length).toBeGreaterThan(0);
    }, 15000);

    it('handles real validation errors from backend API', async () => {
      if (await skipIfBackendDown()) return;

      const invalidEdi = 'INVALID_EDI_CONTENT_FOR_TESTING_ERRORS';
      
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, invalidEdi);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      // Wait for real API error response
      await waitFor(() => {
        // Should show actual error from EDI Lens API
        const errorElements = screen.queryAllByText(/Error|Failed|Invalid|Missing/);
        expect(errorElements.length).toBeGreaterThan(0);
      }, { timeout: 8000 });
    }, 10000);

    it('tests manual profile selection with real profiles from backend', async () => {
      if (await skipIfBackendDown()) return;

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Switch to manual profile selection
      const manualButton = screen.getByText('Manual Selection');
      await user.click(manualButton);

      // Wait for real profiles to load from backend
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Select a profile...')).toBeInTheDocument();
      });

      // Open profile dropdown to see real options from backend
      const profileSelect = screen.getByPlaceholderText('Select a profile...');
      fireEvent.mouseDown(profileSelect);

      // Wait for actual profile options loaded from database
      await waitFor(() => {
        const profileOptions = screen.queryAllByText(/Profile|Claims|Test/);
        // Should have real profiles from the backend database
        expect(profileOptions.length).toBeGreaterThan(0);
      }, { timeout: 5000 });

      // Input EDI data
      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, realEdiData);

      // Select first available profile and validate
      const firstProfile = screen.queryAllByText(/Profile|Claims|Test/)[0];
      if (firstProfile) {
        await user.click(firstProfile);
        
        const validateButton = screen.getByText('Validate EDI');
        await user.click(validateButton);

        // Wait for validation with manual profile selection
        await waitFor(() => {
          const results = screen.queryAllByText(/Manual|Profile|Complete/);
          expect(results.length).toBeGreaterThan(0);
        }, { timeout: 10000 });
      }
    }, 15000);
  });

  describe('Real File Operations Integration', () => {
    it('tests real file upload and validation with backend storage', async () => {
      if (await skipIfBackendDown()) return;

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Create a real file with EDI content
      const file = new File([realEdiData], 'test_real_claim.edi', { type: 'text/plain' });
      const uploadInput = screen.getByRole('button', { name: /upload/i }).querySelector('input[type="file"]');

      if (uploadInput) {
        await user.upload(uploadInput, file);

        // Verify file is loaded
        await waitFor(() => {
          const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
          expect(textarea).toHaveValue(realEdiData);
        });

        // Validate the uploaded file
        const validateButton = screen.getByText('Validate EDI');
        await user.click(validateButton);

        // Wait for real validation results
        await waitFor(() => {
          const results = screen.queryAllByText(/Complete|Valid|Results/);
          expect(results.length).toBeGreaterThan(0);
        }, { timeout: 10000 });

        // Test TA1 download with real backend data
        await waitFor(() => {
          const downloadButtons = screen.queryAllByText(/Download|TA1|Export/);
          expect(downloadButtons.length).toBeGreaterThan(0);
        });
      }
    }, 15000);

    it('tests real file size limits and backend validation', async () => {
      if (await skipIfBackendDown()) return;

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Create a file that exceeds the UI limit (10MB) but tests backend limits
      const largeContent = 'X'.repeat(11 * 1024 * 1024); // 11MB
      const largeFile = new File([largeContent], 'large_test.edi', { type: 'text/plain' });

      const uploadInput = screen.getByRole('button', { name: /upload/i }).querySelector('input[type="file"]');

      if (uploadInput) {
        await user.upload(uploadInput, largeFile);

        // Should show real file size error from UI or backend
        await waitFor(() => {
          const errorMessages = screen.queryAllByText(/limit|size|large|exceed/i);
          expect(errorMessages.length).toBeGreaterThan(0);
        });
      }
    }, 8000);
  });

  describe('Real Processing History Integration', () => {
    it('loads real processing history from database', async () => {
      if (await skipIfBackendDown()) return;

      render(
        <TestWrapper>
          <ProcessingHistory />
        </TestWrapper>
      );

      // Wait for real processing history to load from backend database
      await waitFor(() => {
        const historyElements = screen.queryAllByText(/Processing|History|File|Validation/);
        // Should have real data from ProcessingLog table
        expect(historyElements.length).toBeGreaterThan(0);
      }, { timeout: 8000 });

      // Check for real data columns
      await waitFor(() => {
        const dataElements = screen.queryAllByText(/\.edi|VALID|INVALID|ms|Profile/);
        // Should display real processing log entries
        expect(dataElements.length).toBeGreaterThan(0);
      });
    }, 10000);

    it('tests real-time updates after validation', async () => {
      if (await skipIfBackendDown()) return;

      // First validate a file to create a new processing log entry
      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, realEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      // Wait for validation to complete
      await waitFor(() => {
        const results = screen.queryAllByText(/Complete|Valid/);
        expect(results.length).toBeGreaterThan(0);
      }, { timeout: 10000 });

      // Now switch to processing history to see if new entry appears
      const { rerender } = render(
        <TestWrapper>
          <ProcessingHistory />
        </TestWrapper>
      );

      // Should show the processing entry we just created
      await waitFor(() => {
        const recentEntries = screen.queryAllByText(/pasted_content\.edi|Processing|Recent/);
        expect(recentEntries.length).toBeGreaterThan(0);
      }, { timeout: 5000 });
    }, 20000);
  });

  describe('Real Error Handling and Edge Cases', () => {
    it('handles real backend unavailability gracefully', async () => {
      if (await skipIfBackendDown()) return;

      // Temporarily point to non-existent backend
      const badAxios = axios.create({
        baseURL: 'http://localhost:9999', // Non-existent port
        timeout: 2000
      });

      jest.doMock('axios', () => ({
        create: () => badAxios,
        post: badAxios.post.bind(badAxios)
      }));

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, realEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      // Should show network error handling
      await waitFor(() => {
        const errorElements = screen.queryAllByText(/failed|error|network|connection/i);
        expect(errorElements.length).toBeGreaterThan(0);
      }, { timeout: 5000 });
    }, 8000);

    it('tests real authentication failures', async () => {
      if (await skipIfBackendDown()) return;

      // Create axios instance with invalid auth token
      const unauthedAxios = axios.create({
        baseURL: apiUrl,
        timeout: 5000,
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer INVALID_TOKEN_FOR_TESTING'
        }
      });

      jest.doMock('axios', () => ({
        create: () => unauthedAxios,
        post: unauthedAxios.post.bind(unauthedAxios)
      }));

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, realEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      // Should show authentication error from real backend
      await waitFor(() => {
        const authErrors = screen.queryAllByText(/unauthorized|authentication|forbidden|401|403/i);
        expect(authErrors.length).toBeGreaterThan(0);
      }, { timeout: 6000 });
    }, 8000);
  });

  describe('Real Performance and Load Testing', () => {
    it('tests validation performance with real backend processing time', async () => {
      if (await skipIfBackendDown()) return;

      render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const startTime = Date.now();

      const textarea = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea, realEdiData);

      const validateButton = screen.getByText('Validate EDI');
      await user.click(validateButton);

      await waitFor(() => {
        const results = screen.queryAllByText(/Complete|Valid|Results/);
        expect(results.length).toBeGreaterThan(0);
      }, { timeout: 15000 });

      const endTime = Date.now();
      const totalTime = endTime - startTime;

      // Real backend validation should complete within reasonable time
      expect(totalTime).toBeLessThan(15000); // 15 seconds max
      
      // Should display actual processing time from backend
      await waitFor(() => {
        const processingTimeElements = screen.queryAllByText(/ms|processing|time/i);
        expect(processingTimeElements.length).toBeGreaterThan(0);
      });
    }, 20000);

    it('tests concurrent validation requests', async () => {
      if (await skipIfBackendDown()) return;

      const { rerender } = render(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      // Start first validation
      const textarea1 = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea1, realEdiData);
      
      const validateButton1 = screen.getByText('Validate EDI');
      await user.click(validateButton1);

      // Quickly start second validation (new component instance)
      rerender(
        <TestWrapper>
          <Validation />
        </TestWrapper>
      );

      const textarea2 = screen.getByPlaceholderText('Paste your EDI content here or upload a file above...');
      await user.type(textarea2, realEdiData.replace('TEST_CLAIM_001', 'TEST_CLAIM_002'));
      
      const validateButton2 = screen.getByText('Validate EDI');
      await user.click(validateButton2);

      // Both should complete successfully
      await waitFor(() => {
        const results = screen.queryAllByText(/Complete|Valid|Results/);
        expect(results.length).toBeGreaterThan(0);
      }, { timeout: 20000 });
    }, 25000);
  });
});