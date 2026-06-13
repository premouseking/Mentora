/**
 * 渲染进程桌面能力边界：`window.mentoraDesktop`
 *
 * 约束：
 * - 不得访问 ipcRenderer、Node、文件系统、环境变量或 token
 * - 方法映射 allowlist IPC 通道，DTO 与 preload/main 共享
 *
 * @see docs/architecture/desktop-client-architecture.md §3.2
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

/** 约束：仅相对 path；token 由 main 注入（§5.1） */
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

/** 约束：renderer 不得看到或提交绝对路径（§6.1） */
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
  route?: string;
}

export interface DeepLink {
  domain: string;
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
