import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8848', changeOrigin: true },
      '/articles': {
        target: 'http://127.0.0.1:8848',
        changeOrigin: true,
        bypass: req => req.headers.accept?.includes('text/html') ? '/index.html' : undefined
      },
      '/categories': { target: 'http://127.0.0.1:8848', changeOrigin: true },
      '/tags': { target: 'http://127.0.0.1:8848', changeOrigin: true },
      '/comments': { target: 'http://127.0.0.1:8848', changeOrigin: true },
      '/notifications': {
        target: 'http://127.0.0.1:8848',
        changeOrigin: true,
        bypass: req => req.headers.accept?.includes('text/html') ? '/index.html' : undefined
      },
      '/admin': { target: 'http://127.0.0.1:8848', changeOrigin: true },
    }
  }
})
