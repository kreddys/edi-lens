/// <reference types="vitest" /> // Add this triple-slash directive
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

console.log("--- Vite config: Top level ---");

export default defineConfig({
  plugins: [
    react(),
  ],
  // Vitest configuration
  test: {
    globals: true, // Use global APIs like describe, it, expect
    environment: 'jsdom', // Use jsdom for simulating browser APIs
    setupFiles: './src/setupTests.ts', // Optional setup file
    css: false, // Typically disable CSS processing for unit/component tests
    exclude: [ // <-- Add this exclude block
      '**/node_modules/**',
      '**/dist/**',
      '**/e2e/**', // Exclude E2E tests from Vitest run
      '**/.{idea,git,cache,output,temp}/**',
      '**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build}.config.*'
    ]
    // Optional: include source maps for better stack traces
    // sourcemap: 'inline',
  },
})