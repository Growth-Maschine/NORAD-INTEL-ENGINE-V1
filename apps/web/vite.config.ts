import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5000,
    // If 5000 is taken (common on macOS — AirPlay), try 5001, 5002, …
    strictPort: false,
    allowedHosts: true,
    proxy: {
      // Backend routers already include `/api` in their prefix (e.g.
      // `/api/discovery/*`, `/api/events/*`). Pass through unchanged.
      // Health routes live at root (`/health`) — frontend code that needs
      // them prefixes manually.
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
