import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The built dist/ is committed and served by the FastAPI backend at /.
// Dev: `npm run dev` proxies /api and /ws to the backend on 8765.
export default defineConfig({
  plugins: [react()],
  base: "./",
  build: {
    outDir: "dist",
    sourcemap: false,
    emptyOutDir: true,
    target: "es2020",
    cssCodeSplit: false,
    rollupOptions: { output: { manualChunks: undefined } },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/health": "http://127.0.0.1:8765",
      "/ws": { target: "ws://127.0.0.1:8765", ws: true },
    },
  },
});
