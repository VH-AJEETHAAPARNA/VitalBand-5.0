import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      // Proxy API requests to the FastAPI backend
      "/api": {
        target: "http://localhost:5000",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://localhost:5000",
        ws: true,
        changeOrigin: true,
      },
      // The MJPEG stream and its status probe live outside /api.
      "/video_feed": {
        target: "http://localhost:5000",
        changeOrigin: true,
      },
      "/video_status": {
        target: "http://localhost:5000",
        changeOrigin: true,
      },
    },
  },
});
