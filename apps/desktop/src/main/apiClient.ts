import { app } from "electron";
import { randomUUID } from "node:crypto";

import type { ApiResponse } from "../shared/desktopApi";
import type { ApiRequestInput } from "../shared/schemas";
import {
  API_BASE_URL,
  MAX_API_BODY_BYTES,
  isAllowedApiPath,
} from "./config";
import { createLogger } from "./logger";
import type { AuthManager } from "./auth";

const log = createLogger("api");

/** 约束：非开放代理；path 须匹配 allowlist，body 有大小上限（§5.1） */
export class ApiClient {
  private readonly deviceId = randomUUID();
  private readonly inflight = new Map<string, AbortController>();

  constructor(private readonly auth: AuthManager) {}

  cancel(signalId: string): void {
    this.inflight.get(signalId)?.abort();
    this.inflight.delete(signalId);
  }

  async request<T = unknown>(req: ApiRequestInput): Promise<ApiResponse<T>> {
    if (!isAllowedApiPath(req.path)) {
      throw new Error(`API path not allowed: ${req.path}`);
    }

    const bodyText =
      req.body === undefined ? undefined : JSON.stringify(req.body);
    if (bodyText && Buffer.byteLength(bodyText) > MAX_API_BODY_BYTES) {
      throw new Error("Request body exceeds the maximum allowed size");
    }

    const url = new URL(API_BASE_URL + req.path);
    if (req.query) {
      for (const [key, value] of Object.entries(req.query)) {
        if (value !== undefined) url.searchParams.set(key, String(value));
      }
    }

    const requestId = randomUUID();
    const controller = new AbortController();
    if (req.signalId) this.inflight.set(req.signalId, controller);
    const timeout = setTimeout(() => controller.abort(), 30_000);

    try {
      let response = await this.send(url, req, bodyText, requestId, controller);

      if (response.status === 401) {
        const refreshed = await this.auth.refreshAccessToken();
        if (refreshed) {
          response = await this.send(url, req, bodyText, requestId, controller);
        }
      }

      const data = (await this.parseBody(response)) as T;
      return {
        ok: response.ok,
        status: response.status,
        data,
        requestId,
      };
    } catch (err) {
      log.warn("API request failed", { requestId, message: String(err) });
      throw err instanceof Error ? err : new Error("API request failed");
    } finally {
      clearTimeout(timeout);
      if (req.signalId) this.inflight.delete(req.signalId);
    }
  }

  private async send(
    url: URL,
    req: ApiRequestInput,
    bodyText: string | undefined,
    requestId: string,
    controller: AbortController,
  ): Promise<Response> {
    const headers: Record<string, string> = {
      accept: "application/json",
      "x-request-id": requestId,
      "x-device-id": this.deviceId,
      "x-client-version": app.getVersion(),
    };
    if (bodyText) headers["content-type"] = "application/json";

    const token = await this.auth.getAccessToken();
    if (token) headers.authorization = `Bearer ${token}`;

    return fetch(url, {
      method: req.method,
      headers,
      body: bodyText,
      signal: controller.signal,
    });
  }

  private async parseBody(response: Response): Promise<unknown> {
    const contentType = response.headers.get("content-type") ?? "";
    if (contentType.includes("application/json")) {
      return response.json().catch(() => null);
    }
    return response.text().catch(() => "");
  }
}
