import {
  app,
  dialog,
  ipcMain,
  Notification,
  shell,
  BrowserWindow,
  type IpcMainInvokeEvent,
} from "electron";
import path from "node:path";

import { Channels } from "../../shared/channels";
import type { AppInfo, AuthStatus, PickedFile } from "../../shared/desktopApi";
import {
  ApiRequestSchema,
  EventStreamOptionsSchema,
  ExternalUrlSchema,
  FileTokenSchema,
  NotificationRequestSchema,
  StreamIdSchema,
  UploadIdSchema,
  UploadStartRequestSchema,
} from "../../shared/schemas";
import type { ApiClient } from "../apiClient";
import type { AuthManager } from "../auth";
import type { EventStreamBridge } from "../eventStreams";
import type { FileTokenStore } from "../fileTokens";
import type { UploadManager } from "../uploads";
import type { UpdaterService } from "../updater";
import { createLogger } from "../logger";

const log = createLogger("ipc");

export interface Services {
  auth: AuthManager;
  api: ApiClient;
  events: EventStreamBridge;
  files: FileTokenStore;
  uploads: UploadManager;
  updater: UpdaterService;
}

const EXTENSION_MIME: Record<string, string> = {
  ".pdf": "application/pdf",
  ".ppt": "application/vnd.ms-powerpoint",
  ".pptx":
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ".doc": "application/msword",
  ".docx":
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".mp4": "video/mp4",
  ".mov": "video/quicktime",
  ".txt": "text/plain",
  ".md": "text/markdown",
};

function windowFromEvent(event: IpcMainInvokeEvent): BrowserWindow | null {
  return BrowserWindow.fromWebContents(event.sender);
}

/** 约束：handler 执行业务前须 zod 校验 payload；禁止 catch-all（§3.2） */
export function registerIpc(services: Services): void {
  ipcMain.handle(Channels.app.info, (): AppInfo => ({
    version: app.getVersion(),
    platform: process.platform,
    isPackaged: app.isPackaged,
    locale: app.getLocale(),
  }));

  ipcMain.handle(Channels.auth.status, (): AuthStatus => services.auth.getStatus());
  ipcMain.handle(Channels.auth.login, () => services.auth.login());
  ipcMain.handle(Channels.auth.logout, () => services.auth.logout());

  ipcMain.handle(Channels.api.request, (_event, raw) => {
    const req = ApiRequestSchema.parse(raw);
    return services.api.request(req);
  });

  ipcMain.handle(Channels.events.open, (event, raw) => {
    const options = EventStreamOptionsSchema.parse(raw);
    return services.events.open(event.sender, options);
  });
  ipcMain.handle(Channels.events.abort, (_event, raw) => {
    services.events.abort(StreamIdSchema.parse(raw));
  });

  ipcMain.handle(Channels.files.pick, async (event): Promise<PickedFile[]> => {
    const window = windowFromEvent(event);
    const result = await dialog.showOpenDialog(window ?? undefined!, {
      properties: ["openFile", "multiSelections"],
      filters: [
        {
          name: "Learning materials",
          extensions: ["pdf", "ppt", "pptx", "doc", "docx", "mp4", "mov", "txt", "md"],
        },
      ],
    });
    if (result.canceled) return [];

    const { promises: fs } = await import("node:fs");
    const picked: PickedFile[] = [];
    for (const absolutePath of result.filePaths) {
      const stats = await fs.stat(absolutePath);
      const name = path.basename(absolutePath);
      const ext = path.extname(absolutePath).toLowerCase();
      const mime = EXTENSION_MIME[ext] ?? "application/octet-stream";
      const fileToken = services.files.issue(event.sender, {
        absolutePath,
        name,
        size: stats.size,
        mime,
      });
      picked.push({ fileToken, name, size: stats.size, mime });
    }
    return picked;
  });

  ipcMain.handle(Channels.uploads.start, (event, raw) => {
    const req = UploadStartRequestSchema.parse(raw);
    return services.uploads.start(event.sender, req);
  });
  ipcMain.handle(Channels.uploads.cancel, (_event, raw) => {
    services.uploads.cancel(UploadIdSchema.parse(raw));
  });

  ipcMain.handle(Channels.shell.openExternal, (_event, raw) => {
    const url = ExternalUrlSchema.parse(raw);
    return shell.openExternal(url);
  });
  ipcMain.handle(Channels.shell.showItemInFolder, (event, raw) => {
    const token = FileTokenSchema.parse(raw);
    const grant = services.files.resolve(token, event.sender);
    if (!grant) throw new Error("Invalid or expired file token");
    shell.showItemInFolder(grant.absolutePath);
  });

  ipcMain.handle(Channels.notifications.show, (event, raw) => {
    const req = NotificationRequestSchema.parse(raw);
    const notification = new Notification({ title: req.title, body: req.body });
    if (req.route) {
      notification.on("click", () => {
        if (!event.sender.isDestroyed()) {
          event.sender.send(Channels.notifications.activated, req.route);
        }
      });
    }
    notification.show();
  });

  ipcMain.handle(Channels.updater.check, () => services.updater.check());
  ipcMain.handle(Channels.updater.quitAndInstall, () =>
    services.updater.quitAndInstall(),
  );

  ipcMain.handle(Channels.window.minimize, (event) =>
    windowFromEvent(event)?.minimize(),
  );
  ipcMain.handle(Channels.window.toggleMaximize, (event) => {
    const window = windowFromEvent(event);
    if (!window) return;
    if (window.isMaximized()) window.unmaximize();
    else window.maximize();
  });
  ipcMain.handle(Channels.window.close, (event) => windowFromEvent(event)?.close());

  log.info("IPC handlers registered");
}
