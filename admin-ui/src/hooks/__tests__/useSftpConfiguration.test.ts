import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import { useSftpConfiguration } from '../useSftpConfiguration';
import { mockSftpConfiguration } from '../../test-utils';

// Mock axios - define functions directly in mock
jest.mock('axios', () => ({
  create: () => ({
    post: jest.fn(),
    put: jest.fn(),
    get: jest.fn(),
    delete: jest.fn()
  }),
  post: jest.fn(),
  put: jest.fn(),
  get: jest.fn(),
  delete: jest.fn()
}));

// Get the mocked axios functions
const mockAxios = {
  post: jest.fn(),
  put: jest.fn(),
  get: jest.fn(),
  delete: jest.fn()
};

// Test wrapper with QueryClient
const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  });

  const TestProvider = ({ children }: { children: React.ReactNode }) => (
    React.createElement(QueryClientProvider, { client: queryClient }, children)
  );
  
  return TestProvider;
};

describe('useSftpConfiguration', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('createConfiguration', () => {
    it('creates SFTP configuration with password authentication', async () => {
      const newConfig = {
        partner_id: 1,
        username: 'test-partner',
        authentication_type: 'PASSWORD' as const,
        password: 'secure-password',
        ssh_private_key: null,
        file_patterns: ['*.edi', '*.txt'],
        is_active: true
      };

      const createdConfig = {
        ...newConfig,
        id: 1,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };

      mockAxios.post.mockResolvedValueOnce({ data: createdConfig });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      const promise = result.current.createConfiguration(newConfig);

      await waitFor(() => {
        expect(mockAxios.post).toHaveBeenCalledWith('/api/v1/sftp/configurations', newConfig);
      });

      const response = await promise;
      expect(response).toEqual(createdConfig);
    });

    it('creates SFTP configuration with SSH key authentication', async () => {
      const sshKey = `-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAABAAAAFwAAAAdzc2gtcn
NhAAAAAwEAAQAAAQEA1234567890...
-----END OPENSSH PRIVATE KEY-----`;

      const newConfig = {
        partner_id: 2,
        username: 'ssh-partner',
        authentication_type: 'SSH_KEY' as const,
        password: null,
        ssh_private_key: sshKey,
        file_patterns: ['*.x12'],
        is_active: true
      };

      const createdConfig = {
        ...newConfig,
        id: 2,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };

      mockAxios.post.mockResolvedValueOnce({ data: createdConfig });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      const response = await result.current.createConfiguration(newConfig);

      expect(mockAxios.post).toHaveBeenCalledWith('/api/v1/sftp/configurations', newConfig);
      expect(response).toEqual(createdConfig);
    });

    it('creates SFTP configuration with both authentication methods', async () => {
      const newConfig = {
        partner_id: 3,
        username: 'hybrid-partner',
        authentication_type: 'BOTH' as const,
        password: 'backup-password',
        ssh_private_key: '-----BEGIN OPENSSH PRIVATE KEY-----\n...',
        file_patterns: ['*.edi', '*.x12', '*.txt'],
        is_active: true
      };

      const createdConfig = {
        ...newConfig,
        id: 3,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };

      mockAxios.post.mockResolvedValueOnce({ data: createdConfig });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      const response = await result.current.createConfiguration(newConfig);

      expect(mockAxios.post).toHaveBeenCalledWith('/api/v1/sftp/configurations', newConfig);
      expect(response).toEqual(createdConfig);
    });

    it('handles creation errors gracefully', async () => {
      const newConfig = {
        partner_id: 1,
        username: 'existing-user',
        authentication_type: 'PASSWORD' as const,
        password: 'password',
        ssh_private_key: null,
        file_patterns: ['*.edi'],
        is_active: true
      };

      const errorResponse = {
        response: {
          status: 409,
          data: { detail: 'SFTP user already exists' }
        }
      };

      mockAxios.post.mockRejectedValueOnce(errorResponse);

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      await expect(result.current.createConfiguration(newConfig)).rejects.toEqual(errorResponse);
      
      expect(result.current.error).toBe('SFTP user already exists');
    });

    it('validates required fields before creation', async () => {
      const invalidConfig = {
        partner_id: 1,
        username: '', // Empty username
        authentication_type: 'PASSWORD' as const,
        password: 'password',
        ssh_private_key: null,
        file_patterns: [],
        is_active: true
      };

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      await expect(result.current.createConfiguration(invalidConfig)).rejects.toThrow('Username is required');
    });

    it('validates authentication type requirements', async () => {
      const configMissingPassword = {
        partner_id: 1,
        username: 'test-user',
        authentication_type: 'PASSWORD' as const,
        password: null, // Missing password
        ssh_private_key: null,
        file_patterns: ['*.edi'],
        is_active: true
      };

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      await expect(result.current.createConfiguration(configMissingPassword)).rejects.toThrow('Password is required for PASSWORD authentication');
    });
  });

  describe('updateConfiguration', () => {
    it('updates existing SFTP configuration', async () => {
      const configId = 1;
      const updateData = {
        username: 'updated-partner',
        file_patterns: ['*.edi', '*.x12', '*.txt'],
        is_active: false
      };

      const updatedConfig = {
        ...mockSftpConfiguration,
        ...updateData,
        updated_at: new Date().toISOString()
      };

      mockAxios.put.mockResolvedValueOnce({ data: updatedConfig });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      const response = await result.current.updateConfiguration(configId, updateData);

      expect(mockAxios.put).toHaveBeenCalledWith(`/api/v1/sftp/configurations/${configId}`, updateData);
      expect(response).toEqual(updatedConfig);
    });

    it('handles update errors', async () => {
      const configId = 999;
      const updateData = { username: 'new-name' };

      const errorResponse = {
        response: {
          status: 404,
          data: { detail: 'SFTP configuration not found' }
        }
      };

      mockAxios.put.mockRejectedValueOnce(errorResponse);

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      await expect(result.current.updateConfiguration(configId, updateData)).rejects.toEqual(errorResponse);
      
      expect(result.current.error).toBe('SFTP configuration not found');
    });

    it('updates authentication credentials securely', async () => {
      const configId = 1;
      const updateData = {
        authentication_type: 'SSH_KEY' as const,
        password: null,
        ssh_private_key: '-----BEGIN OPENSSH PRIVATE KEY-----\nnew-key-content\n-----END OPENSSH PRIVATE KEY-----'
      };

      const updatedConfig = {
        ...mockSftpConfiguration,
        ...updateData,
        updated_at: new Date().toISOString()
      };

      mockAxios.put.mockResolvedValueOnce({ data: updatedConfig });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      const response = await result.current.updateConfiguration(configId, updateData);

      expect(mockAxios.put).toHaveBeenCalledWith(`/api/v1/sftp/configurations/${configId}`, updateData);
      expect(response.ssh_private_key).toBe(updateData.ssh_private_key);
      expect(response.password).toBeNull();
    });
  });

  describe('deleteConfiguration', () => {
    it('deletes SFTP configuration', async () => {
      const configId = 1;

      mockAxios.delete.mockResolvedValueOnce({ data: { success: true } });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      await result.current.deleteConfiguration(configId);

      expect(mockAxios.delete).toHaveBeenCalledWith(`/api/v1/sftp/configurations/${configId}`);
    });

    it('handles deletion errors', async () => {
      const configId = 999;

      const errorResponse = {
        response: {
          status: 404,
          data: { detail: 'Configuration not found' }
        }
      };

      mockAxios.delete.mockRejectedValueOnce(errorResponse);

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      await expect(result.current.deleteConfiguration(configId)).rejects.toEqual(errorResponse);
      
      expect(result.current.error).toBe('Configuration not found');
    });
  });

  describe('getConfiguration', () => {
    it('retrieves SFTP configuration by ID', async () => {
      const configId = 1;

      mockAxios.get.mockResolvedValueOnce({ data: mockSftpConfiguration });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      const response = await result.current.getConfiguration(configId);

      expect(mockAxios.get).toHaveBeenCalledWith(`/api/v1/sftp/configurations/${configId}`);
      expect(response).toEqual(mockSftpConfiguration);
    });

    it('handles retrieval errors', async () => {
      const configId = 999;

      const errorResponse = {
        response: {
          status: 404,
          data: { detail: 'Configuration not found' }
        }
      };

      mockAxios.get.mockRejectedValueOnce(errorResponse);

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      await expect(result.current.getConfiguration(configId)).rejects.toEqual(errorResponse);
    });
  });

  describe('testConnection', () => {
    it('tests SFTP connection successfully', async () => {
      const configId = 1;
      const testResult = {
        success: true,
        message: 'Connection successful',
        details: {
          hostname: 'sftp.example.com',
          port: 22,
          username: 'test-partner',
          connection_time_ms: 150
        }
      };

      mockAxios.post.mockResolvedValueOnce({ data: testResult });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      const response = await result.current.testConnection(configId);

      expect(mockAxios.post).toHaveBeenCalledWith(`/api/v1/sftp/configurations/${configId}/test`);
      expect(response).toEqual(testResult);
    });

    it('handles connection test failures', async () => {
      const configId = 1;
      const testResult = {
        success: false,
        message: 'Authentication failed',
        details: {
          error: 'Invalid credentials',
          hostname: 'sftp.example.com',
          port: 22,
          username: 'test-partner'
        }
      };

      mockAxios.post.mockResolvedValueOnce({ data: testResult });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      const response = await result.current.testConnection(configId);

      expect(response.success).toBe(false);
      expect(response.message).toBe('Authentication failed');
    });
  });

  describe('Loading States', () => {
    it('sets loading state during operations', async () => {
      mockAxios.post.mockImplementationOnce(() => 
        new Promise(resolve => setTimeout(() => resolve({ data: mockSftpConfiguration }), 100))
      );

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      const promise = result.current.createConfiguration({
        partner_id: 1,
        username: 'test',
        authentication_type: 'PASSWORD',
        password: 'password',
        ssh_private_key: null,
        file_patterns: ['*.edi'],
        is_active: true
      });

      expect(result.current.isLoading).toBe(true);

      await promise;
      
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false);
      });
    });
  });

  describe('Error Handling', () => {
    it('clears errors between operations', async () => {
      // First operation fails
      mockAxios.post.mockRejectedValueOnce({
        response: { status: 400, data: { detail: 'Bad request' }}
      });

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      try {
        await result.current.createConfiguration({
          partner_id: 1,
          username: 'test',
          authentication_type: 'PASSWORD',
          password: 'password',
          ssh_private_key: null,
          file_patterns: ['*.edi'],
          is_active: true
        });
      } catch (e) {
        // Expected to fail
      }

      expect(result.current.error).toBe('Bad request');

      // Second operation succeeds
      mockAxios.post.mockResolvedValueOnce({ data: mockSftpConfiguration });

      await result.current.createConfiguration({
        partner_id: 2,
        username: 'test2',
        authentication_type: 'PASSWORD',
        password: 'password',
        ssh_private_key: null,
        file_patterns: ['*.edi'],
        is_active: true
      });

      expect(result.current.error).toBeNull();
    });

    it('extracts error messages from different response formats', async () => {
      const errorFormats = [
        {
          response: { status: 400, data: { detail: 'Validation error' } },
          expectedMessage: 'Validation error'
        },
        {
          response: { status: 500, data: { message: 'Server error' } },
          expectedMessage: 'Server error'
        },
        {
          response: { status: 403, data: 'Forbidden' },
          expectedMessage: 'Forbidden'
        },
        {
          message: 'Network error'
        }
      ];

      const wrapper = createWrapper();
      const { result } = renderHook(() => useSftpConfiguration(), { wrapper });

      for (const errorFormat of errorFormats) {
        mockAxios.post.mockRejectedValueOnce(errorFormat);
        
        try {
          await result.current.createConfiguration({
            partner_id: 1,
            username: 'test',
            authentication_type: 'PASSWORD',
            password: 'password',
            ssh_private_key: null,
            file_patterns: ['*.edi'],
            is_active: true
          });
        } catch (e) {
          // Expected to fail
        }

        if ('expectedMessage' in errorFormat) {
          expect(result.current.error).toBe(errorFormat.expectedMessage);
        } else {
          expect(result.current.error).toBe('Network error');
        }
      }
    });
  });
});