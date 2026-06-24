/**
 * 文档查询 API 服务层。
 *
 * 约定：
 * - 资料列表按 DEV_OWNER_ID 过滤
 * - 详情接口返回 ParsedBundle 正文供文档阅读页渲染
 */
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

export async function fetchSources(): Promise<SourceItem[]> {
  const res = await fetch(`${API}/library/sources/`);
  if (!res.ok) throw new Error(`获取资料列表失败: ${res.status}`);
  const data = await res.json();
  return data.items ?? [];
}

export async function fetchSourceDetail(sourceVersionId: string): Promise<SourceDetail> {
  const res = await fetch(`${API}/library/sources/${sourceVersionId}/`);
  if (!res.ok) throw new Error(`获取资料详情失败: ${res.status}`);
  return res.json();
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
