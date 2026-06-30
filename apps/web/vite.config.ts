import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, repoRoot, "");
  const apiProxyTarget = env.VITE_API_PROXY_TARGET ?? env.VITE_API_ORIGIN;

  return {
    base: "./",
    envDir: repoRoot,
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
