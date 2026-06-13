import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build to studio/web/dist (served by the stdlib backend in production).
// In dev, proxy /api to the backend on 127.0.0.1:3010.
export default defineConfig({
  plugins: [react()],
  build: { outDir: "dist", emptyOutDir: true },
  server: {
    port: 5174,
    proxy: { "/api": "http://127.0.0.1:3010" },
  },
});
