import { BrowserWindow, session, shell } from "electron";

import {
  allowedNavigationOrigins,
  isDev,
  resolvePreloadPath,
  resolveRendererTarget,
} from "./config";
import { createLogger } from "./logger";

const log = createLogger("window");

/**
 * Content-Security-Policy applied to the renderer. No `unsafe-eval`; dev adds
 * the Vite websocket/origin so HMR works (desktop-client-architecture §4).
 */
function contentSecurityPolicy(): string {
  const devConnect = isDev ? " http://localhost:5173 ws://localhost:5173" : "";
  const devScript = isDev ? " 'unsafe-inline'" : "";
  return [
    "default-src 'self'",
    `script-src 'self'${devScript}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self'${devConnect}`,
    "object-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'none'",
  ].join("; ");
}

function applySecurityHeaders(): void {
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        "Content-Security-Policy": [contentSecurityPolicy()],
        "X-Content-Type-Options": ["nosniff"],
      },
    });
  });
}

/** Blocks navigation to anything but the dev server / packaged renderer and
 *  routes user-approved external links to the system browser. */
function hardenNavigation(window: BrowserWindow): void {
  const allowedOrigins = allowedNavigationOrigins();

  window.webContents.on("will-navigate", (event, url) => {
    const target = new URL(url);
    const isFile = target.protocol === "file:";
    const isAllowedOrigin = allowedOrigins.includes(target.origin);
    if (!isFile && !isAllowedOrigin) {
      event.preventDefault();
      log.warn("Blocked navigation", { url });
    }
  });

  window.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//i.test(url)) {
      void shell.openExternal(url);
    }
    return { action: "deny" };
  });

  window.webContents.on("will-attach-webview", (event) => event.preventDefault());
}

export function createMainWindow(): BrowserWindow {
  applySecurityHeaders();

  const window = new BrowserWindow({
    width: 1280,
    height: 832,
    minWidth: 960,
    minHeight: 640,
    show: false,
    backgroundColor: "#0f1115",
    title: "Mentora",
    webPreferences: {
      preload: resolvePreloadPath(),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      webSecurity: true,
      spellcheck: false,
    },
  });

  hardenNavigation(window);

  window.once("ready-to-show", () => window.show());

  const target = resolveRendererTarget();
  if (target.kind === "url") {
    void window.loadURL(target.url);
    if (isDev) window.webContents.openDevTools({ mode: "detach" });
  } else {
    void window.loadFile(target.file);
  }

  return window;
}
