/**
 * LightRead-like Resource / Reader API。
 *
 * @module services/resourceApi
 */
import { apiClient, ApiError } from "./client";
import type {
  PdfBlock,
  PdfPageInfo,
  PdfReaderDocument,
  ReaderOutlineItem,
  ResourceItem,
  ResourceMeta,
} from "./resourceTypes";

const API = "/api";

function normalizeMeta(raw: Record<string, unknown> | undefined): ResourceMeta {
  const m = raw ?? {};
  return {
    filename: String(m.filename ?? ""),
    media_type: String(m.media_type ?? m.mediaType ?? ""),
    byte_size: Number(m.byte_size ?? m.byteSize ?? 0),
    source_id: String(m.source_id ?? m.sourceId ?? ""),
    parser_name: String(m.parser_name ?? m.parserName ?? ""),
    parser_version: String(m.parser_version ?? m.parserVersion ?? ""),
  };
}

export function normalizeResourceItem(raw: Record<string, unknown>): ResourceItem {
  return {
    resource_id: String(raw.resource_id ?? raw.resourceId ?? ""),
    resource_name: String(raw.resource_name ?? raw.resourceName ?? ""),
    resource_type: String(raw.resource_type ?? raw.resourceType ?? "file"),
    open_method: String(raw.open_method ?? raw.openMethod ?? "file"),
    pages: Number(raw.pages ?? 0),
    file_size: Number(raw.file_size ?? raw.fileSize ?? 0),
    processing_status: String(raw.processing_status ?? raw.processingStatus ?? ""),
    updated_at: (raw.updated_at ?? raw.updatedAt ?? null) as string | null,
    meta: normalizeMeta(raw.meta as Record<string, unknown> | undefined),
  };
}

function normalizePageInfo(raw: Record<string, unknown>): PdfPageInfo {
  return {
    page: Number(raw.page ?? 0),
    width: raw.width == null ? null : Number(raw.width),
    height: raw.height == null ? null : Number(raw.height),
    thumbnail_url: (raw.thumbnail_url ?? raw.thumbnailUrl ?? null) as string | null,
  };
}

export function normalizePdfBlock(raw: Record<string, unknown>): PdfBlock {
  const bboxRaw = raw.bbox;
  let bbox: PdfBlock["bbox"] = null;
  if (Array.isArray(bboxRaw) && bboxRaw.length >= 4) {
    bbox = [
      Number(bboxRaw[0]),
      Number(bboxRaw[1]),
      Number(bboxRaw[2]),
      Number(bboxRaw[3]),
    ];
  }
  return {
    idx: String(raw.idx ?? ""),
    type: String(raw.type ?? "paragraph"),
    page: Number(raw.page ?? 1),
    bbox,
    text: String(raw.text ?? ""),
    level: raw.level == null ? null : Number(raw.level),
    evidence_unit_id: (raw.evidence_unit_id ?? raw.evidenceUnitId ?? null) as string | null,
    children: Array.isArray(raw.children) ? raw.children.map(String) : [],
  };
}

function normalizeOutline(raw: Record<string, unknown>): ReaderOutlineItem {
  return {
    id: String(raw.id ?? ""),
    title: String(raw.title ?? ""),
    page: Number(raw.page ?? 1),
    level: Number(raw.level ?? 1),
    block_idx: (raw.block_idx ?? raw.blockIdx ?? null) as string | null,
    children: Array.isArray(raw.children)
      ? raw.children.map((c) => normalizeOutline(c as Record<string, unknown>))
      : [],
  };
}

export function normalizeReaderDocument(raw: Record<string, unknown>): PdfReaderDocument {
  return {
    resource: normalizeResourceItem((raw.resource ?? {}) as Record<string, unknown>),
    pdf_url: String(raw.pdf_url ?? raw.pdfUrl ?? ""),
    pages: Array.isArray(raw.pages)
      ? raw.pages.map((p) => normalizePageInfo(p as Record<string, unknown>))
      : [],
    blocks: Array.isArray(raw.blocks)
      ? raw.blocks.map((b) => normalizePdfBlock(b as Record<string, unknown>))
      : [],
    outline: Array.isArray(raw.outline)
      ? raw.outline.map((o) => normalizeOutline(o as Record<string, unknown>))
      : [],
    parsed_bundle_ref: String(raw.parsed_bundle_ref ?? raw.parsedBundleRef ?? ""),
    layout_ref: String(raw.layout_ref ?? raw.layoutRef ?? ""),
    source_version_id: String(raw.source_version_id ?? raw.sourceVersionId ?? ""),
  };
}

export async function fetchResources(): Promise<ResourceItem[]> {
  const data = await apiClient.get<{ items?: Record<string, unknown>[] }>(`${API}/resources/`);
  return (data.items ?? []).map((item: Record<string, unknown>) => normalizeResourceItem(item));
}

export async function fetchResourceInfo(resourceId: string): Promise<ResourceItem> {
  const data = await apiClient.get<Record<string, unknown>>(
    `${API}/resources/${encodeURIComponent(resourceId)}/info/`,
  );
  return normalizeResourceItem(data);
}

export async function fetchReaderMeta(resourceId: string): Promise<PdfReaderDocument> {
  try {
    const data = await apiClient.get<Record<string, unknown>>(
      `${API}/resources/${encodeURIComponent(resourceId)}/reader/meta/`,
    );
    return normalizeReaderDocument(data);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      // 旧版 API 无 meta 端点时回退到完整 reader 契约
      return fetchReaderDocument(resourceId);
    }
    throw error;
  }
}

export async function fetchReaderBlocks(
  resourceId: string,
  pages: number[],
): Promise<PdfBlock[]> {
  const params = new URLSearchParams();
  if (pages.length > 0) params.set("pages", pages.join(","));
  const qs = params.toString();
  try {
    const data = await apiClient.get<{ blocks?: Record<string, unknown>[] }>(
      `${API}/resources/${encodeURIComponent(resourceId)}/reader/blocks/${qs ? `?${qs}` : ""}`,
    );
    return (data.blocks ?? []).map((b) => normalizePdfBlock(b));
  } catch (error) {
    if (!(error instanceof ApiError) || error.status !== 404) throw error;
    const doc = await fetchReaderDocument(resourceId);
    if (pages.length === 0) return doc.blocks;
    const wanted = new Set(pages);
    return doc.blocks.filter((block) => wanted.has(block.page));
  }
}

export async function fetchReaderDocument(resourceId: string): Promise<PdfReaderDocument> {
  const data = await apiClient.get<Record<string, unknown>>(
    `${API}/resources/${encodeURIComponent(resourceId)}/reader/`,
  );
  return normalizeReaderDocument(data);
}

export function buildResourcePdfUrl(resourceId: string): string {
  return `${API}/resources/${resourceId}/pdf/`;
}

export async function fetchPageThumbnails(
  resourceId: string,
  pages?: number[],
): Promise<PdfPageInfo[]> {
  const params = new URLSearchParams();
  if (pages?.length) params.set("pages", pages.join(","));
  const qs = params.toString();
  const url = `${API}/resources/${resourceId}/pages/thumbnail/${qs ? `?${qs}` : ""}`;
  const data = await apiClient.get<{ pages?: Record<string, unknown>[] }>(url);
  return (data.pages ?? []).map((p: Record<string, unknown>) => normalizePageInfo(p));
}
