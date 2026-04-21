import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(() => {
  const backendHost = process.env.VITE_BACKEND_HOST || 'localhost'
  const backendPort = process.env.VITE_BACKEND_PORT || '8000'
  const backendHttp = `http://${backendHost}:${backendPort}`
  const backendWs = `ws://${backendHost}:${backendPort}`

  return {
    plugins: [react()],
    server: {
      port: 5174,
      proxy: {
        '/api': {
          target: backendHttp,
          changeOrigin: true,
        },
        '/ws': {
          target: backendWs,
          ws: true,
        },
      },
    },
  }
})
