import type { DeepLink } from "../shared/desktopApi";
import { APP_PROTOCOL } from "./config";

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

/** Windows 第二实例通过 argv 投递 Deep Link，而非 macOS 的 open-url */
export function findDeepLinkInArgv(argv: string[]): DeepLink | null {
  for (const arg of argv) {
    const link = parseDeepLink(arg);
    if (link) return link;
  }
  return null;
}
