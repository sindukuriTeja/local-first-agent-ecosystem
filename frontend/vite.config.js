import { resolve } from 'path'
import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/ask': 'http://127.0.0.1:8000',
      '/agents': 'http://127.0.0.1:8000',
      '/models': 'http://127.0.0.1:8000',
      '/approvals': 'http://127.0.0.1:8000',
      '/audit': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        roles: resolve(__dirname, 'roles.html'),
        login: resolve(__dirname, 'login.html'),
        workspace: resolve(__dirname, 'workspace.html'),
        signup: resolve(__dirname, 'signup.html'),
        forgot: resolve(__dirname, 'forgot-password.html'),
        notfound: resolve(__dirname, '404.html'),
        error500: resolve(__dirname, '500.html'),
      },
    },
  },
})
