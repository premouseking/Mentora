/// <reference types="vite/client" />

import type { DesktopApi } from "./lib/desktop";

declare global {
  interface Window {
    mentoraDesktop?: DesktopApi;
  }
}

interface ImportMetaEnv {
  /** 设为 "true" 时跳过所有后端 API 调用，使用 mock 数据直接导航 */
  readonly VITE_SKIP_BACKEND?: string;
}

export {};
