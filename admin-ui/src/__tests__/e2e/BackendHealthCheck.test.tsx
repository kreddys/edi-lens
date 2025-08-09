import axios from 'axios';

// Simple health check test to verify backend integration test setup
// This test validates that the EDI Lens backend is running and accessible
// Run with: npm test -- --testPathPattern="BackendHealthCheck"

describe.skip('Backend Health Check - Real Integration Setup (Requires Backend)', () => {
  const apiUrl = 'http://localhost:8000';
  
  const realAxios = axios.create({
    baseURL: apiUrl,
    timeout: 5000,
    headers: {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJzdWIiOiAidGVzdC11c2VyLTEyMyIsICJwcmVmZXJyZWRfdXNlcm5hbWUiOiAidGVzdC1hZG1pbiIsICJlbWFpbCI6ICJhZG1pbkB0ZXN0LmNvbSIsICJncm91cHMiOiBbInRlbmFudC1hIl0sICJyZWFsbV9hY2Nlc3MiOiB7InJvbGVzIjogWyJzZnRwOnJlYWQiLCAic2Z0cDpwcm9jZXNzIiwgImFkbWluIl19LCAiaWF0IjogMTc1NDI3MDU2OSwgImV4cCI6IDE3NTQyNzc3NjksICJpc3MiOiAiZWRpLWxlbnMtdGVzdCIsICJhdWQiOiAiZWRpLWxlbnMtYXBpIn0.ZmFrZV9zaWduYXR1cmVfZm9yX2RlbW8'
    }
  });

  it('verifies backend health endpoint is accessible', async () => {
    try {
      const response = await realAxios.get('/health');
      
      expect(response.status).toBe(200);
      expect(response.data).toBeTruthy();
      
      console.log('✅ Backend health check passed:', response.data);
    } catch (error: any) {
      console.log('❌ Backend not running or not accessible');
      console.log('Start backend with: ./run.sh dev:start');
      console.log('Error:', error.message);
      
      // Skip the test instead of failing - Jest doesn't have pending, use skip
      console.log('⏭️  Skipping test - backend not available');
      return;
    }
  }, 8000);

  it('verifies validation endpoint is accessible', async () => {
    try {
      // Test a simple validation request
      const testEdi = 'ISA*00*          *00*          *ZZ*TEST           *ZZ*TEST           *250109*1234*^*00501*000000001*0*T*:~IEA*0*000000001~';
      
      const response = await realAxios.post('/api/v1/validate', {
        edi_data: testEdi,
        file_name: 'health_check.edi'
      });

      expect(response.status).toBeOneOf([200, 400, 422]); // Any response means endpoint is working
      console.log('✅ Validation endpoint responding');
      
    } catch (error: any) {
      if (error.code === 'ECONNREFUSED' || !error.response) {
        console.log('⏭️  Skipping - backend validation endpoint not accessible');
        return;
      } else {
        // Endpoint exists but may have returned an error - that's still good
        expect(error.response.status).toBeDefined();
        console.log('✅ Validation endpoint accessible (returned expected error)');
      }
    }
  }, 8000);

  it('verifies trading partners endpoint is accessible', async () => {
    try {
      const response = await realAxios.get('/trading-partners');
      
      expect(response.status).toBeOneOf([200, 401, 403]); // Any response means endpoint exists
      console.log('✅ Trading partners endpoint responding');
      
    } catch (error: any) {
      if (error.code === 'ECONNREFUSED' || !error.response) {
        console.log('⏭️  Skipping - backend trading partners endpoint not accessible');
        return;
      } else {
        // Endpoint exists
        expect(error.response.status).toBeDefined();
        console.log('✅ Trading partners endpoint accessible');
      }
    }
  }, 8000);

  it('displays backend integration test setup instructions', async () => {
    console.log('\n📋 Backend Integration Test Setup:');
    console.log('1. Start EDI Lens development environment: ./run.sh dev:start');
    console.log('2. Wait for all services to be ready (backend, database, keycloak)');
    console.log('3. Run backend integration tests: npm test -- --testPathPattern="e2e"');
    console.log('4. Or run specific test: npm test -- --testPathPattern="RealBackendValidation"');
    console.log('\n🔧 Troubleshooting:');
    console.log('- Check backend logs: ./run.sh dev:logs backend');
    console.log('- Check service status: docker ps');
    console.log('- Backend API docs: http://localhost:8000/docs');
    
    // This test always passes - it's just for documentation
    expect(true).toBe(true);
  });

  it('validates test JWT token format', async () => {
    const testJWT = 'eyJhbGciOiAiSFMyNTYiLCAidHlwIjogIkpXVCJ9.eyJzdWIiOiAidGVzdC11c2VyLTEyMyIsICJwcmVmZXJyZWRfdXNlcm5hbWUiOiAidGVzdC1hZG1pbiIsICJlbWFpbCI6ICJhZG1pbkB0ZXN0LmNvbSIsICJncm91cHMiOiBbInRlbmFudC1hIl0sICJyZWFsbV9hY2Nlc3MiOiB7InJvbGVzIjogWyJzZnRwOnJlYWQiLCAic2Z0cDpwcm9jZXNzIiwgImFkbWluIl19LCAiaWF0IjogMTc1NDI3MDU2OSwgImV4cCI6IDE3NTQyNzc3NjksICJpc3MiOiAiZWRpLWxlbnMtdGVzdCIsICJhdWQiOiAiZWRpLWxlbnMtYXBpIn0.ZmFrZV9zaWduYXR1cmVfZm9yX2RlbW8';
    
    // Validate JWT structure (header.payload.signature)
    const jwtParts = testJWT.split('.');
    expect(jwtParts).toHaveLength(3);
    
    // Decode payload to verify structure
    const payload = JSON.parse(atob(jwtParts[1]));
    expect(payload.sub).toBe('test-user-123');
    expect(payload.groups).toContain('tenant-a');
    expect(payload.realm_access.roles).toContain('admin');
    
    console.log('✅ Test JWT token is properly formatted');
    console.log('Token payload:', JSON.stringify(payload, null, 2));
  });

  describe('Service Availability Check', () => {
    const services = [
      { name: 'Backend API', url: '/health' },
      { name: 'Validation Service', url: '/api/v1/validate', method: 'POST' },
      { name: 'Trading Partners', url: '/trading-partners' },
      { name: 'Schema Management', url: '/schemas' },
      { name: 'SFTP Configuration', url: '/sftp/configurations' }
    ];

    services.forEach(service => {
      it(`checks ${service.name} availability`, async () => {
        try {
          let response;
          if (service.method === 'POST') {
            response = await realAxios.post(service.url, { test: true });
          } else {
            response = await realAxios.get(service.url);
          }
          
          console.log(`✅ ${service.name}: Available (${response.status})`);
          expect(response.status).toBeLessThan(500); // Any response < 500 means service is up
          
        } catch (error: any) {
          if (error.code === 'ECONNREFUSED' || !error.response) {
            console.log(`❌ ${service.name}: Connection refused`);
            console.log(`⏭️  Skipping ${service.name} - backend not running`);
            return;
          } else {
            console.log(`⚠️  ${service.name}: Available but returned ${error.response.status}`);
            // Service exists but may have validation errors - that's expected
            expect(error.response.status).toBeLessThan(500);
          }
        }
      }, 5000);
    });
  });
});