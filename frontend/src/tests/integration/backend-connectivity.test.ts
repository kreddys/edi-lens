/**
 * Backend Connectivity Integration Tests
 *
 * These tests verify that the frontend can connect to the real backend
 * and receive data in the expected format.
 */

import { flowAPI } from '../../providers/data';

// Test configuration
const BACKEND_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const TEST_TIMEOUT = 10000; // 10 seconds

describe('Backend Connectivity Integration Tests', () => {
  beforeAll(() => {
    console.log(`Testing backend connectivity at: ${BACKEND_URL}`);
  });

  describe('Health Endpoints', () => {
    test('should connect to backend health endpoint', async () => {
      const response = await fetch(`${BACKEND_URL}/health`);
      expect(response.ok).toBe(true);

      const healthData = await response.json();
      expect(healthData).toHaveProperty('status');
      expect(healthData.status).toBe('healthy');
      expect(healthData).toHaveProperty('nifi_url');
      expect(healthData).toHaveProperty('registry_url');
    }, TEST_TIMEOUT);
  });

  describe('Flow Registry Endpoints', () => {
    test('should list registry buckets', async () => {
      const buckets = await flowAPI.listBuckets();

      expect(Array.isArray(buckets)).toBe(true);

      if (buckets.length > 0) {
        const bucket = buckets[0];
        expect(bucket).toHaveProperty('bucket_id');
        expect(bucket).toHaveProperty('bucket_name');
        expect(bucket).toHaveProperty('description');
        expect(bucket).toHaveProperty('permissions');
        expect(typeof bucket.bucket_id).toBe('string');
        expect(typeof bucket.bucket_name).toBe('string');
      }
    }, TEST_TIMEOUT);

    test('should handle bucket flows listing', async () => {
      const buckets = await flowAPI.listBuckets();

      if (buckets.length > 0) {
        const bucketId = buckets[0].bucket_id;

        // This might return empty array if no flows exist, but should not error
        const flows = await flowAPI.listFlowsInBucket(bucketId);
        expect(Array.isArray(flows)).toBe(true);

        if (flows.length > 0) {
          const flow = flows[0];
          // Check if it has either 'identifier' or 'id' or 'flowId'
          expect(flow).toSatisfy((f: any) =>
            f.hasOwnProperty('identifier') ||
            f.hasOwnProperty('id') ||
            f.hasOwnProperty('flowId') ||
            f.hasOwnProperty('flow_id')
          );
          // Check for name property (could be 'name' or 'flowName')
          expect(flow).toSatisfy((f: any) =>
            f.hasOwnProperty('name') ||
            f.hasOwnProperty('flowName')
          );
          console.log('Flow data structure:', flow);
        }
      }
    }, TEST_TIMEOUT);
  });

  describe('Flow Management Endpoints', () => {
    test('should handle flow status requests gracefully', async () => {
      // Test with a non-existent process group ID
      const fakeProcessGroupId = 'test-process-group-id';

      try {
        await flowAPI.getStatus(fakeProcessGroupId);
        // If it doesn't throw, that's fine - the endpoint exists
      } catch (error: any) {
        // Should be a 404 or similar, not a connection error
        expect(error.response?.status).toBeDefined();
        expect([404, 400, 500].includes(error.response?.status)).toBe(true);
      }
    }, TEST_TIMEOUT);
  });

  describe('Data Provider Integration', () => {
    test('should handle custom API calls', async () => {
      const { dataProvider } = await import('../../providers/data');

      // Test custom method with health endpoint
      const result = await dataProvider.custom!({
        url: '/health',
        method: 'GET'
      });

      expect(result).toHaveProperty('data');
      expect(result.data).toHaveProperty('status');
      expect(result.data.status).toBe('healthy');
    }, TEST_TIMEOUT);

    test('should handle flows resource requests', async () => {
      const { dataProvider } = await import('../../providers/data');

      // Test flows resource (should return empty array since no flows deployed)
      const result = await dataProvider.getList({
        resource: 'flows',
        pagination: { current: 1, pageSize: 10 },
        sorters: [],
        filters: []
      });

      expect(result).toHaveProperty('data');
      expect(result).toHaveProperty('total');
      expect(Array.isArray(result.data)).toBe(true);
      expect(typeof result.total).toBe('number');
    }, TEST_TIMEOUT);
  });

  describe('Environment Configuration', () => {
    test('should have correct API URL configured', () => {
      expect(BACKEND_URL).toBeDefined();
      expect(BACKEND_URL).toMatch(/^https?:\/\//);

      // Should be the expected backend URL
      expect(BACKEND_URL).toBe('http://localhost:8000');
    });

    test('should have environment variables available', () => {
      expect(import.meta.env.VITE_API_URL).toBeDefined();
      expect(import.meta.env.VITE_API_URL).toBe('http://localhost:8000');
    });
  });

  describe('Error Handling', () => {
    test('should handle network errors gracefully', async () => {
      // Test with invalid URL to simulate network error
      const invalidAPI = {
        ...flowAPI,
        listBuckets: async () => {
          const response = await fetch('http://localhost:9999/api/flows/registry/buckets');
          if (!response.ok) throw new Error('Network error');
          return response.json();
        }
      };

      await expect(invalidAPI.listBuckets()).rejects.toThrow();
    }, TEST_TIMEOUT);

    test('should validate response data structure', async () => {
      const buckets = await flowAPI.listBuckets();

      // Validate each bucket has required fields
      buckets.forEach(bucket => {
        expect(bucket).toMatchObject({
          bucket_id: expect.any(String),
          bucket_name: expect.any(String),
          description: expect.any(String),
          permissions: expect.any(Object)
        });
      });
    }, TEST_TIMEOUT);
  });
});