import { app } from "electron";
import path from "node:path";

export const APP_PROTOCOL = "mentora";

export const DEV_SERVER_URL = process.env.MENTORA_DEV_SERVER_URL ?? null;

export const isDev = !app.isPackaged;

export const API_BASE_URL =
  process.env.MENTORA_API_BASE_URL ?? "http://127.0.0.1:8000/api";

/** 约束：桥接拒绝不在 allowlist 内的 path（§5.1） */
export const API_PATH_ALLOWLIST: readonly string[] = [
  "/health/",
  "/auth/",
  "/courses",
  "/sources",
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
