/** 网页端崩溃诊断：记录最近错误供 ErrorBoundary 展示与排查。 */

const STORAGE_KEY = "mentora:last-crash";

export interface CrashRecord {
  message: string;
  stack?: string;
  source: "error" | "unhandledrejection" | "react";
  at: string;
}

export function recordCrash(record: CrashRecord): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(record));
  } catch {
    // sessionStorage 不可用时忽略
  }
}

export function readLastCrash(): CrashRecord | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as CrashRecord;
  } catch {
    return null;
  }
}

export function clearLastCrash(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function installGlobalCrashHandlers(): void {
  window.addEventListener("error", (event) => {
    recordCrash({
      message: event.message || "未知错误",
      stack: event.error instanceof Error ? event.error.stack : undefined,
      source: "error",
      at: new Date().toISOString(),
    });
  });

  window.addEventListener("unhandledrejection", (event) => {
    const reason = event.reason;
    recordCrash({
      message: reason instanceof Error ? reason.message : String(reason),
      stack: reason instanceof Error ? reason.stack : undefined,
      source: "unhandledrejection",
      at: new Date().toISOString(),
    });
  });
}
