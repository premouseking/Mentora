/**
 * 文档查询 API 服务层。
 *
 * 约定：
 * - 资料列表按 DEV_OWNER_ID 过滤
 * - 详情接口返回 ParsedBundle 正文供文档阅读页渲染
 */
import { apiClient } from "./client";

const API = "/api";

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
  const url = qs ? `/api/library/sources/?${qs}` : `/api/library/sources/`;
  const data = await apiClient.get<{ items?: SourceItem[] }>(url);
  return data.items ?? [];
}

export async function fetchSourceDetail(sourceVersionId: string): Promise<SourceDetail> {
  return apiClient.get<SourceDetail>(`/api/library/sources/${encodeURIComponent(sourceVersionId)}/`);
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

export async function setSessionSources(
  sessionId: string,
  sourceVersionIds: string[],
): Promise<void> {
  await apiClient.post(
    `/api/courses/sessions/${encodeURIComponent(sessionId)}/sources/`,
    { source_version_ids: sourceVersionIds },
  );
}

/** @deprecated 使用 setSessionSources */
export const setCourseSources = setSessionSources;

/* ── 重新解析 ── */

export async function reparseSource(sourceId: string): Promise<void> {
  const res = await fetch(`${API}/library/sources/${encodeURIComponent(sourceId)}/reparse/`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("重新解析失败");
}

/* ── 文件夹 ── */

export interface FolderItem {
  id: string;
  name: string;
}

export async function fetchFolders(): Promise<FolderItem[]> {
  const res = await fetch(`${API}/library/folders/`);
  if (!res.ok) throw new Error(`获取文件夹列表失败: ${res.status}`);
  const data = await res.json();
  return data.items ?? data ?? [];
}

export async function createFolder(name: string): Promise<FolderItem> {
  const res = await fetch(`${API}/library/folders/create/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error("创建文件夹失败");
  return res.json();
}

/** 预留：重命名文件夹。UI 实现后接入。
 *  `PATCH /api/library/folders/{folderId}/` — body: { name: string }
 *  后端已就绪，前端待设计双击编辑或右键菜单触发。
 */
export async function renameFolder(folderId: string, name: string): Promise<void> {
  const res = await fetch(`${API}/library/folders/${encodeURIComponent(folderId)}/`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error("重命名文件夹失败");
}

export async function deleteFolder(folderId: string): Promise<void> {
  const res = await fetch(`${API}/library/folders/${encodeURIComponent(folderId)}/delete/`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("删除文件夹失败");
}

/* ── 标签 ── */

export async function fetchTags(): Promise<string[]> {
  const res = await fetch(`${API}/library/tags/`);
  if (!res.ok) throw new Error(`获取标签列表失败: ${res.status}`);
  const data = await res.json();
  return data.tags ?? data.items ?? [];
}

/** 预留：更新资料标签。UI 实现后接入。
 *  `POST /api/library/sources/{sourceId}/tags/` — body: { tags: string[] }
 *  后端已就绪，前端待设计标签编辑器（添加/删除/建议）后对接。
 */
export async function updateSourceTags(sourceId: string, tags: string[]): Promise<void> {
  const res = await fetch(`${API}/library/sources/${encodeURIComponent(sourceId)}/tags/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tags }),
  });
  if (!res.ok) throw new Error("更新标签失败");
}

/* ── 移动 ── */

export async function moveSource(sourceId: string, folderId: string | null): Promise<void> {
  const res = await fetch(`${API}/library/sources/${encodeURIComponent(sourceId)}/move/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ folder_id: folderId }),
  });
  if (!res.ok) throw new Error("移动资料失败");
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
  const res = await fetch(`${API}/courses/${encodeURIComponent(courseId)}/files/`);
  if (!res.ok) throw new Error(`获取文件树失败: ${res.status}`);
  return res.json();
}

export async function fetchCoursePhases(courseId: string): Promise<CoursePhasesResponse> {
  const res = await fetch(`${API}/courses/${encodeURIComponent(courseId)}/phases/`);
  if (!res.ok) throw new Error(`获取阶段列表失败: ${res.status}`);
  return res.json();
}
