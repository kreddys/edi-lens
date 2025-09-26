import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  envDir: '../', // Load environment files from parent directory
  server: {
    host: '0.0.0.0', // Necessary for Docker
    port: 3000,
    watch: {
      usePolling: true,
    },
  }
})