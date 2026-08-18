// vite.config.js
import { defineConfig } from "file:///home/AI/workspace/Mcp%20Server/DeepFusion/dashboard/node_modules/vite/dist/node/index.js";
import react from "file:///home/AI/workspace/Mcp%20Server/DeepFusion/dashboard/node_modules/@vitejs/plugin-react/dist/index.js";
var vite_config_default = defineConfig({
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
      interval: 1e3,
      ignored: ["**/node_modules/**", "**/.git/**"]
    },
    proxy: {
      "/api": {
        target: "http://localhost:5173",
        changeOrigin: true,
        timeout: 12e4,
        proxyTimeout: 12e4
      }
    }
  },
  test: {
    globals: true,
    environment: "happy-dom",
    setupFiles: ["./tests/setup.js"]
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcuanMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvaG9tZS9BSS93b3Jrc3BhY2UvTWNwIFNlcnZlci9EZWVwRnVzaW9uL2Rhc2hib2FyZFwiO2NvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9maWxlbmFtZSA9IFwiL2hvbWUvQUkvd29ya3NwYWNlL01jcCBTZXJ2ZXIvRGVlcEZ1c2lvbi9kYXNoYm9hcmQvdml0ZS5jb25maWcuanNcIjtjb25zdCBfX3ZpdGVfaW5qZWN0ZWRfb3JpZ2luYWxfaW1wb3J0X21ldGFfdXJsID0gXCJmaWxlOi8vL2hvbWUvQUkvd29ya3NwYWNlL01jcCUyMFNlcnZlci9EZWVwRnVzaW9uL2Rhc2hib2FyZC92aXRlLmNvbmZpZy5qc1wiOy8vLyA8cmVmZXJlbmNlIHR5cGVzPVwidml0ZXN0XCIgLz5cbmltcG9ydCB7ZGVmaW5lQ29uZmlnfSBmcm9tICd2aXRlJztcbmltcG9ydCByZWFjdCBmcm9tICdAdml0ZWpzL3BsdWdpbi1yZWFjdCc7XG5cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XG4gIHBsdWdpbnM6IFtyZWFjdCgpXSxcbiAgc2VydmVyOiB7XG4gICAgaG9zdDogdHJ1ZSxcbiAgICBwb3J0OiA4MDgwLFxuICAgIGFsbG93ZWRIb3N0czogdHJ1ZSxcbiAgICAvLyBcdTUxNzNcdTk1MkVcdUZGMUFcdTdDRkJcdTdFREYgaW5vdGlmeSBcdTRFMEFcdTk2NTBcdTUwNEZcdTRGNEUoNjU1MzYvXHU1QjlFXHU0RjhCMTI4KVx1NjVGNlx1RkYwQ3ZpdGUgXHU2NTg3XHU0RUY2XHU3NkQxXHU4OUM2XHU1NjY4XHU0RjFBXHU2MkE1XG4gICAgLy8gRU1GSUxFOiB0b28gbWFueSBvcGVuIGZpbGVzIFx1NUJGQ1x1ODFGNFx1NTI0RFx1N0FFRlx1OEZEQlx1N0EwQlx1NUQyOVx1NkU4M1x1MzAwMTgwODAgXHU4RDc3XHU0RTBEXHU2NzY1XHUzMDAyXHU2NTM5XHU3NTI4XHU4RjZFXHU4QkUyXG4gICAgLy8gXHU1RjdCXHU1RTk1XHU3RUQ1XHU1RjAwIGlub3RpZnlcdUZGMENcdTkwN0ZcdTUxNERcdTRGOURcdThENTYgc3lzY3RsIFx1NjNEMFx1Njc0M1x1RkYwOFx1NUY1M1x1NTI0RFx1NzNBRlx1NTg4M1x1NjVFMCByb290XHVGRjA5XHUzMDAyXG4gICAgd2F0Y2g6IHtcbiAgICAgIHVzZVBvbGxpbmc6IHRydWUsXG4gICAgICBpbnRlcnZhbDogMTAwMCxcbiAgICAgIGlnbm9yZWQ6IFsnKiovbm9kZV9tb2R1bGVzLyoqJywgJyoqLy5naXQvKionXSxcbiAgICB9LFxuICAgIHByb3h5OiB7XG4gICAgICAnL2FwaSc6IHtcbiAgICAgICAgdGFyZ2V0OiAnaHR0cDovL2xvY2FsaG9zdDo1MTczJyxcbiAgICAgICAgY2hhbmdlT3JpZ2luOiB0cnVlLFxuICAgICAgICB0aW1lb3V0OiAxMjAwMDAsXG4gICAgICAgIHByb3h5VGltZW91dDogMTIwMDAwLFxuICAgICAgfSxcbiAgICB9LFxuICB9LFxuICB0ZXN0OiB7XG4gICAgZ2xvYmFsczogdHJ1ZSxcbiAgICBlbnZpcm9ubWVudDogJ2hhcHB5LWRvbScsXG4gICAgc2V0dXBGaWxlczogWycuL3Rlc3RzL3NldHVwLmpzJ10sXG4gIH0sXG59KTtcbiJdLAogICJtYXBwaW5ncyI6ICI7QUFDQSxTQUFRLG9CQUFtQjtBQUMzQixPQUFPLFdBQVc7QUFFbEIsSUFBTyxzQkFBUSxhQUFhO0FBQUEsRUFDMUIsU0FBUyxDQUFDLE1BQU0sQ0FBQztBQUFBLEVBQ2pCLFFBQVE7QUFBQSxJQUNOLE1BQU07QUFBQSxJQUNOLE1BQU07QUFBQSxJQUNOLGNBQWM7QUFBQTtBQUFBO0FBQUE7QUFBQSxJQUlkLE9BQU87QUFBQSxNQUNMLFlBQVk7QUFBQSxNQUNaLFVBQVU7QUFBQSxNQUNWLFNBQVMsQ0FBQyxzQkFBc0IsWUFBWTtBQUFBLElBQzlDO0FBQUEsSUFDQSxPQUFPO0FBQUEsTUFDTCxRQUFRO0FBQUEsUUFDTixRQUFRO0FBQUEsUUFDUixjQUFjO0FBQUEsUUFDZCxTQUFTO0FBQUEsUUFDVCxjQUFjO0FBQUEsTUFDaEI7QUFBQSxJQUNGO0FBQUEsRUFDRjtBQUFBLEVBQ0EsTUFBTTtBQUFBLElBQ0osU0FBUztBQUFBLElBQ1QsYUFBYTtBQUFBLElBQ2IsWUFBWSxDQUFDLGtCQUFrQjtBQUFBLEVBQ2pDO0FBQ0YsQ0FBQzsiLAogICJuYW1lcyI6IFtdCn0K
