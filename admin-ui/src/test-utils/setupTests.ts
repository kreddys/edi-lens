import '@testing-library/jest-dom';
import { configure } from '@testing-library/react';

// Mock import.meta.env for Jest
Object.defineProperty(globalThis, 'import', {
  value: {
    meta: {
      env: {
        VITE_KEYCLOAK_URL: 'http://localhost:8080',
        VITE_KEYCLOAK_REALM: 'test-realm',
        VITE_KEYCLOAK_CLIENT_ID: 'test-client',
        VITE_API_URL: 'http://localhost:8000'
      }
    }
  }
});

// Also mock import.meta.env directly
Object.defineProperty(globalThis, 'import.meta', {
  value: {
    env: {
      VITE_KEYCLOAK_URL: 'http://localhost:8080',
      VITE_KEYCLOAK_REALM: 'test-realm',
      VITE_KEYCLOAK_CLIENT_ID: 'test-client',
      VITE_API_URL: 'http://localhost:8000'
    }
  }
});

// Mock Keycloak module
jest.mock('../utils/keycloak', () => ({
  __esModule: true,
  default: {
    init: jest.fn(() => Promise.resolve(true)),
    login: jest.fn(),
    logout: jest.fn(),
    authenticated: true,
    token: 'mock-token',
    tokenParsed: {
      sub: 'test-user',
      preferred_username: 'test-user',
      email: 'test@example.com'
    }
  }
}));

// Mock axios globally for all tests
jest.mock('axios', () => ({
  create: jest.fn(() => ({
    post: jest.fn(),
    get: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
    interceptors: {
      request: { use: jest.fn() },
      response: { use: jest.fn() }
    }
  })),
  post: jest.fn(),
  get: jest.fn(),
  put: jest.fn(),
  delete: jest.fn(),
  interceptors: {
    request: { use: jest.fn() },
    response: { use: jest.fn() }
  }
}));

// Configure testing library
configure({ testIdAttribute: 'data-testid' });

// Mock window.matchMedia for Ant Design responsive components
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: query === '(min-width: 768px)' ? true : false,
    media: query,
    onchange: null,
    addListener: jest.fn(), // deprecated
    removeListener: jest.fn(), // deprecated
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock ResizeObserver for Ant Design components that need it
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Mock Ant Design ResponsiveObserver - use factory function to avoid scope issues
jest.mock('antd/lib/_util/responsiveObserver', () => ({
  __esModule: true,
  default: jest.fn(() => ({
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
    responsiveMap: {
      xs: '(max-width: 575px)',
      sm: '(min-width: 576px)',
      md: '(min-width: 768px)',
      lg: '(min-width: 992px)',
      xl: '(min-width: 1200px)',
      xxl: '(min-width: 1600px)',
    },
  })),
}));

// Also mock the antd Steps useBreakpoint hook that depends on ResponsiveObserver
jest.mock('antd/lib/grid/hooks/useBreakpoint', () => ({
  __esModule: true,
  default: () => ({
    xs: false,
    sm: false,
    md: true,
    lg: true,
    xl: true,
    xxl: true,
  }),
}));

// Mock console methods to reduce noise in tests
const originalError = console.error;
const originalWarn = console.warn;

beforeAll(() => {
  console.error = (...args) => {
    if (
      typeof args[0] === 'string' &&
      (args[0].includes('Warning: ReactDOM.render') ||
       args[0].includes('Warning: React.createFactory') ||
       args[0].includes('Warning: componentWillReceiveProps'))
    ) {
      return;
    }
    originalError.call(console, ...args);
  };

  console.warn = (...args) => {
    if (
      typeof args[0] === 'string' &&
      (args[0].includes('Warning: ReactDOM.render') ||
       args[0].includes('Warning: React.createFactory'))
    ) {
      return;
    }
    originalWarn.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
  console.warn = originalWarn;
});