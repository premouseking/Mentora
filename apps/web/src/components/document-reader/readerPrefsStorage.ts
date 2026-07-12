/** 阅读器 per-resource 偏好：页码、缩放、侧栏收起状态。 */

export interface ReaderPrefs {
  page?: number;
  scale?: number;
  sidebarCollapsed?: boolean;
}

const STORAGE_PREFIX = "mentora:reader:";

function storageKey(resourceId: string): string {
  return `${STORAGE_PREFIX}${resourceId}`;
}

export function readReaderPrefs(resourceId: string | undefined): ReaderPrefs {
  if (!resourceId) return {};
  try {
    const raw = sessionStorage.getItem(storageKey(resourceId));
    if (!raw) return {};
    return JSON.parse(raw) as ReaderPrefs;
  } catch {
    return {};
  }
}

export function writeReaderPrefs(resourceId: string | undefined, patch: ReaderPrefs): void {
  if (!resourceId) return;
  try {
    const current = readReaderPrefs(resourceId);
    sessionStorage.setItem(storageKey(resourceId), JSON.stringify({ ...current, ...patch }));
  } catch {
    // sessionStorage 不可用时忽略
  }
}
