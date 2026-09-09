import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Use './' so assets resolve correctly from Electron's file:// protocol
  base: './',
  server: {
    port: 5173,
    strictPort: false,
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rolldownOptions: {
      output: {
        // Split the heavy vendor libraries out of the main bundle so the app
        // shell loads faster and the chunks stay under the warning threshold.
        advancedChunks: {
          groups: [
            { name: 'react-vendor', test: /node_modules[\\/](react|react-dom)[\\/]/ },
            { name: 'markdown-vendor', test: /node_modules[\\/](marked|highlight\.js)[\\/]/ },
          ],
        },
      },
    },
  },
})
