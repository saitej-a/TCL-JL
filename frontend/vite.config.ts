import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// D3 (CONTEXT): the dev SPA stays same-origin with the API — /api, /admin,
// /static and /media are proxied to the compose stack's nginx on :80, which
// forwards to web:8000. No CORS change anywhere in config/.
const NGINX_DEV_ORIGIN = "http://localhost:80";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": { target: NGINX_DEV_ORIGIN, changeOrigin: true },
      "/admin": { target: NGINX_DEV_ORIGIN, changeOrigin: true },
      "/static": { target: NGINX_DEV_ORIGIN, changeOrigin: true },
      "/media": { target: NGINX_DEV_ORIGIN, changeOrigin: true },
    },
  },
  build: {
    outDir: "dist",
  },
});
