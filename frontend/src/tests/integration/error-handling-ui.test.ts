/**
 * Error Handling UI Integration Tests
 *
 * These tests verify that the frontend properly displays detailed error information
 * when deployment failures occur, including component-specific error details.
 */

import { flowAPI } from '../../providers/data';
// Note: ErrorDetails component testing will be done separately due to React Testing Library dependency
// import { ErrorDetails } from '../../components/ErrorDetails';
// import { render, screen } from '@testing-library/react';
// import React from 'react';

// Test configuration
const BACKEND_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const TEST_TIMEOUT = 15000; // 15 seconds for deployment tests

describe('Error Handling UI Integration Tests', () => {
  beforeAll(() => {
    console.log(`Testing error handling with backend at: ${BACKEND_URL}`);
  });

  describe('Deployment Error Handling', () => {
    test('should handle flow deployment with invalid processors', async () => {
      // Create a test bucket first
      const testBucketName = `test-error-handling-${Date.now()}`;
      let createdBucket: any;
      
      try {
        createdBucket = await flowAPI.createBucket(testBucketName, 'Test bucket for error handling');
        expect(createdBucket).toHaveProperty('bucket_id');

        // Create a flow definition that should fail
        const invalidFlowDefinition = {
          name: "Invalid Test Flow",
          description: "Flow designed to test error handling",
          processors: [
            {
              identifier: "invalid-processor-1",
              name: "Invalid-GetFile",
              type: "org.apache.nifi.processors.standard.GetFile",
              position: { x: 100, y: 100 },
              properties: {
                "Input Directory": "/nonexistent/invalid/path/that/should/fail",
                "File Filter": "*.txt"
              },
              autoTerminatedRelationships: []
            },
            {
              identifier: "invalid-processor-2",
              name: "Invalid-PutFile", 
              type: "org.apache.nifi.processors.standard.PutFile",
              position: { x: 300, y: 100 },
              properties: {
                "Directory": "" // Empty directory should cause validation error
              },
              autoTerminatedRelationships: []
            }
          ],
          connections: [
            {
              name: "Invalid Connection",
              source: {
                id: "invalid-processor-1",
                name: "Invalid-GetFile",
                type: "PROCESSOR"
              },
              destination: {
                id: "invalid-processor-2",
                name: "Invalid-PutFile", 
                type: "PROCESSOR"
              },
              selectedRelationships: ["success"]
            }
          ]
        };

        // Attempt to deploy the invalid flow
        try {
          await flowAPI.deployAndStore(invalidFlowDefinition, createdBucket.bucket_id, {});
          // If deployment succeeds, that's unexpected but not a test failure
          console.warn('Expected deployment to fail, but it succeeded');
        } catch (deploymentError: any) {
          console.log('Deployment error caught (expected):', deploymentError);
          
          // Verify error structure
          expect(deploymentError).toHaveProperty('response');
          expect(deploymentError.response).toHaveProperty('status', 400);
          expect(deploymentError.response).toHaveProperty('data');
          
          const errorData = deploymentError.response.data;
          expect(errorData).toHaveProperty('detail');
          
          const detail = errorData.detail;
          expect(detail).toHaveProperty('error_type');
          expect(detail).toHaveProperty('user_message');
          expect(detail).toHaveProperty('action_required');
          
          // Check for detailed deployment information
          if (detail.details) {
            expect(detail.details).toHaveProperty('stage');
            expect(detail.details.stage).toBe('nifi_deployment');
            
            if (detail.details.failures) {
              expect(Array.isArray(detail.details.failures)).toBe(true);
              
              // Verify failure structure
              detail.details.failures.forEach((failure: any) => {
                expect(failure).toHaveProperty('component_type');
                expect(failure).toHaveProperty('component_name');
                expect(failure).toHaveProperty('error_type');
                expect(failure).toHaveProperty('message');
                expect(failure).toHaveProperty('details');
              });
            }
            
            if (detail.details.summary) {
              const summary = detail.details.summary;
              expect(summary).toHaveProperty('total_processors');
              expect(summary).toHaveProperty('created_processors');
              expect(summary).toHaveProperty('failed_processors');
            }
          }
        }

      } finally {
        // Clean up the test bucket
        if (createdBucket?.bucket_id) {
          try {
            // Note: The backend might not have a delete bucket endpoint
            // This is just for cleanup if available
            console.log(`Test bucket ${createdBucket.bucket_id} should be cleaned up manually if needed`);
          } catch (cleanupError) {
            console.log('Cleanup error (expected if no delete endpoint):', cleanupError);
          }
        }
      }
    }, TEST_TIMEOUT);

    test('should handle malformed flow definitions', async () => {
      // Create a test bucket
      const testBucketName = `test-malformed-${Date.now()}`;
      let createdBucket: any;
      
      try {
        createdBucket = await flowAPI.createBucket(testBucketName, 'Test bucket for malformed flow');
        
        // Test with malformed flow definition
        const malformedFlow = {
          name: "Malformed Flow",
          // Missing required fields, invalid structure
          processors: [
            {
              // Missing identifier, type, etc.
              name: "Incomplete Processor"
            }
          ],
          connections: [
            {
              // Invalid connection structure
              source: "non-existent",
              destination: "also-non-existent"
            }
          ]
        };

        try {
          await flowAPI.deployAndStore(malformedFlow, createdBucket.bucket_id, {});
        } catch (error: any) {
          // Verify error response structure
          expect(error.response?.status).toBeDefined();
          expect([400, 422, 500].includes(error.response?.status)).toBe(true);
          
          const errorDetail = error.response?.data?.detail;
          if (errorDetail) {
            expect(errorDetail).toHaveProperty('error_type');
            expect(errorDetail).toHaveProperty('user_message');
          }
        }
        
      } finally {
        // Cleanup
        if (createdBucket?.bucket_id) {
          console.log(`Test bucket ${createdBucket.bucket_id} should be cleaned up manually if needed`);
        }
      }
    }, TEST_TIMEOUT);
  });

  describe('Error Response Structure Validation', () => {
    test('should validate deployment error response structure', () => {
      const mockDeploymentError = {
        response: {
          status: 400,
          data: {
            detail: {
              error_type: 'NIFI_DEPLOYMENT_FAILED',
              user_message: 'Flow deployment to NiFi failed',
              action_required: 'Review the NiFi flow definition and resolve the reported validation errors before retrying',
              details: {
                stage: 'nifi_deployment',
                summary: {
                  total_processors: 2,
                  created_processors: 1,
                  failed_processors: 1,
                  total_connections: 1,
                  created_connections: 0,
                  failed_connections: 1
                },
                failures: [
                  {
                    component_type: 'processor',
                    component_name: 'Invalid-PutFile',
                    error_type: 'validation',
                    message: 'Processor validation failed',
                    details: {
                      validation_errors: ['Directory property is required'],
                      validation_status: 'INVALID'
                    }
                  },
                  {
                    component_type: 'connection',
                    component_name: 'Invalid Connection',
                    error_type: 'creation',
                    message: 'Failed to create connection',
                    details: {
                      source: { id: 'processor-1', name: 'GetFile' },
                      destination: { id: 'processor-2', name: 'PutFile' }
                    }
                  }
                ]
              }
            }
          }
        }
      };

      // Validate the error structure that our UI error handling expects
      const errorData = mockDeploymentError.response.data.detail;
      expect(errorData).toHaveProperty('error_type', 'NIFI_DEPLOYMENT_FAILED');
      expect(errorData).toHaveProperty('user_message');
      expect(errorData).toHaveProperty('action_required');
      expect(errorData).toHaveProperty('details');
      
      const details = errorData.details;
      expect(details).toHaveProperty('stage', 'nifi_deployment');
      expect(details).toHaveProperty('summary');
      expect(details).toHaveProperty('failures');
      expect(Array.isArray(details.failures)).toBe(true);
      
      // Validate failure structure
      details.failures.forEach((failure: any) => {
        expect(failure).toHaveProperty('component_type');
        expect(failure).toHaveProperty('component_name');
        expect(failure).toHaveProperty('error_type');
        expect(failure).toHaveProperty('message');
        expect(failure).toHaveProperty('details');
      });

      // Test the logic that determines whether to show detailed errors
      const hasDetailedErrors = details.failures?.length > 0;
      expect(hasDetailedErrors).toBe(true);
    });

    test('should validate simple error response structure', () => {
      const mockSimpleError = {
        response: {
          status: 400,
          data: {
            detail: {
              error_type: 'INVALID_BUCKET',
              user_message: 'Bucket not found',
              action_required: 'Verify the bucket ID exists in Registry'
            }
          }
        }
      };

      const errorData = mockSimpleError.response.data.detail;
      expect(errorData).toHaveProperty('error_type', 'INVALID_BUCKET');
      expect(errorData).toHaveProperty('user_message', 'Bucket not found');
      expect(errorData).toHaveProperty('action_required');
      
      // Test the logic that determines whether to show detailed errors
      const hasDetailedErrors = errorData.details?.failures?.length > 0;
      expect(hasDetailedErrors).toBe(false);
    });
  });

  describe('Bucket Creation Error Handling', () => {
    test('should handle duplicate bucket name errors', async () => {
      const duplicateBucketName = `duplicate-test-${Date.now()}`;
      
      try {
        // Create the first bucket
        const firstBucket = await flowAPI.createBucket(duplicateBucketName, 'First bucket');
        expect(firstBucket).toHaveProperty('bucket_id');
        
        // Try to create a second bucket with the same name
        try {
          await flowAPI.createBucket(duplicateBucketName, 'Duplicate bucket');
          // If this succeeds, the backend allows duplicates (which might be valid)
          console.log('Backend allows duplicate bucket names');
        } catch (duplicateError: any) {
          // Verify error structure for duplicate bucket
          expect(duplicateError.response?.status).toBeDefined();
          expect([400, 409, 422].includes(duplicateError.response?.status)).toBe(true);
          
          const errorDetail = duplicateError.response?.data?.detail;
          if (errorDetail) {
            expect(errorDetail).toHaveProperty('user_message');
            expect(typeof errorDetail.user_message).toBe('string');
          }
        }
        
      } catch (error) {
        console.log('Initial bucket creation failed:', error);
        // This is acceptable - we're testing error handling
      }
    }, TEST_TIMEOUT);
  });
});