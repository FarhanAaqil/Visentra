import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    // three.js ships as one ~530 kB module; it is lazy-loaded behind the UI.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('@xyflow/react')) return 'vendor-xyflow'
          if (id.includes('node_modules/three')) return 'vendor-three'
          if (id.includes('react') || id.includes('react-dom')) return 'vendor-react'
        },
      },
    },
  },
})
