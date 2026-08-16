import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// Flask 后端运行在 5000；开发阶段把 /api 代理过去，生产由 Flask 托管 dist
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
      // 上传的图标/头像落在 Flask 的 /uploads 目录，开发模式下需一并代理过去，
      // 否则浏览器从 Vite(5173) 请求 /uploads/... 会 404，头像/图标显示为破图或回退图标
      '/uploads': {
        target: 'http://localhost:5001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    // false：部分环境下 Vite 清理 dist 会被安全删除包装拦截而构建失败；
    // 改为覆盖写入，旧的无用哈希产物可手动删除（不影响新产物引用）。
    emptyOutDir: false,
  },
})
