import { useCallback, useEffect, useState } from "react";

import {
  DEV_AUTH_BYPASS_STATUS,
  getDesktopApi,
  isDesktopHost,
  type AuthCredentials,
  type AuthRegisterRequest,
  type AuthStatus,
} from "../lib/desktop";

export function useAuth() {
  const [status, setStatus] = useState<AuthStatus>({ state: "signed-out" });
  const [loading, setLoading] = useState(true);
  const desktop = isDesktopHost();

  useEffect(() => {
    const api = getDesktopApi();
    if (!api) {
      // 浏览器预览无 preload；开发构建直接视为已登录
      if (import.meta.env.DEV) {
        setStatus(DEV_AUTH_BYPASS_STATUS);
      }
      setLoading(false);
      return;
    }

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
  }, []);

  const login = useCallback(async (credentials: AuthCredentials) => {
    const api = getDesktopApi();
    if (!api) throw new Error("请在 Mentora 桌面客户端中登录");
    return api.auth.login(credentials);
  }, []);

  const register = useCallback(async (request: AuthRegisterRequest) => {
    const api = getDesktopApi();
    if (!api) throw new Error("请在 Mentora 桌面客户端中注册");
    return api.auth.register(request);
  }, []);

  const logout = useCallback(async () => {
    const api = getDesktopApi();
    if (!api) {
      setStatus({ state: "signed-out" });
      return;
    }
    await api.auth.logout();
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
