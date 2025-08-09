export * from './TestWrapper';

// Common test utilities
export const mockSftpConfiguration = {
  id: 1,
  partner_id: 1,
  username: 'test-partner',
  authentication_type: 'PASSWORD' as const,
  password: 'test-password',
  ssh_private_key: null,
  file_patterns: ['*.edi', '*.txt'],
  is_active: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

export const mockTradingPartner = {
  id: 1,
  name: 'Test Partner',
  tenant_id: 'tenant-1',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  profiles: []
};

export const mockProfile = {
  id: 1,
  name: 'Test Profile',
  validation_schema_name: '837.5010.X222.A1.json',
  snip_level: 'SNIP3' as const,
  generate_ta1: true,
  generate_999: false,
  criteria: [
    {
      field_source: 'ISA' as const,
      field_identifier: 'ISA06',
      operator: 'EQUALS' as const,
      expected_value: 'TEST123'
    }
  ]
};

export const mockValidationResult = {
  valid: true,
  status: 'Validation Complete',
  matched_profile: 'Test Profile',
  detection_method: 'auto',
  processing_time_ms: 250,
  schema_used: '837.5010.X222.A1.json',
  snip_level_used: 'SNIP3',
  ta1_content: 'ISA*00*          *00*          *ZZ*SENDER         *ZZ*RECEIVER       *250109*1234*^*00501*000000001*0*T*:~TA1*000000001*A*000*~IEA*1*000000001~',
  findings: []
};

// Mock fetch for API calls
export const mockFetch = (data: any, ok = true, status = 200) => {
  return jest.fn(() =>
    Promise.resolve({
      ok,
      status,
      json: () => Promise.resolve(data),
      text: () => Promise.resolve(typeof data === 'string' ? data : JSON.stringify(data))
    })
  );
};