import React from 'react';
import { ConfigProvider } from 'antd';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Refine } from '@refinedev/core';
import routerProvider from '@refinedev/react-router-v6';

// Mock data provider for tests - simple implementation
const mockDataProvider = {
  create: jest.fn(() => Promise.resolve({ data: { id: 1 } })),
  update: jest.fn(() => Promise.resolve({ data: { id: 1 } })),
  getList: jest.fn(() => Promise.resolve({ data: [], total: 0 })),
  getOne: jest.fn(() => Promise.resolve({ data: { id: 1 } })),
  deleteOne: jest.fn(() => Promise.resolve({ data: { id: 1 } })),
  custom: jest.fn(() => Promise.resolve({ data: {} })),
  getApiUrl: () => 'http://localhost:3001'
};

// Mock auth provider
const mockAuthProvider = {
  login: jest.fn(() => Promise.resolve({ success: true })),
  logout: jest.fn(() => Promise.resolve({ success: true })),
  check: jest.fn(() => Promise.resolve({ authenticated: true })),
  getPermissions: jest.fn(() => Promise.resolve(['admin'])),
  getIdentity: jest.fn(() => Promise.resolve({ 
    id: 'test-user', 
    name: 'Test User',
    email: 'test@example.com' 
  })),
  onError: jest.fn(() => Promise.resolve()),
};

export interface TestWrapperProps {
  children: React.ReactNode;
  queryClient?: QueryClient;
  dataProvider?: any;
  authProvider?: any;
  navigation?: any;
}

export const TestWrapper: React.FC<TestWrapperProps> = ({ 
  children, 
  dataProvider = mockDataProvider,
  authProvider = mockAuthProvider,
  queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false }
    }
  })
}) => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ConfigProvider>
          <Refine
            dataProvider={dataProvider}
            authProvider={authProvider}
            routerProvider={routerProvider}
            resources={[
              { name: 'trading-partners', list: '/trading-partners' },
              { name: 'schemas', list: '/schemas' },
              { name: 'validation', list: '/validation' },
              { name: 'history', list: '/history' },
              { name: 'workflow-templates', list: '/workflow-templates' },
              { name: 'workflows', list: '/workflows' }
            ]}
            options={{ disableTelemetry: true }}
          >
            {children}
          </Refine>
        </ConfigProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export { mockDataProvider, mockAuthProvider };