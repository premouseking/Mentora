import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiProxyTarget = env.VITE_API_PROXY_TARGET ?? env.VITE_API_ORIGIN;

  return {
    base: "./",
    plugins: [react()],
    server: {
      port: 5173,
      strictPort: true,
      proxy: apiProxyTarget
        ? {
            "/api": apiProxyTarget,
          }
        : undefined,
    },
  };
});
