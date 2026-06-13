import type { DeepLink } from "../shared/desktopApi";
import { APP_PROTOCOL } from "./config";

/**
 * Parses a `mentora://<domain>/<path...>?<params>` URL into a structured
 * DeepLink. Returns null for anything that is not our protocol so callers can
 * safely ignore unrelated argv entries.
 */
export function parseDeepLink(raw: string): DeepLink | null {
  if (!raw.startsWith(`${APP_PROTOCOL}://`)) return null;
  try {
    const url = new URL(raw);
    const params: Record<string, string> = {};
    for (const [key, value] of url.searchParams) params[key] = value;
    return {
      domain: url.hostname,
      path: url.pathname.replace(/^\/+/, ""),
      params,
    };
  } catch {
    return null;
  }
}

/** Finds the first deep link in a process argv array (Windows second-instance). */
export function findDeepLinkInArgv(argv: string[]): DeepLink | null {
  for (const arg of argv) {
    const link = parseDeepLink(arg);
    if (link) return link;
  }
  return null;
}
