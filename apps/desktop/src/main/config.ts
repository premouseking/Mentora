import { app } from "electron";
import fs from "node:fs";
import path from "node:path";

function loadRootEnv(): void {
  const candidates = [
    path.resolve(process.cwd(), "..", "..", ".env"),
    path.resolve(__dirname, "..", "..", "..", "..", ".env"),
  ];
  const envPath = candidates.find((candidate) => fs.existsSync(candidate));
  if (!envPath) return;

  for (const line of fs.readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const separatorIndex = trimmed.indexOf("=");
    if (separatorIndex <= 0) continue;

    const name = trimmed.slice(0, separatorIndex).trim();
    const rawValue = trimmed.slice(separatorIndex + 1).trim();
    const value = rawValue.replace(/^(['"])(.*)\1$/, "$2");
    if (process.env[name] === undefined) {
      process.env[name] = value;
    }
  }
}

loadRootEnv();

export const DEV_SERVER_URL = process.env.MENTORA_DEV_SERVER_URL ?? null;
export const OBJECT_STORAGE_ORIGIN = process.env.MENTORA_OBJECT_STORAGE_ORIGIN ?? null;

export const isDev = !app.isPackaged;

/** 开发态默认跳过认证门禁；设 MENTORA_DEV_AUTH_BYPASS=0 可验证完整登录流程 */
export function isDevAuthBypassEnabled(): boolean {
  return isDev && process.env.MENTORA_DEV_AUTH_BYPASS !== "0";
}

export const DEV_AUTH_BYPASS_ACCOUNT_ID = "dev-bypass";

function requiredEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`${name} is required`);
  }
  return value;
}

export const API_BASE_URL = requiredEnv("MENTORA_API_BASE_URL");

/** 约束：桥接拒绝不在 allowlist 内的 path（§5.1） */
export const API_PATH_ALLOWLIST: readonly string[] = [
  "/health/",
  "/auth/",
  "/courses",
  "/sources",
  "/library",
  "/uploads",
  "/events",
  "/assessments",
  "/plans",
];

export function isAllowedApiPath(pathname: string): boolean {
  return API_PATH_ALLOWLIST.some((prefix) => pathname.startsWith(prefix));
}

/** 约束：renderer 经 API 桥接提交的 JSON body 上限（§5.1） */
export const MAX_API_BODY_BYTES = 1024 * 1024;

export function resolvePreloadPath(): string {
  return path.join(__dirname, "..", "preload", "index.cjs");
}

export function resolveWindowIconPath(): string | undefined {
  if (!isDev) return undefined;
  // 与 preload 一致：bundle 在 dist/main，build 资源在项目根 build/
  const fileName = process.platform === "win32" ? "icon.ico" : "icon-dev.png";
  return path.resolve(__dirname, "..", "..", "build", fileName);
}

export function resolveRendererTarget():
  | { kind: "url"; url: string }
  | { kind: "file"; file: string } {
  if (isDev && DEV_SERVER_URL) {
    return { kind: "url", url: DEV_SERVER_URL };
  }
  return {
    kind: "file",
    file: path.join(process.resourcesPath, "renderer", "index.html"),
  };
}

export function allowedNavigationOrigins(): string[] {
  if (isDev && DEV_SERVER_URL) {
    return [new URL(DEV_SERVER_URL).origin];
  }
  return [];
}

export function allowedConnectSources(): string[] {
  const sources = [API_BASE_URL];
  if (isDev && DEV_SERVER_URL) {
    sources.push(new URL(DEV_SERVER_URL).origin, DEV_SERVER_URL.replace(/^http/, "ws"));
  }
  if (OBJECT_STORAGE_ORIGIN) {
    sources.push(OBJECT_STORAGE_ORIGIN);
  }
  return Array.from(new Set(sources.map((source) => new URL(source).origin)));
}
