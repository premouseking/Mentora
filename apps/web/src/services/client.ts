/**
 * 统一 API 客户端。
 *
 * 约定：
 * - 所有后端请求走 apiClient，统一注入 Authorization 头
 * - access token 过期时自动用 refresh token 换取新 token 后重试
 * - 超时 60s，支持 AbortSignal
 *
 * 约束：
 * - 不对 auth 端点（/api/auth/）注入 token
 *
 * @module services/client
 */

const TOKEN_KEY = "mentora-auth";
const DEFAULT_TIMEOUT_MS = 60_000;

/* ── Token 持久化 ── */

export interface TokenData {
  access: string;
  refresh: string;
  userId: string;
  displayName: string;
}

export const tokenStore = {
  get(): TokenData | null {
    try {
      const raw = localStorage.getItem(TOKEN_KEY);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (parsed.access && parsed.refresh) return parsed as TokenData;
      return null;
    } catch {
      return null;
    }
  },
  set(data: TokenData): void {
    localStorage.setItem(TOKEN_KEY, JSON.stringify(data));
  },
  clear(): void {
    localStorage.removeItem(TOKEN_KEY);
  },
};

/* ── 错误类型 ── */

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/* ── 内部工具 ── */

let _refreshPromise: Promise<TokenData | null> | null = null;

async function _refreshAccessToken(): Promise<TokenData | null> {
  // 多个并发 401 共享一次 refresh
  if (_refreshPromise) return _refreshPromise;

  const stored = tokenStore.get();
  if (!stored?.refresh) {
    _refreshPromise = Promise.resolve(null);
    return _refreshPromise;
  }

  _refreshPromise = (async () => {
    try {
      const resp = await fetch("/api/auth/refresh/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh: stored.refresh }),
      });
      if (!resp.ok) {
        tokenStore.clear();
        return null;
      }
      const data = await resp.json();
      const updated: TokenData = {
        access: data.access,
        refresh: data.refresh ?? stored.refresh,
        userId: stored.userId,
        displayName: stored.displayName,
      };
      tokenStore.set(updated);
      return updated;
    } catch {
      return null;
    } finally {
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
}

function combineSignals(s1: AbortSignal, s2: AbortSignal): AbortSignal {
  if (s1.aborted || s2.aborted) return AbortSignal.abort("已取消");
  const c = new AbortController();
  s1.addEventListener("abort", () => c.abort(s1.reason), { once: true });
  s2.addEventListener("abort", () => c.abort(s2.reason), { once: true });
  return c.signal;
}

function _shouldInjectAuth(url: string): boolean {
  return !url.startsWith("/api/auth/");
}

/* ── 核心请求 ── */

async function request<T>(
  method: string,
  url: string,
  opts: {
    body?: unknown;
    signal?: AbortSignal;
    timeoutMs?: number;
    skipAuth?: boolean;
  } = {},
): Promise<T> {
  const { body, signal: externalSignal, timeoutMs = DEFAULT_TIMEOUT_MS, skipAuth } = opts;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  const signal = externalSignal
    ? combineSignals(externalSignal, controller.signal)
    : controller.signal;

  const headers: Record<string, string> = {};
  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
  }
  if (!skipAuth && _shouldInjectAuth(url)) {
    const token = tokenStore.get();
    if (token) {
      headers["Authorization"] = `Bearer ${token.access}`;
    }
  }

  const doFetch = () =>
    fetch(url, {
      method,
      signal,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });

  const handleResponse = async (resp: Response): Promise<T> => {
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new ApiError(resp.status, data.error ?? data.detail ?? `请求失败 (${resp.status})`);
    }
    return data as T;
  };

  try {
    let resp = await doFetch();

    // 401 自动 refresh + 重试（仅 1 次）
    if (resp.status === 401 && !skipAuth && _shouldInjectAuth(url)) {
      const refreshed = await _refreshAccessToken();
      if (refreshed) {
        headers["Authorization"] = `Bearer ${refreshed.access}`;
        resp = await doFetch();
      }
    }

    return await handleResponse(resp);
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(0, "请求已取消或超时");
    }
    throw new ApiError(0, err instanceof Error ? err.message : "网络错误");
  } finally {
    clearTimeout(timeoutId);
  }
}

/* ── 公开 API ── */

export const apiClient = {
  get<T>(url: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<T> {
    return request<T>("GET", url, opts);
  },
  post<T>(
    url: string,
    body?: unknown,
    opts?: { signal?: AbortSignal; timeoutMs?: number; skipAuth?: boolean },
  ): Promise<T> {
    return request<T>("POST", url, { ...opts, body });
  },
  patch<T>(
    url: string,
    body?: unknown,
    opts?: { signal?: AbortSignal; timeoutMs?: number },
  ): Promise<T> {
    return request<T>("PATCH", url, { ...opts, body });
  },
  delete<T>(url: string, opts?: { signal?: AbortSignal; timeoutMs?: number }): Promise<T> {
    return request<T>("DELETE", url, opts);
  },
  /** SSE 流式 POST：返回 raw Response，由调用方读取 body stream。 */
  async streamPost(
    url: string,
    body?: unknown,
    opts?: { signal?: AbortSignal; timeoutMs?: number; skipAuth?: boolean },
  ): Promise<Response> {
    const { signal: externalSignal, timeoutMs = DEFAULT_TIMEOUT_MS, skipAuth } = opts ?? {};

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
    const signal = externalSignal
      ? combineSignals(externalSignal, controller.signal)
      : controller.signal;

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      // 不设 Accept: text/event-stream —— DRF @api_view 会在进入视图前做内容协商，
      // 该 Accept 不在默认 renderer 列表内会 406；响应体仍是 SSE，由调用方读 stream。
    };
    if (!skipAuth && _shouldInjectAuth(url)) {
      const token = tokenStore.get();
      if (token) {
        headers.Authorization = `Bearer ${token.access}`;
      }
    }

    const doFetch = () =>
      fetch(url, {
        method: "POST",
        signal,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      });

    try {
      let resp = await doFetch();
      if (resp.status === 401 && !skipAuth && _shouldInjectAuth(url)) {
        const refreshed = await _refreshAccessToken();
        if (refreshed) {
          headers.Authorization = `Bearer ${refreshed.access}`;
          resp = await doFetch();
        }
      }
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        throw new ApiError(resp.status, data.error ?? data.detail ?? `请求失败 (${resp.status})`);
      }
      return resp;
    } catch (err: unknown) {
      if (err instanceof ApiError) throw err;
      if (err instanceof DOMException && err.name === "AbortError") {
        throw new ApiError(0, "请求已取消或超时");
      }
      throw new ApiError(0, err instanceof Error ? err.message : "网络错误");
    } finally {
      clearTimeout(timeoutId);
    }
  },
};
