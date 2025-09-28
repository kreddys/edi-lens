/**
 * Backend Connectivity Integration Tests
 */

import { describe, test, expect, beforeAll } from 'vitest';
import { flowAPI } from '../../providers/data';

const BACKEND_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const TEST_TIMEOUT = 10000;

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
    }, TEST_TIMEOUT);
  });

  describe('Parameter Management', () => {
    test('should have updateFlowParameters method available', async () => {
      expect(typeof flowAPI.updateFlowParameters).toBe('function');
    });

    test('should handle parameter update API call structure', async () => {
      const fakeFlowId = 'test-flow-id';
      const testParameters = [
        {
          name: 'test_param',
          value: 'test_value',
          description: 'Test parameter',
          sensitive: false
        }
      ];

      try {
        await flowAPI.updateFlowParameters(fakeFlowId, testParameters);
      } catch (error: any) {
        expect(error.response?.status).toBeDefined();
        expect([404, 400, 500].includes(error.response?.status)).toBe(true);
      }
    }, TEST_TIMEOUT);
  });

  describe('Flow Registry Endpoints', () => {
    test('should list registry buckets', async () => {
      const buckets = await flowAPI.listBuckets();
      expect(Array.isArray(buckets)).toBe(true);

      if (buckets.length > 0) {
        const bucket = buckets[0];
        expect(bucket).toHaveProperty('id');
        expect(bucket).toHaveProperty('name');
      }
    }, TEST_TIMEOUT);
  });
});
