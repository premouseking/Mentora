/** 开发环境阅读器性能诊断。 */

export interface ReaderPerfPayload {
  resourceId?: string;
  [key: string]: unknown;
}

export function logReaderPerf(event: string, payload: ReaderPerfPayload = {}): void {
  if (!import.meta.env.DEV) return;
  console.debug(`[reader] ${event}`, payload);
}
