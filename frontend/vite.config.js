import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(
  )],
  server: {
    host: true,
    hmr: true, 
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:5001",
        changeOrigin: true,
      },
    },
    // Set up your coding workspace host.
    // allowedHosts: [""],
    watch: {
      usePolling: true
    }
  }
})
