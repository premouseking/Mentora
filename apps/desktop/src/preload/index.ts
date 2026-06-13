import { contextBridge, ipcRenderer, type IpcRendererEvent } from "electron";

import { Channels } from "../shared/channels";
import type {
  ApiRequest,
  ApiResponse,
  AppInfo,
  AuthStatus,
  DeepLink,
  EventStreamOptions,
  MentoraDesktopApi,
  NotificationRequest,
  PickedFile,
  StreamHandle,
  StreamMessage,
  Unsubscribe,
  UpdaterStatus,
  UploadProgress,
  UploadStartRequest,
} from "../shared/desktopApi";

/**
 * Subscribes to a broadcast channel and returns an unsubscribe function. The raw
 * IpcRendererEvent is never forwarded to the renderer listener so the renderer
 * cannot reach back into the IPC layer (desktop-client-architecture §3.2).
 */
function subscribe<T>(
  channel: string,
  listener: (payload: T) => void,
): Unsubscribe {
  const handler = (_event: IpcRendererEvent, payload: T) => listener(payload);
  ipcRenderer.on(channel, handler);
  return () => ipcRenderer.removeListener(channel, handler);
}

// Lightweight guards. The main process performs authoritative zod validation;
// these only catch obvious renderer mistakes early.
function requireString(value: unknown, name: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new TypeError(`${name} must be a non-empty string`);
  }
  return value;
}

function requireObject(value: unknown, name: string): void {
  if (typeof value !== "object" || value === null) {
    throw new TypeError(`${name} must be an object`);
  }
}

const api: MentoraDesktopApi = {
  app: {
    getInfo: () => ipcRenderer.invoke(Channels.app.info) as Promise<AppInfo>,
  },
  auth: {
    getStatus: () =>
      ipcRenderer.invoke(Channels.auth.status) as Promise<AuthStatus>,
    login: () => ipcRenderer.invoke(Channels.auth.login) as Promise<AuthStatus>,
    logout: () => ipcRenderer.invoke(Channels.auth.logout) as Promise<void>,
    onChanged: (listener) =>
      subscribe<AuthStatus>(Channels.auth.changed, listener),
  },
  api: {
    request: <T = unknown>(req: ApiRequest) => {
      requireObject(req, "request");
      requireString(req.path, "request.path");
      return ipcRenderer.invoke(Channels.api.request, req) as Promise<
        ApiResponse<T>
      >;
    },
  },
  events: {
    open: (options: EventStreamOptions) => {
      requireObject(options, "options");
      requireString(options.path, "options.path");
      return ipcRenderer.invoke(
        Channels.events.open,
        options,
      ) as Promise<StreamHandle>;
    },
    abort: (streamId) =>
      ipcRenderer.invoke(
        Channels.events.abort,
        requireString(streamId, "streamId"),
      ) as Promise<void>,
    onMessage: (listener) =>
      subscribe<StreamMessage>(Channels.events.message, listener),
  },
  files: {
    pick: () => ipcRenderer.invoke(Channels.files.pick) as Promise<PickedFile[]>,
  },
  uploads: {
    start: (req: UploadStartRequest) => {
      requireObject(req, "request");
      requireString(req.fileToken, "request.fileToken");
      return ipcRenderer.invoke(Channels.uploads.start, req) as Promise<{
        uploadId: string;
      }>;
    },
    cancel: (uploadId) =>
      ipcRenderer.invoke(
        Channels.uploads.cancel,
        requireString(uploadId, "uploadId"),
      ) as Promise<void>,
    onProgress: (listener) =>
      subscribe<UploadProgress>(Channels.uploads.progress, listener),
  },
  shell: {
    openExternal: (url) =>
      ipcRenderer.invoke(
        Channels.shell.openExternal,
        requireString(url, "url"),
      ) as Promise<void>,
    showItemInFolder: (fileToken) =>
      ipcRenderer.invoke(
        Channels.shell.showItemInFolder,
        requireString(fileToken, "fileToken"),
      ) as Promise<void>,
  },
  notifications: {
    show: (req: NotificationRequest) => {
      requireObject(req, "request");
      requireString(req.title, "request.title");
      return ipcRenderer.invoke(Channels.notifications.show, req) as Promise<void>;
    },
    onActivated: (listener) =>
      subscribe<string>(Channels.notifications.activated, listener),
  },
  updater: {
    check: () => ipcRenderer.invoke(Channels.updater.check) as Promise<void>,
    quitAndInstall: () =>
      ipcRenderer.invoke(Channels.updater.quitAndInstall) as Promise<void>,
    onStatus: (listener) =>
      subscribe<UpdaterStatus>(Channels.updater.status, listener),
  },
  window: {
    minimize: () =>
      ipcRenderer.invoke(Channels.window.minimize) as Promise<void>,
    toggleMaximize: () =>
      ipcRenderer.invoke(Channels.window.toggleMaximize) as Promise<void>,
    close: () => ipcRenderer.invoke(Channels.window.close) as Promise<void>,
    onDeepLink: (listener) =>
      subscribe<DeepLink>(Channels.window.deepLink, listener),
  },
};

contextBridge.exposeInMainWorld("mentoraDesktop", api);
