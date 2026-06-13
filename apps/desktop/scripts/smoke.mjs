import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

import electronPath from "electron";
import { _electron as electron } from "playwright";

import { terminateProcessTree } from "./process-tree.mjs";
import { pnpmInvocation } from "./smoke-runtime.mjs";

const desktopDir = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const webDir = path.resolve(desktopDir, "..", "web");
const rendererUrl = "http://localhost:5173";
const startupTimeoutMs = 30_000;
const viteLogs = [];

function capture(stream) {
  stream?.on("data", (chunk) => {
    const text = chunk.toString();
    viteLogs.push(text);
    process.stdout.write(text);
  });
}

async function waitForRenderer() {
  const deadline = Date.now() + startupTimeoutMs;
  let lastError;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(rendererUrl);
      if (response.ok) return;
      lastError = new Error(`HTTP ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  throw new Error(
    `Vite did not become ready at ${rendererUrl}: ${String(lastError)}\n${viteLogs.join("")}`,
  );
}

async function waitForRendererWindow(app) {
  const deadline = Date.now() + startupTimeoutMs;

  while (Date.now() < deadline) {
    const page = app
      .windows()
      .find((candidate) => {
        const url = candidate.url();
        return (
          url.startsWith(rendererUrl) ||
          /\/apps\/web\/dist\/index\.html$/i.test(url)
        );
      });
    if (page) return page;
    await new Promise((resolve) => setTimeout(resolve, 100));
  }

  const urls = app.windows().map((candidate) => candidate.url());
  throw new Error(`Renderer window did not appear. Open windows: ${urls.join(", ")}`);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function pass(message) {
  process.stdout.write(`[PASS] ${message}\n`);
}

const viteCommand = pnpmInvocation(["dev", "--host", "localhost"]);
const vite = spawn(viteCommand.command, viteCommand.args, {
  cwd: webDir,
  env: process.env,
  detached: process.platform !== "win32",
  stdio: ["ignore", "pipe", "pipe"],
});
capture(vite.stdout);
capture(vite.stderr);

let electronApp;

try {
  await waitForRenderer();
  pass("Vite renderer is reachable");

  electronApp = await electron.launch({
    executablePath: electronPath,
    args: [desktopDir],
    cwd: desktopDir,
    env: {
      ...process.env,
      MENTORA_DEV_SERVER_URL: rendererUrl,
    },
    timeout: startupTimeoutMs,
  });

  const page = await waitForRendererWindow(electronApp);
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(error));
  await page.waitForLoadState("domcontentloaded");

  assert(
    page.url().startsWith(rendererUrl) ||
      /\/apps\/web\/dist\/index\.html$/i.test(page.url()),
    `Unexpected renderer URL: ${page.url()}`,
  );
  assert((await page.title()).trim().length > 0, "Renderer title is empty");
  pass("Electron main window loaded the renderer");

  const chromeState = await electronApp.evaluate(({ BrowserWindow, Menu }) => {
    const window = BrowserWindow.getAllWindows()[0];
    if (!window) throw new Error("Main window disappeared");
    return {
      bounds: window.getBounds(),
      contentBounds: window.getContentBounds(),
      menuBarVisible: window.isMenuBarVisible(),
      hasMenu: Menu.getApplicationMenu() !== null,
    };
  });
  process.stdout.write(`[INFO] Window chrome: ${JSON.stringify(chromeState)}\n`);
  assert(!chromeState.menuBarVisible, "Native menu bar must not be visible");
  assert(!chromeState.hasMenu, "Electron application menu must be removed");

  await page.waitForSelector("[data-desktop-titlebar]", {
    timeout: startupTimeoutMs,
  });
  const rendererChrome = await page.evaluate(() => {
    const titleBars = document.querySelectorAll("[data-desktop-titlebar]");
    const dragRegion = document.querySelector("[data-desktop-drag-region]");
    const noDragRegion = document.querySelector("[data-desktop-no-drag]");
    return {
      titleBarCount: titleBars.length,
      hasDragRegion:
        dragRegion !== null &&
        getComputedStyle(dragRegion).getPropertyValue("-webkit-app-region") ===
          "drag",
      hasNoDragRegion:
        noDragRegion !== null &&
        getComputedStyle(noDragRegion).getPropertyValue("-webkit-app-region") ===
          "no-drag",
      documentOverflows:
        document.documentElement.scrollHeight > window.innerHeight ||
        document.documentElement.scrollWidth > window.innerWidth,
    };
  });
  assert(rendererChrome.titleBarCount === 1, "Renderer must expose one title bar");
  assert(rendererChrome.hasDragRegion, "Title bar must expose a drag region");
  assert(rendererChrome.hasNoDragRegion, "Title bar controls must be non-draggable");
  assert(!rendererChrome.documentOverflows, "Document must not overflow the viewport");
  pass("Desktop chrome and viewport constraints passed");

  const bridgeState = await page.evaluate(async () => ({
    hasBridge: typeof window.mentoraDesktop === "object",
    appInfo: await window.mentoraDesktop?.app.getInfo(),
    hasRequire: typeof window.require !== "undefined",
    hasProcess: typeof window.process !== "undefined",
    hasIpcRenderer:
      typeof window.mentoraDesktop?.ipcRenderer !== "undefined",
  }));

  assert(bridgeState.hasBridge, "window.mentoraDesktop was not injected");
  assert(
    bridgeState.appInfo?.platform === process.platform,
    "app.getInfo platform mismatch",
  );
  assert(bridgeState.appInfo?.isPackaged === false, "Smoke must run unpackaged");
  assert(!bridgeState.hasRequire, "window.require must not be exposed");
  assert(!bridgeState.hasProcess, "window.process must not be exposed");
  assert(!bridgeState.hasIpcRenderer, "ipcRenderer must not be exposed");
  pass("Preload bridge and renderer isolation checks passed");

  await page.evaluate(() => window.mentoraDesktop.window.minimize());
  await electronApp.evaluate(({ BrowserWindow }) => {
    const window = BrowserWindow.getAllWindows()[0];
    if (!window) throw new Error("Main window disappeared");
    if (!window.isMinimized()) throw new Error("Window did not minimize");
    window.restore();
  });

  await page.evaluate(() => window.mentoraDesktop.window.toggleMaximize());
  await electronApp.evaluate(({ BrowserWindow }) => {
    const window = BrowserWindow.getAllWindows()[0];
    if (!window) throw new Error("Main window disappeared");
    if (!window.isMaximized()) throw new Error("Window did not maximize");
    window.unmaximize();
  });
  pass("Window control IPC checks passed");

  assert(pageErrors.length === 0, `Renderer page errors: ${pageErrors.join("\n")}`);
  pass("Renderer reported no uncaught page errors");
} finally {
  if (electronApp) {
    await electronApp.close().catch(() => undefined);
  }
  terminateProcessTree(vite);
}
