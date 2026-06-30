/// <reference types="vite/client" />

import type { DesktopApi } from "./lib/desktop";

declare global {
  interface Window {
    mentoraDesktop?: DesktopApi;
  }
}

export {};
