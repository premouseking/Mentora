import { app, safeStorage } from "electron";
import { promises as fs } from "node:fs";
import path from "node:path";
import { EventEmitter } from "node:events";

import type {
  AuthCredentials,
  AuthRegisterRequest,
  AuthStatus,
} from "../shared/desktopApi";
import {
  API_BASE_URL,
  DEV_AUTH_BYPASS_ACCOUNT_ID,
  isDevAuthBypassEnabled,
} from "./config";
import { createLogger } from "./logger";

const log = createLogger("auth");

interface TokenResponse {
  access: string;
  refresh: string;
  user_id?: string;
  display_name?: string;
}

/** 约束：长效 token 不得进入 renderer（§5.3） */
export class AuthManager extends EventEmitter {
  private status: AuthStatus = { state: "signed-out" };
  private accessToken: string | null = null;
  private refreshPromise: Promise<string | null> | null = null;

  private get tokenFile(): string {
    return path.join(app.getPath("userData"), "refresh.bin");
  }

  async initialize(): Promise<void> {
    const refreshToken = await this.readRefreshToken();
    if (refreshToken) {
      this.setStatus({ state: "signed-in" });
      return;
    }
    if (isDevAuthBypassEnabled()) {
      this.setStatus({
        state: "signed-in",
        accountId: DEV_AUTH_BYPASS_ACCOUNT_ID,
        displayName: "开发用户",
      });
    }
  }

  getStatus(): AuthStatus {
    return this.status;
  }

  async login(credentials: AuthCredentials): Promise<AuthStatus> {
    this.setStatus({ state: "signing-in" });
    try {
      await this.exchangeCredentials("/auth/login/", {
        email: credentials.email,
        password: credentials.password,
      });
      return this.status;
    } catch (err) {
      log.error("Login failed", { message: String(err) });
      this.setStatus({ state: "signed-out" });
      throw err;
    }
  }

  async register(request: AuthRegisterRequest): Promise<AuthStatus> {
    this.setStatus({ state: "signing-in" });
    try {
      const body: Record<string, string> = {
        email: request.email,
        password: request.password,
      };
      if (request.displayName) body.display_name = request.displayName;
      await this.exchangeCredentials("/auth/register/", body);
      return this.status;
    } catch (err) {
      log.error("Register failed", { message: String(err) });
      this.setStatus({ state: "signed-out" });
      throw err;
    }
  }

  async logout(): Promise<void> {
    this.accessToken = null;
    await fs.rm(this.tokenFile, { force: true }).catch(() => undefined);
    this.setStatus({ state: "signed-out" });
  }

  async getAccessToken(): Promise<string | null> {
    if (this.accessToken) return this.accessToken;
    return this.refreshAccessToken();
  }

  async refreshAccessToken(): Promise<string | null> {
    if (this.refreshPromise) return this.refreshPromise;

    this.refreshPromise = (async () => {
      const refreshToken = await this.readRefreshToken();
      if (!refreshToken) {
        this.setStatus({ state: "signed-out" });
        return null;
      }
      try {
        const res = await fetch(`${API_BASE_URL}/auth/refresh/`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ refresh: refreshToken }),
        });
        if (!res.ok) throw new Error(`refresh failed: ${res.status}`);
        const data = (await res.json()) as TokenResponse;
        await this.applyTokenResponse(data);
        return this.accessToken;
      } catch (err) {
        log.warn("Access token refresh failed", { message: String(err) });
        await this.logout();
        return null;
      } finally {
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  private async exchangeCredentials(
    apiPath: string,
    body: Record<string, string>,
  ): Promise<void> {
    const res = await fetch(`${API_BASE_URL}${apiPath}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      throw new Error(await this.readErrorMessage(res));
    }
    const data = (await res.json()) as TokenResponse;
    await this.applyTokenResponse(data);
  }

  private async applyTokenResponse(data: TokenResponse): Promise<void> {
    this.accessToken = data.access;
    await this.writeRefreshToken(data.refresh);
    this.setStatus({
      state: "signed-in",
      accountId: data.user_id,
      displayName: data.display_name,
    });
  }

  private async readErrorMessage(res: Response): Promise<string> {
    try {
      const body = (await res.json()) as {
        error?: string;
        detail?: string;
        message?: string;
      };
      return body.error ?? body.detail ?? body.message ?? `认证失败（${res.status}）`;
    } catch {
      return `认证失败（${res.status}）`;
    }
  }

  private setStatus(status: AuthStatus): void {
    this.status = status;
    this.emit("changed", status);
  }

  private async writeRefreshToken(token: string): Promise<void> {
    if (!safeStorage.isEncryptionAvailable()) {
      log.warn("safeStorage unavailable; refusing to persist refresh token in plaintext");
      return;
    }
    const encrypted = safeStorage.encryptString(token);
    await fs.writeFile(this.tokenFile, encrypted);
  }

  private async readRefreshToken(): Promise<string | null> {
    try {
      const encrypted = await fs.readFile(this.tokenFile);
      if (!safeStorage.isEncryptionAvailable()) return null;
      return safeStorage.decryptString(encrypted);
    } catch {
      return null;
    }
  }
}
