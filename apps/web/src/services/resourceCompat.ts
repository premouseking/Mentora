/** 课程 / evidence 与 Resource API 的兼容适配。 */
import { resourceIdFromSourceVersion, sourceVersionIdFromResource } from "./resourceTypes";

export function resolveReaderResourceId(input: {
  resourceId?: string | null;
  sourceVersionId?: string | null;
}): string {
  const rid = input.resourceId?.trim();
  if (rid) return rid;
  const sv = input.sourceVersionId?.trim();
  if (sv) return resourceIdFromSourceVersion(sv);
  return "";
}

export function buildLibraryReaderPath(
  id: string,
  options?: { returnTo?: string; useResourceRoute?: boolean },
): string {
  const returnTo = options?.returnTo?.trim();
  const qs = returnTo ? `?returnTo=${encodeURIComponent(returnTo)}` : "";
  // 路由仍使用 sourceVersionId 参数名，值等同 resource_id
  return `/library/read/${encodeURIComponent(id)}${qs}`;
}

export function evidenceHighlightToFlashRect(
  pageNumber: number,
  bbox: { x0: number; y0: number; x1: number; y1: number } | null | undefined,
): { page: number; bbox: [number, number, number, number] } | null {
  if (!bbox) return null;
  return {
    page: pageNumber,
    bbox: [bbox.x0, bbox.y0, bbox.x1, bbox.y1],
  };
}

export { sourceVersionIdFromResource, resourceIdFromSourceVersion };
