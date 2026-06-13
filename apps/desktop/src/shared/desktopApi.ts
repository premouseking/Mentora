/**
 * The typed surface exposed to the renderer as `window.mentoraDesktop`.
 *
 * This is the ONLY desktop capability boundary the renderer sees. There is no
 * `ipcRenderer`, no Node module, no filesystem, and no token access. Every
 * method maps to an allow-listed IPC channel and shares these DTOs across
 * preload and main (desktop-client-architecture §3.2).
 */

export type Unsubscribe = () => void;

export interface AppInfo {
  version: string;
  platform: NodeJS.Platform;
  isPackaged: boolean;
  locale: string;
}

export type AuthState = "signed-out" | "signing-in" | "signed-in";

export interface AuthStatus {
  state: AuthState;
  accountId?: string;
  displayName?: string;
}

/**
 * API bridge request. The renderer never supplies an absolute URL: only a
 * relative API path that the main process matches against an allowlist before
 * attaching the access token (desktop-client-architecture §5.1).
 */
export interface ApiRequest {
  path: string;
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  query?: Record<string, string | number | boolean | undefined>;
  body?: unknown;
  signalId?: string;
}

export interface ApiResponse<T = unknown> {
  ok: boolean;
  status: number;
  data: T;
  requestId: string;
}

export interface EventStreamOptions {
  path: string;
  lastEventId?: string;
}

export interface StreamHandle {
  streamId: string;
}

export type StreamMessage =
  | { streamId: string; kind: "head"; status: number }
  | { streamId: string; kind: "event"; id?: string; event?: string; data: string }
  | { streamId: string; kind: "error"; message: string }
  | { streamId: string; kind: "end" };

/**
 * A short-lived, window-bound handle to a user-selected file. The renderer
 * never sees or submits absolute paths (desktop-client-architecture §6.1).
 */
export interface PickedFile {
  fileToken: string;
  name: string;
  size: number;
  mime: string;
}

export interface UploadStartRequest {
  fileToken: string;
  courseId?: string;
}

export interface UploadProgress {
  uploadId: string;
  phase: "creating" | "uploading" | "completing" | "done" | "error" | "cancelled";
  bytesSent: number;
  bytesTotal: number;
  message?: string;
}

export type UpdaterStatus =
  | { state: "disabled"; reason: string }
  | { state: "checking" }
  | { state: "up-to-date" }
  | { state: "available"; version: string }
  | { state: "downloading"; percent: number }
  | { state: "ready"; version: string }
  | { state: "error"; message: string };

export interface NotificationRequest {
  title: string;
  body: string;
  /** Internal route opened when the user clicks the notification. */
  route?: string;
}

export interface DeepLink {
  /** e.g. "auth", "course", "task" */
  domain: string;
  /** Remaining path, e.g. "callback" or a course id. */
  path: string;
  params: Record<string, string>;
}

export interface MentoraDesktopApi {
  app: {
    getInfo(): Promise<AppInfo>;
  };
  auth: {
    getStatus(): Promise<AuthStatus>;
    login(): Promise<AuthStatus>;
    logout(): Promise<void>;
    onChanged(listener: (status: AuthStatus) => void): Unsubscribe;
  };
  api: {
    request<T = unknown>(req: ApiRequest): Promise<ApiResponse<T>>;
  };
  events: {
    open(options: EventStreamOptions): Promise<StreamHandle>;
    abort(streamId: string): Promise<void>;
    onMessage(listener: (message: StreamMessage) => void): Unsubscribe;
  };
  files: {
    pick(): Promise<PickedFile[]>;
  };
  uploads: {
    start(req: UploadStartRequest): Promise<{ uploadId: string }>;
    cancel(uploadId: string): Promise<void>;
    onProgress(listener: (progress: UploadProgress) => void): Unsubscribe;
  };
  shell: {
    openExternal(url: string): Promise<void>;
    showItemInFolder(fileToken: string): Promise<void>;
  };
  notifications: {
    show(req: NotificationRequest): Promise<void>;
    onActivated(listener: (route: string) => void): Unsubscribe;
  };
  updater: {
    check(): Promise<void>;
    quitAndInstall(): Promise<void>;
    onStatus(listener: (status: UpdaterStatus) => void): Unsubscribe;
  };
  window: {
    minimize(): Promise<void>;
    toggleMaximize(): Promise<void>;
    close(): Promise<void>;
    onDeepLink(listener: (link: DeepLink) => void): Unsubscribe;
  };
}

declare global {
  interface Window {
    mentoraDesktop: MentoraDesktopApi;
  }
}
