import { app, BrowserWindow, Menu } from "electron";

import { isDev, isDevAuthBypassEnabled } from "./config";
import { createLogger } from "./logger";
import { createMainWindow } from "./window";
import { AuthManager } from "./auth";
import { ApiClient } from "./apiClient";
import { EventStreamBridge } from "./eventStreams";
import { FileTokenStore } from "./fileTokens";
import { UploadManager } from "./uploads";
import { UpdaterService } from "./updater";
import { registerIpc, type Services } from "./ipc";
import { Channels } from "../shared/channels";

const log = createLogger("bootstrap");

let mainWindow: BrowserWindow | null = null;
let services: Services | null = null;

function focusMainWindow(): void {
  if (!mainWindow) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.focus();
}

function wireRendererCleanup(window: BrowserWindow): void {
  // renderer 销毁时须回收其 SSE、上传与 fileToken，避免泄漏
  window.webContents.on("destroyed", () => {
    if (!services) return;
    services.events.abortAllFor(window.webContents);
    services.uploads.cancelAllFor(window.webContents);
    services.files.revokeAllFor(window.webContents);
  });
}

function createServices(): Services {
  const auth = new AuthManager();
  const api = new ApiClient(auth);
  const events = new EventStreamBridge(auth);
  const files = new FileTokenStore();
  const uploads = new UploadManager(api, files);
  const updater = new UpdaterService();
  return { auth, api, events, files, uploads, updater };
}

async function onReady(): Promise<void> {
  Menu.setApplicationMenu(null);
  services = createServices();
  await services.auth.initialize();
  registerIpc(services);

  services.auth.on("changed", (status) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send(Channels.auth.changed, status);
    }
  });

  mainWindow = createMainWindow();
  wireRendererCleanup(mainWindow);
  services.updater.attach(mainWindow);
  services.updater.initialize();
}

export function bootstrap(): void {
  if (process.platform === "win32") {
    // 开发态须与 electron-builder appId 一致，否则任务栏仍显示 Electron 默认图标
    app.setAppUserModelId("com.mentora.desktop");
  }

  const gotLock = app.requestSingleInstanceLock();
  if (!gotLock) {
    app.quit();
    return;
  }

  app.on("second-instance", () => {
    focusMainWindow();
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin") app.quit();
  });

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) void onReady();
  });

  app.whenReady().then(onReady).catch((err) => {
    log.error("Failed during app ready", { message: String(err) });
    app.quit();
  });

  if (isDev) {
    log.info("Bootstrapping in development mode", {
      authBypass: isDevAuthBypassEnabled(),
    });
  }
}
