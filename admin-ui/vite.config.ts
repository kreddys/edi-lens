import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Necessary for Docker
    port: 3000,
    // --- THIS IS THE FIX ---
    // Add this watch option to enable polling.
    // This is often required when running Vite in a Docker container
    // to ensure the dev server correctly detects file changes from the host machine.
    watch: {
      usePolling: true,
    },
  }
})