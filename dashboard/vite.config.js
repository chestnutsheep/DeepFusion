/// <reference types="vitest" />
import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 8080,
    allowedHosts: true,
    // 关键：系统 inotify 上限偏低(65536/实例128)时，vite 文件监视器会报
    // EMFILE: too many open files 导致前端进程崩溃、8080 起不来。改用轮询
    // 彻底绕开 inotify，避免依赖 sysctl 提权（当前环境无 root）。
    watch: {
      usePolling: true,
      interval: 1000,
      ignored: ['**/node_modules/**', '**/.git/**'],
    },
    proxy: {
      '/api': {
        target: 'http://localhost:5173',
        changeOrigin: true,
        timeout: 120000,
        proxyTimeout: 120000,
      },
    },
  },
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./tests/setup.js'],
  },
});
