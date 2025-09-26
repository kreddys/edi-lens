/**
 * Test setup file for integration tests
 */

// Make sure environment variables are loaded
console.log('Test environment setup:');
console.log('VITE_API_URL:', import.meta.env.VITE_API_URL);

// Global test configuration
global.fetch = global.fetch || fetch;