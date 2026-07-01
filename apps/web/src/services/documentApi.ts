/**
 * 文档查询 API 服务层。
 *
 * 约定：
 * - 资料列表按 DEV_OWNER_ID 过滤
 * - 详情接口返回 ParsedBundle 正文供文档阅读页渲染
 */
import { apiClient } from "./client";

/* ── shared types ──────────────────────────────────── */

export interface SourceItem {
  id: string;
  displayTitle: string;
  status: string;
  latestVersion: {
    id: string;
    versionNumber: number;
    processingStatus: string;
    byteSize: number;
    originalFilename: string;
  } | null;
}

export interface BoundingBox {
  x0: number; y0: number; x1: number; y1: number;
}

export interface ParsedElementRaw {
  type: string; text: string; bbox: BoundingBox | null; heading_level: number | null;
}

export interface PageRaw {
  page_number: number; elements: ParsedElementRaw[]; warnings: string[];
}

export interface BundleRaw {
  id: string; page_count: number; element_count: number;
  content_hash: string; quality: { score: number | null };
  pages: PageRaw[]; warnings: string[];
  parser: { name: string; version: string };
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
    parserName: string;
    parserVersion: string;
    errorCode: string;
    errorMessage: string;
  };
  bundle: BundleRaw | null;
}

/* ── API functions ─────────────────────────────────── */

export async function fetchSources(courseId?: string): Promise<SourceItem[]> {
  const params = new URLSearchParams();
  if (courseId) params.set("courseId", courseId);
  const qs = params.toString();
  const url = qs ? `/api/library/sources/?${qs}` : "/api/library/sources/";
  const data = await apiClient.get<{ items?: SourceItem[] }>(url);
  return data.items ?? [];
}

export async function fetchSourceDetail(sourceVersionId: string): Promise<SourceDetail> {
  return apiClient.get<SourceDetail>(`/api/library/sources/${sourceVersionId}/`);
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
  await apiClient.delete(`/api/library/sources/${encodeURIComponent(sourceId)}/delete/`);
}

/* ── 课程资料关联 ── */

export interface CourseSourceItem {
  sourceVersionId: string;
  sourceId: string;
  displayTitle: string;
  originalFilename: string;
  processingStatus: string;
  addedAt: string;
}

export async function getCourseSources(courseId: string): Promise<CourseSourceItem[]> {
  const data = await apiClient.get<{ items?: CourseSourceItem[] }>(
    `/api/courses/sessions/${encodeURIComponent(courseId)}/sources/`,
  );
  return data.items ?? [];
}

export async function setCourseSources(
  courseId: string,
  sourceVersionIds: string[],
): Promise<void> {
  await apiClient.post(
    `/api/courses/sessions/${encodeURIComponent(courseId)}/sources/`,
    { source_version_ids: sourceVersionIds },
  );
}

/* ── 重新解析 ── */

export async function reparseSource(sourceId: string): Promise<void> {
  await apiClient.post(`/api/library/sources/${encodeURIComponent(sourceId)}/reparse/`);
}

/* ── 文件夹 ── */

export interface FolderItem {
  id: string;
  name: string;
}

export async function fetchFolders(): Promise<FolderItem[]> {
  const data = await apiClient.get<{ items?: FolderItem[] } | FolderItem[]>("/api/library/folders/");
  if (Array.isArray(data)) return data;
  return data.items ?? [];
}

export async function createFolder(name: string): Promise<FolderItem> {
  return apiClient.post<FolderItem>("/api/library/folders/create/", { name });
}

/** 预留：重命名文件夹。UI 实现后接入。
 *  `PATCH /api/library/folders/{folderId}/` — body: { name: string }
 *  后端已就绪，前端待设计双击编辑或右键菜单触发。
 */
export async function renameFolder(folderId: string, name: string): Promise<void> {
  await apiClient.patch(`/api/library/folders/${encodeURIComponent(folderId)}/`, { name });
}

export async function deleteFolder(folderId: string): Promise<void> {
  await apiClient.delete(`/api/library/folders/${encodeURIComponent(folderId)}/delete/`);
}

/* ── 标签 ── */

export async function fetchTags(): Promise<string[]> {
  const data = await apiClient.get<{ tags: string[] }>("/api/library/tags/");
  return data.tags ?? [];
}

/** 预留：更新资料标签。UI 实现后接入。
 *  `POST /api/library/sources/{sourceId}/tags/` — body: { tags: string[] }
 *  后端已就绪，前端待设计标签编辑器（添加/删除/建议）后对接。
 */
export async function updateSourceTags(sourceId: string, tags: string[]): Promise<void> {
  await apiClient.post(`/api/library/sources/${encodeURIComponent(sourceId)}/tags/`, { tags });
}

/* ── 移动 ── */

export async function moveSource(sourceId: string, folderId: string | null): Promise<void> {
  await apiClient.post(`/api/library/sources/${encodeURIComponent(sourceId)}/move/`, {
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
  return apiClient.get<{ tree: TreeNode[] }>(
    `/api/courses/${encodeURIComponent(courseId)}/files/`,
  );
}

export async function fetchSessionPhases(sessionId: string): Promise<CoursePhasesResponse> {
  return apiClient.get<CoursePhasesResponse>(
    `/api/courses/sessions/${encodeURIComponent(sessionId)}/phases/`,
  );
}

export async function fetchCoursePhases(courseId: string): Promise<CoursePhasesResponse> {
  return apiClient.get<CoursePhasesResponse>(
    `/api/courses/${encodeURIComponent(courseId)}/phases/`,
  );
}
