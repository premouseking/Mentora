export const DEV_AUTH_BYPASS_ACCOUNT_ID = "dev-bypass";

export type AuthState = "signed-out" | "signing-in" | "signed-in";

export interface AuthStatus {
  state: AuthState;
  accountId?: string;
  displayName?: string;
}

export interface AuthCredentials {
  email: string;
  password: string;
}

export interface AuthRegisterRequest extends AuthCredentials {
  displayName?: string;
}

export interface DesktopAuthApi {
  getStatus(): Promise<AuthStatus>;
  login(credentials: AuthCredentials): Promise<AuthStatus>;
  register(request: AuthRegisterRequest): Promise<AuthStatus>;
  logout(): Promise<void>;
  onChanged(listener: (status: AuthStatus) => void): () => void;
}

/** 约束：凭据仅经 IPC 交给主进程，renderer 不得直连后端 */
export interface DesktopWindowApi {
  minimize(): Promise<void>;
  toggleMaximize(): Promise<void>;
  close(): Promise<void>;
}

export interface DesktopApi {
  auth: DesktopAuthApi;
  window: DesktopWindowApi;
}

export function getDesktopApi(): DesktopApi | null {
  if (typeof window === "undefined" || !("mentoraDesktop" in window)) {
    return null;
  }
  return window.mentoraDesktop as DesktopApi;
}

export function isDesktopHost(): boolean {
  return getDesktopApi() !== null;
}

/** 约束：与主进程 dev bypass 的 accountId 对齐，仅用于 UI 提示 */
export function isDevAuthBypassStatus(status: AuthStatus): boolean {
  return status.accountId === DEV_AUTH_BYPASS_ACCOUNT_ID;
}

export const DEV_AUTH_BYPASS_STATUS: AuthStatus = {
  state: "signed-in",
  accountId: DEV_AUTH_BYPASS_ACCOUNT_ID,
  displayName: "开发用户",
};
