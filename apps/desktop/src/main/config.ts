import { app } from "electron";
import path from "node:path";

/** Custom protocol scheme for deep links (mentora://...). */
export const APP_PROTOCOL = "mentora";

/** Dev server URL injected by the dev script; absent in packaged builds. */
export const DEV_SERVER_URL = process.env.MENTORA_DEV_SERVER_URL ?? null;

export const isDev = !app.isPackaged;

/** Cloud Django API base URL. Overridable for staging/local backends. */
export const API_BASE_URL =
  process.env.MENTORA_API_BASE_URL ?? "http://127.0.0.1:8000/api";

/**
 * Allowlisted API path prefixes. The bridge rejects any request whose path does
 * not match one of these (desktop-client-architecture §5.1). Tighten this as
 * concrete endpoints land.
 */
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

/** Max JSON body accepted from the renderer over the API bridge (1 MiB). */
export const MAX_API_BODY_BYTES = 1024 * 1024;

/** Resolve the preload script path for both dev and packaged runtimes. */
export function resolvePreloadPath(): string {
  return path.join(__dirname, "..", "preload", "index.cjs");
}

/**
 * Resolve the renderer entry. In dev we load the Vite server; in production we
 * load the renderer build copied into resources/renderer by electron-builder.
 */
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

/** Origins the renderer is allowed to navigate to. */
export function allowedNavigationOrigins(): string[] {
  if (isDev && DEV_SERVER_URL) {
    return [new URL(DEV_SERVER_URL).origin];
  }
  return [];
}
