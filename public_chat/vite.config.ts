import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { nodePolyfills } from "vite-plugin-node-polyfills";

const ROOT_ENV_DIR = path.resolve(__dirname, "..");

export default defineConfig({
  plugins: [
    react(),
    nodePolyfills({
      include: ["buffer"],
      globals: {
        Buffer: true,
      },
    }),
  ],
  root: __dirname,
  envDir: ROOT_ENV_DIR,
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 8002,
    strictPort: false,
  },
  preview: {
    host: "0.0.0.0",
    port: 8003,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-plotly": ["react-plotly.js", "plotly.js"],
          "vendor-markdown": ["react-markdown", "remark-gfm"],
        },
      },
    },
  },
});
