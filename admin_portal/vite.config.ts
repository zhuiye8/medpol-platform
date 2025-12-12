import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const ROOT_ENV_DIR = path.resolve(__dirname, "..");

// 使用父级 .env，确保后端/前端共享一份配置
export default defineConfig({
  plugins: [react()],
  root: __dirname,
  envDir: ROOT_ENV_DIR,
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 4173,
    strictPort: false,
  },
  preview: {
    host: "0.0.0.0",
    port: 4174,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          // React 核心（稳定，长期缓存）
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          // Plotly 图表库（大体积，按需加载）
          "vendor-plotly": ["react-plotly.js", "plotly.js"],
          // Markdown 渲染
          "vendor-markdown": ["react-markdown", "remark-gfm"],
        },
      },
    },
  },
});
