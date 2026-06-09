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
    port: Number(process.env.VITE_STUDIO_PORT || 5107),
    proxy: {
      // Routes that live in Core backend (8106) — must be listed BEFORE the
      // catch-all "/api" rule so Vite matches them first.
      "/api/v1/conversations": {
        target: process.env.VITE_CORE_BACKEND_URL || "http://localhost:8106",
        changeOrigin: true,
      },
      "/api/v1/roles": {
        target: process.env.VITE_CORE_BACKEND_URL || "http://localhost:8106",
        changeOrigin: true,
      },
      "/api/v1/departments": {
        target: process.env.VITE_CORE_BACKEND_URL || "http://localhost:8106",
        changeOrigin: true,
      },
      // Everything else goes to Studio backend (8107)
      "/api": {
        target: process.env.VITE_STUDIO_BACKEND_URL || "http://localhost:8107",
        changeOrigin: true,
      },
    },
  },
});
