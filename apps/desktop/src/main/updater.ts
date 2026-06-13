import { app } from "electron";
import type { BrowserWindow } from "electron";
import { autoUpdater } from "electron-updater";

import type { UpdaterStatus } from "../shared/desktopApi";
import { Channels } from "../shared/channels";
import { isDev } from "./config";
import { createLogger } from "./logger";

const log = createLogger("updater");

/**
 * Wraps electron-updater. Dev and unpacked builds never check for updates;
 * packaged builds check after a short delay, download in the background, and
 * only install when the user explicitly clicks "restart and install"
 * (desktop-client-architecture §10).
 */
export class UpdaterService {
  private status: UpdaterStatus = { state: "disabled", reason: "not initialized" };
  private window: BrowserWindow | null = null;

  attach(window: BrowserWindow): void {
    this.window = window;
  }

  initialize(): void {
    if (isDev || !app.isPackaged) {
      this.setStatus({ state: "disabled", reason: "dev or unpacked build" });
      return;
    }

    autoUpdater.autoDownload = true;
    autoUpdater.autoInstallOnAppQuit = false;
    autoUpdater.logger = null;

    autoUpdater.on("checking-for-update", () => this.setStatus({ state: "checking" }));
    autoUpdater.on("update-not-available", () =>
      this.setStatus({ state: "up-to-date" }),
    );
    autoUpdater.on("update-available", (info) =>
      this.setStatus({ state: "available", version: info.version }),
    );
    autoUpdater.on("download-progress", (p) =>
      this.setStatus({ state: "downloading", percent: Math.round(p.percent) }),
    );
    autoUpdater.on("update-downloaded", (info) =>
      this.setStatus({ state: "ready", version: info.version }),
    );
    autoUpdater.on("error", (err) =>
      this.setStatus({ state: "error", message: String(err) }),
    );

    setTimeout(() => void this.check(), 8_000);
  }

  async check(): Promise<void> {
    if (this.status.state === "disabled") return;
    try {
      await autoUpdater.checkForUpdates();
    } catch (err) {
      log.warn("Update check failed", { message: String(err) });
    }
  }

  quitAndInstall(): void {
    if (this.status.state !== "ready") return;
    autoUpdater.quitAndInstall(false, true);
  }

  getStatus(): UpdaterStatus {
    return this.status;
  }

  private setStatus(status: UpdaterStatus): void {
    this.status = status;
    if (this.window && !this.window.isDestroyed()) {
      this.window.webContents.send(Channels.updater.status, status);
    }
  }
}
