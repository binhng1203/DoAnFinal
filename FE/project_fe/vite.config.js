// vite.config.js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // ==== AUTH SERVICE (port 8001) ====
      "/api/v1/auth": {
        target: "http://localhost:8001",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
      },

      // ==== PROJECT SERVICE (port 8002) ====
      "/api/v1/projects": {
        target: "http://localhost:8002",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
      },

      "/api/v1/suites": {
        target: "http://localhost:8002",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
      },

      "/api/v1/cases": {
        target: "http://localhost:8002",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
      },

      "/api/v1/steps": {
        target: "http://localhost:8002",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
      },

      // ==== TEST RUN SERVICE (port 8003) ====
      "/run_testcase": {
        target: "http://localhost:8003",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,   // giữ nguyên /run_testcase
      },

      "/api/v1/locators": {
        target: "http://localhost:8004",
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
      },

    },
  },
});
