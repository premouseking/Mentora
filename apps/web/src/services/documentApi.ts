/**
 * 文档查询 API 服务层。
 *
 * 约定：
 * - 资料归属由后端根据 JWT 用户确定
 * - 详情接口返回 ParsedBundle 正文供文档阅读页渲染
 */
import {
  normalizeParsedBundle,
  type BoundingBox,
  type BundleRaw,
  type PageRaw,
  type ParsedElementRaw,
  type ParsedBundle,
} from "./parsedBundleContract";
import { apiClient } from "./client";

const API = "/api";

/* ── shared types ──────────────────────────────────── */

export type {
  BoundingBox,
  BundleRaw,
  PageRaw,
  ParsedBundle,
  ParsedElementRaw,
};

export interface SourceItem {
  id: string;
  displayTitle: string;
  status: string;
  tags?: string[];
  folderId?: string | null;
  updatedAt?: string | null;
  latestVersion: {
    id: string;
    versionNumber: number;
    processingStatus: string;
    byteSize: number;
    originalFilename: string;
    mediaType?: string;
  } | null;
}

export interface SourceDetail {
  source: { id: string; displayTitle: string; status: string };
  version: {
    id: string;
    versionNumber: number;
    processingStatus: string;
    byteSize: number;
    originalFilename: string;
    mediaType: string;
    objectKey: string;
    parserName: string;
    parserVersion: string;
    errorCode: string;
    errorMessage: string;
  };
  bundle: BundleRaw | null;
}

/* ── API functions ─────────────────────────────────── */

export async function fetchSources(
  courseId?: string,
  options?: { limit?: number; offset?: number; signal?: AbortSignal; status?: "active" | "archived" },
): Promise<SourceItem[]> {
  const params = new URLSearchParams();
  if (courseId) params.set("courseId", courseId);
  if (options?.limit != null) params.set("limit", String(options.limit));
  if (options?.offset != null) params.set("offset", String(options.offset));
  if (options?.status) params.set("status", options.status);
  const url = `${API}/library/sources/?${params.toString()}`;
  const data = await apiClient.get<{ items?: SourceItem[] }>(url, { signal: options?.signal });
  return data.items ?? [];
}

export function buildLibraryAssetUrl(sourceVersionId: string, artifactRef: string): string {
  const params = new URLSearchParams({ key: artifactRef });
  return `${API}/library/sources/${sourceVersionId}/assets/?${params}`;
}

/** 原始上传文件 URL，供 pdf.js 阅读器加载。 */
export function buildSourceOriginalAssetUrl(sourceVersionId: string): string {
  const params = new URLSearchParams({ kind: "original" });
  return `${API}/library/sources/${sourceVersionId}/assets/?${params}`;
}

export function isPdfMediaType(mediaType: string, filename?: string): boolean {
  if (mediaType === "application/pdf") return true;
  const lower = (filename ?? "").toLowerCase();
  return lower.endsWith(".pdf");
}

export async function fetchSourceDetail(sourceVersionId: string): Promise<SourceDetail> {
  const data = await apiClient.get<SourceDetail>(`${API}/library/sources/${sourceVersionId}/`);
  return {
    ...data,
    bundle: data.bundle ? normalizeParsedBundle(data.bundle) : null,
  };
}

/* ── helpers ───────────────────────────────────────── */

/** 过滤出已完成解析的 Source，返回平铺 FileNode 列表。 */
export function sourcesToFileNodes(items: SourceItem[]): { id: string; name: string; type: "file"; extension: string }[] {
  const completed = items.filter(
    (s) => s.latestVersion?.processingStatus === "completed"
  );
  return completed.map((s) => ({
    id: s.latestVersion!.id,
    name: s.displayTitle || s.latestVersion!.originalFilename || "未命名",
    type: "file" as const,
    extension: ".pdf",
  }));
}

/* ── 删除 ── */

export async function deleteSource(sourceId: string): Promise<void> {
  await apiClient.delete(`${API}/library/sources/${encodeURIComponent(sourceId)}/delete/`);
}

export async function archiveSource(sourceId: string): Promise<void> {
  await apiClient.patch(`${API}/library/sources/${encodeURIComponent(sourceId)}/archive/`, {});
}

export async function unarchiveSource(sourceId: string): Promise<void> {
  await apiClient.patch(`${API}/library/sources/${encodeURIComponent(sourceId)}/unarchive/`, {});
}

export async function archiveCourseSource(
  sessionId: string,
  sourceVersionId: string,
): Promise<void> {
  await apiClient.patch(
    `${API}/courses/sessions/${encodeURIComponent(sessionId)}/sources/${encodeURIComponent(sourceVersionId)}/archive/`,
    {},
  );
}

export async function unarchiveCourseSource(
  sessionId: string,
  sourceVersionId: string,
): Promise<void> {
  await apiClient.patch(
    `${API}/courses/sessions/${encodeURIComponent(sessionId)}/sources/${encodeURIComponent(sourceVersionId)}/unarchive/`,
    {},
  );
}

/* ── 课程资料关联 ── */

export interface CourseSourceItem {
  sourceVersionId: string;
  sourceId: string;
  displayTitle: string;
  originalFilename: string;
  processingStatus: string;
  addedAt: string;
  archivedAt?: string | null;
}

export async function getCourseSources(courseId: string): Promise<CourseSourceItem[]> {
  const data = await apiClient.get<{ items?: CourseSourceItem[] }>(
    `${API}/courses/sessions/${encodeURIComponent(courseId)}/sources/`,
  );
  return data.items ?? [];
}

export async function setCourseSources(
  courseId: string,
  sourceVersionIds: string[],
): Promise<void> {
  await apiClient.post(
    `${API}/courses/sessions/${encodeURIComponent(courseId)}/sources/`,
    { source_version_ids: sourceVersionIds },
  );
}

/* ── 重新解析 ── */

export async function reparseSource(sourceId: string): Promise<void> {
  await apiClient.post(`${API}/library/sources/${encodeURIComponent(sourceId)}/reparse/`);
}

/* ── 文件夹 ── */

export interface FolderItem {
  id: string;
  name: string;
}

export async function fetchFolders(): Promise<FolderItem[]> {
  const data = await apiClient.get<{ items?: FolderItem[] } | FolderItem[]>(`${API}/library/folders/`);
  return Array.isArray(data) ? data : data.items ?? [];
}

export async function createFolder(name: string): Promise<FolderItem> {
  return apiClient.post<FolderItem>(`${API}/library/folders/create/`, { name });
}

/** 预留：重命名文件夹。UI 实现后接入。
 *  `PATCH /api/library/folders/{folderId}/` — body: { name: string }
 *  后端已就绪，前端待设计双击编辑或右键菜单触发。
 */
export async function renameFolder(folderId: string, name: string): Promise<void> {
  await apiClient.patch(`${API}/library/folders/${encodeURIComponent(folderId)}/`, { name });
}

export async function deleteFolder(folderId: string): Promise<void> {
  await apiClient.delete(`${API}/library/folders/${encodeURIComponent(folderId)}/delete/`);
}

/* ── 标签 ── */

export async function fetchTags(): Promise<string[]> {
  const data = await apiClient.get<{ tags?: string[]; items?: string[] }>(`${API}/library/tags/`);
  return data.tags ?? data.items ?? [];
}

/** 预留：更新资料标签。UI 实现后接入。
 *  `POST /api/library/sources/{sourceId}/tags/` — body: { tags: string[] }
 *  后端已就绪，前端待设计标签编辑器（添加/删除/建议）后对接。
 */
export async function updateSourceTags(sourceId: string, tags: string[]): Promise<void> {
  await apiClient.post(`${API}/library/sources/${encodeURIComponent(sourceId)}/tags/`, { tags });
}

/* ── 移动 ── */

export async function moveSource(sourceId: string, folderId: string | null): Promise<void> {
  await apiClient.post(`${API}/library/sources/${encodeURIComponent(sourceId)}/move/`, {
    folder_id: folderId,
  });
}

/* ── 课程文件树 ── */

export interface TreeNode {
  id: string;
  name: string;
  type: "file" | "folder";
  children?: TreeNode[];
  extension?: string;
}

export interface CoursePhasesResponse {
  phases: {
    id: string;
    title: string;
    position: number;
    objective: string;
    estimated_minutes: number;
    units_count: number;
    completed_units: number;
    state: string;
  }[];
  adjustments: { id: string; scope: string; change: string }[];
}

export async function fetchCourseFiles(courseId: string): Promise<{ tree: TreeNode[] }> {
  return apiClient.get<{ tree: TreeNode[] }>(`${API}/courses/${encodeURIComponent(courseId)}/files/`);
}

export async function fetchCoursePhases(courseId: string): Promise<CoursePhasesResponse> {
  return apiClient.get<CoursePhasesResponse>(`${API}/courses/${encodeURIComponent(courseId)}/phases/`);
}
