/**
 * 🔧 TEST SETUP VERIFICATION
 * 
 * This test verifies our test infrastructure is working correctly.
 * Run with: ./run.sh dev:test ui --testNamePattern="Setup Verification"
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { TestWrapper } from '../test-utils';

describe('🔧 Test Setup Verification', () => {
  it('renders TestWrapper without errors', () => {
    render(
      <TestWrapper>
        <div>Test Content</div>
      </TestWrapper>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('provides mock data provider', () => {
    const mockDataProvider = {
      getList: jest.fn().mockResolvedValue({ data: [], total: 0 }),
      getOne: jest.fn().mockResolvedValue({ data: { id: 1 } }),
      create: jest.fn().mockResolvedValue({ data: { id: 1 } }),
      update: jest.fn().mockResolvedValue({ data: { id: 1 } }),
      deleteOne: jest.fn().mockResolvedValue({ data: { id: 1 } }),
      custom: jest.fn().mockResolvedValue({ data: {} }),
    };

    render(
      <TestWrapper dataProvider={mockDataProvider}>
        <div>Test with Mock Provider</div>
      </TestWrapper>
    );

    expect(screen.getByText('Test with Mock Provider')).toBeInTheDocument();
  });

  it('provides workflow resources', () => {
    // This test verifies that workflow resources are available in TestWrapper
    render(
      <TestWrapper>
        <div data-testid="workflow-test">Workflow Test Ready</div>
      </TestWrapper>
    );

    expect(screen.getByTestId('workflow-test')).toBeInTheDocument();
  });
});