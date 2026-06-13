import { app, safeStorage, shell } from "electron";
import { randomBytes, createHash } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";
import { EventEmitter } from "node:events";

import type { AuthStatus, DeepLink } from "../shared/desktopApi";
import { API_BASE_URL, APP_PROTOCOL } from "./config";
import { createLogger } from "./logger";

const log = createLogger("auth");

interface PendingLogin {
  state: string;
  codeVerifier: string;
}

/** 约束：长效 token 不得进入 renderer 或出现在传给 renderer 的 URL 中（§5.3） */
export class AuthManager extends EventEmitter {
  private status: AuthStatus = { state: "signed-out" };
  private accessToken: string | null = null;
  private refreshPromise: Promise<string | null> | null = null;
  private pendingLogin: PendingLogin | null = null;

  private get tokenFile(): string {
    return path.join(app.getPath("userData"), "refresh.bin");
  }

  async initialize(): Promise<void> {
    const refreshToken = await this.readRefreshToken();
    if (refreshToken) {
      this.setStatus({ state: "signed-in" });
    }
  }

  getStatus(): AuthStatus {
    return this.status;
  }

  async login(): Promise<AuthStatus> {
    const state = randomBytes(16).toString("hex");
    const codeVerifier = randomBytes(32).toString("base64url");
    const codeChallenge = createHash("sha256")
      .update(codeVerifier)
      .digest("base64url");

    this.pendingLogin = { state, codeVerifier };
    this.setStatus({ state: "signing-in" });

    const authUrl = new URL(`${API_BASE_URL}/auth/authorize/`);
    authUrl.searchParams.set("response_type", "code");
    authUrl.searchParams.set("redirect_uri", `${APP_PROTOCOL}://auth/callback`);
    authUrl.searchParams.set("state", state);
    authUrl.searchParams.set("code_challenge", codeChallenge);
    authUrl.searchParams.set("code_challenge_method", "S256");

    await shell.openExternal(authUrl.toString());
    return this.status;
  }

  async handleCallback(link: DeepLink): Promise<void> {
    if (link.domain !== "auth" || link.path !== "callback") return;

    const pending = this.pendingLogin;
    this.pendingLogin = null;

    if (!pending || link.params.state !== pending.state) {
      log.warn("Rejected auth callback with mismatched state");
      this.setStatus({ state: "signed-out" });
      return;
    }

    const code = link.params.code;
    if (!code) {
      this.setStatus({ state: "signed-out" });
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/auth/token/`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          grant_type: "authorization_code",
          code,
          code_verifier: pending.codeVerifier,
          redirect_uri: `${APP_PROTOCOL}://auth/callback`,
        }),
      });
      if (!res.ok) throw new Error(`token exchange failed: ${res.status}`);
      const data = (await res.json()) as {
        access_token: string;
        refresh_token: string;
        account_id?: string;
        display_name?: string;
      };
      this.accessToken = data.access_token;
      await this.writeRefreshToken(data.refresh_token);
      this.setStatus({
        state: "signed-in",
        accountId: data.account_id,
        displayName: data.display_name,
      });
    } catch (err) {
      log.error("Login token exchange failed", { message: String(err) });
      this.setStatus({ state: "signed-out" });
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
        const res = await fetch(`${API_BASE_URL}/auth/token/`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            grant_type: "refresh_token",
            refresh_token: refreshToken,
          }),
        });
        if (!res.ok) throw new Error(`refresh failed: ${res.status}`);
        const data = (await res.json()) as {
          access_token: string;
          refresh_token?: string;
        };
        this.accessToken = data.access_token;
        if (data.refresh_token) await this.writeRefreshToken(data.refresh_token);
        if (this.status.state !== "signed-in") {
          this.setStatus({ state: "signed-in" });
        }
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
