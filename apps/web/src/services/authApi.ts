/**
 * 认证 API 服务层。
 *
 * 封装 /api/auth/ 下 7 个端点。
 * 登录/注册使用 skipAuth 跳过 token 注入（尚未有 token）。
 *
 * @module services/authApi
 */

import { apiClient } from "./client";

/* ── 类型 ── */

export interface AuthTokens {
  user_id: string;
  email: string;
  display_name: string;
  access: string;
  refresh: string;
}

export interface UserProfile {
  user_id: string;
  email: string;
  display_name: string;
  date_joined: string;
}

/* ── 端点 ── */

export async function login(email: string, password: string): Promise<AuthTokens> {
  return apiClient.post<AuthTokens>(
    "/api/auth/login/",
    { email, password },
    { skipAuth: true },
  );
}

export async function register(
  email: string,
  password: string,
  displayName?: string,
): Promise<AuthTokens> {
  return apiClient.post<AuthTokens>(
    "/api/auth/register/",
    { email, password, display_name: displayName },
    { skipAuth: true },
  );
}

export async function refreshToken(refresh: string): Promise<{ access: string; refresh: string }> {
  return apiClient.post<{ access: string; refresh: string }>(
    "/api/auth/refresh/",
    { refresh },
    { skipAuth: true },
  );
}

export async function getProfile(): Promise<UserProfile> {
  return apiClient.get<UserProfile>("/api/auth/profile/");
}

export async function updateProfile(displayName: string): Promise<{ user_id: string; display_name: string }> {
  return apiClient.patch<{ user_id: string; display_name: string }>(
    "/api/auth/profile/update/",
    { display_name: displayName },
  );
}

export async function changePassword(
  oldPassword: string,
  newPassword: string,
): Promise<{ status: string }> {
  return apiClient.post<{ status: string }>(
    "/api/auth/change-password/",
    { old_password: oldPassword, new_password: newPassword },
  );
}

export function logout(): void {
  // 登出时清除本地 token；后端 logout 端点不存储状态（无 blacklist）
  const { tokenStore } = require("./client");
  tokenStore.clear();
}
