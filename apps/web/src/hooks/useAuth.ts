import { useCallback, useEffect, useState } from "react";

import {
  DEV_AUTH_BYPASS_STATUS,
  getDesktopApi,
  isDesktopHost,
  type AuthCredentials,
  type AuthRegisterRequest,
  type AuthStatus,
} from "../lib/desktop";
import * as authApi from "../services/authApi";
import { tokenStore } from "../services/client";

export function useAuth() {
  const [status, setStatus] = useState<AuthStatus>({ state: "signed-out" });
  const [loading, setLoading] = useState(true);
  const desktop = isDesktopHost();

  useEffect(() => {
    const api = getDesktopApi();

    if (api) {
      // Electron IPC：保持原有逻辑
      let active = true;
      void api.auth.getStatus().then((next) => {
        if (active) setStatus(next);
      }).finally(() => {
        if (active) setLoading(false);
      });
      const unsubscribe = api.auth.onChanged((next) => {
        if (active) setStatus(next);
      });
      return () => {
        active = false;
        unsubscribe();
      };
    }

    // 浏览器模式：优先检查 localStorage 中已存储的 token
    const stored = tokenStore.get();
    if (stored) {
      setStatus({
        state: "signed-in",
        accountId: stored.userId,
        displayName: stored.displayName,
      });
    } else if (import.meta.env.DEV) {
      setStatus(DEV_AUTH_BYPASS_STATUS);
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (credentials: AuthCredentials) => {
    const api = getDesktopApi();
    if (api) return api.auth.login(credentials);

    // 浏览器模式：HTTP 登录
    const result = await authApi.login(credentials.email, credentials.password);
    tokenStore.set({
      access: result.access,
      refresh: result.refresh,
      userId: result.user_id,
      displayName: result.display_name,
    });
    const next: AuthStatus = {
      state: "signed-in",
      accountId: result.user_id,
      displayName: result.display_name,
    };
    setStatus(next);
    return next;
  }, []);

  const register = useCallback(async (request: AuthRegisterRequest) => {
    const api = getDesktopApi();
    if (api) return api.auth.register(request);

    // 浏览器模式：HTTP 注册
    const result = await authApi.register(
      request.email,
      request.password,
      request.displayName,
    );
    tokenStore.set({
      access: result.access,
      refresh: result.refresh,
      userId: result.user_id,
      displayName: result.display_name,
    });
    const next: AuthStatus = {
      state: "signed-in",
      accountId: result.user_id,
      displayName: result.display_name,
    };
    setStatus(next);
    return next;
  }, []);

  const logout = useCallback(async () => {
    const api = getDesktopApi();
    if (api) {
      await api.auth.logout();
      return;
    }
    tokenStore.clear();
    setStatus({ state: "signed-out" });
  }, []);

  return {
    status,
    loading,
    desktop,
    login,
    register,
    logout,
  };
}
