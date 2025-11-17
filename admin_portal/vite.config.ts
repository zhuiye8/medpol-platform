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
  },
});
