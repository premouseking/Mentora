/**
 * LightRead-like 资源 / 阅读器契约类型。
 *
 * @module services/resourceTypes
 */

export interface ResourceMeta {
  filename: string;
  media_type: string;
  byte_size: number;
  source_id: string;
  parser_name: string;
  parser_version: string;
}

export interface ResourceItem {
  resource_id: string;
  resource_name: string;
  resource_type: string;
  open_method: string;
  pages: number;
  file_size: number;
  processing_status: string;
  updated_at: string | null;
  meta: ResourceMeta;
}

export interface PdfPageInfo {
  page: number;
  width: number | null;
  height: number | null;
  thumbnail_url?: string | null;
}

export interface PdfBlock {
  idx: string;
  type: string;
  page: number;
  bbox: [number, number, number, number] | null;
  text: string;
  level: number | null;
  evidence_unit_id: string | null;
  children: string[];
}

export interface ReaderOutlineItem {
  id: string;
  title: string;
  page: number;
  level: number;
  block_idx: string | null;
  children: ReaderOutlineItem[];
}

export interface PdfReaderDocument {
  resource: ResourceItem;
  pdf_url: string;
  pages: PdfPageInfo[];
  blocks: PdfBlock[];
  outline: ReaderOutlineItem[];
  parsed_bundle_ref: string;
  layout_ref: string;
  source_version_id: string;
}

/** resource_id 与 source_version_id 兼容期一一对应。 */
export function resourceIdFromSourceVersion(sourceVersionId: string): string {
  return sourceVersionId;
}

export function sourceVersionIdFromResource(resourceId: string): string {
  return resourceId;
}

export function isResourceReady(status: string): boolean {
  return status === "completed";
}

export function isPdfResource(item: Pick<ResourceItem, "resource_type" | "open_method" | "meta">): boolean {
  if (item.open_method === "pdf" || item.resource_type === "pdf") return true;
  const filename = item.meta?.filename ?? "";
  return filename.toLowerCase().endsWith(".pdf");
}
