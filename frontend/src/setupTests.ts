import '@testing-library/jest-dom'; // Import jest-dom matchers
import { vi } from 'vitest';

// Mock ResizeObserver if needed (common issue with some UI libraries/layouts)
const MockResizeObserver = vi.fn(() => ({
    observe: vi.fn(),
    unobserve: vi.fn(),
    disconnect: vi.fn(),
}));
vi.stubGlobal('ResizeObserver', MockResizeObserver);

// Mock window.matchMedia (often needed for responsive components)
Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation(query => ({
        matches: false,
        media: query,
        onchange: null,
        addListener: vi.fn(), // deprecated
        removeListener: vi.fn(), // deprecated
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
    })),
});

// Mock Performance API if used directly and causing issues in jsdom
Object.defineProperty(window, 'performance', {
    writable: true,
    value: {
        now: vi.fn(() => Date.now()), // Simple mock, adjust if specific timing needed
        mark: vi.fn(),
        measure: vi.fn(),
        // Add other methods if your code uses them
    }
});

// Mock Ace Editor minimally if it causes issues in tests that don't need it
// vi.mock('react-ace', () => ({
//   __esModule: true,
//   default: (props: any) => <textarea data-testid="mock-ace-editor" defaultValue={props.value} readOnly />,
// }));