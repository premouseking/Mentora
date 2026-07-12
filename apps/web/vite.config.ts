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
    build: {
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("node_modules/pdfjs-dist")) return "vendor-pdfjs";
            if (id.includes("node_modules/katex") || id.includes("node_modules/react-markdown")) {
              return "vendor-markdown";
            }
            if (id.includes("node_modules/@tanstack/react-query")) return "vendor-query";
            if (id.includes("node_modules/react-router")) return "vendor-router";
            if (id.includes("node_modules/react-dom") || id.includes("node_modules/react/")) {
              return "vendor-react";
            }
          },
        },
      },
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      strictPort: true,
      // 云服务器经 nginx 以公网 IP 访问时需放行 Host 校验
      allowedHosts: true,
      proxy: apiProxyTarget
        ? {
            "/api": {
              target: apiProxyTarget,
              changeOrigin: true,
              // 学习方案生成等 LLM 结构化输出可能超过 2 分钟
              timeout: 300_000,
              proxyTimeout: 300_000,
              configure(proxy) {
                proxy.on("proxyReq", (proxyReq) => {
                  // Docker 内 target 为 http://api:8000 时 changeOrigin 会把 Host 设为 api:8000，触发 Django DisallowedHost
                  proxyReq.setHeader("host", "127.0.0.1:8000");
                });
                proxy.on("error", (_err, _req, res) => {
                  if (res.headersSent) return;
                  res.writeHead(503, { "Content-Type": "application/json" });
                  res.end(
                    JSON.stringify({
                      error: "后端 API 未启动，请在项目根目录运行 pnpm dev:api",
                    }),
                  );
                });
              },
            },
          }
        : undefined,
    },
  };
});
