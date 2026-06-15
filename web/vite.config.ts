import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");

  return {
    base: env.VITE_PAGES_BASE || "/",
    plugins: [react()],
    server: {
      port: 5173,
      host: "0.0.0.0",
      // 后端编排器（FastAPI）就绪后，SSE/REST 走代理；当前留作开发参考。
      proxy: {
        "/api": {
          target: "http://127.0.0.1:8000",
          changeOrigin: true,
        },
      },
    },
  };
});
