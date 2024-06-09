import { defineConfig } from 'vite'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
    base: '/static',
    build: {
      assetsDir: '.',
      outDir: 'build',
    },
    resolve: {
      alias: {
        '~': path.resolve('./src'),
      }
    }
})
