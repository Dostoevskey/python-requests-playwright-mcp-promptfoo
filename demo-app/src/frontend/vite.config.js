import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

const backendTarget = process.env.VITE_BACKEND_URL || 'http://localhost:3001'
const frontendPort = Number(process.env.FRONTEND_PORT || 3000)
console.log(`[vite] Proxying API requests to ${backendTarget}`)

export default defineConfig({
  plugins: [react()],
  server: {
    port: frontendPort,
    proxy: {
      '/api': {
        target: backendTarget
      }
    }
  }
})
