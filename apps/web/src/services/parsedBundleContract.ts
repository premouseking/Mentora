/**
 * ParsedBundle 前后端共享契约。
 *
 * 约定：
 * - bundle 内部字段使用 snake_case，与后端 parsing/schemas.py 一致
 * - 资料列表/详情元数据仍使用 camelCase（见 documentApi.SourceDetail）
 */

export interface BoundingBox {
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface ParsedElement {
  type: string;
  text: string;
  bbox: BoundingBox | null;
  heading_level: number | null;
  confidence?: number | null;
  extra?: Record<string, unknown> | null;
}

export interface ParsedPage {
  page_number: number;
  original_label?: string | null;
  /** PDF 页面尺寸 [width, height]，单位 pt；旧 artifact 可能缺失 */
  page_size?: [number, number] | null;
  elements: ParsedElement[];
  warnings: string[];
}

export interface ParserInfo {
  name: string;
  version: string;
}

export interface QualityInfo {
  score: number | null;
  text_page_ratio?: number | null;
  garbled_ratio?: number | null;
}

/** 与后端 ParsedBundle JSON 对齐 */
export interface ParsedBundle {
  id: string;
  source_version_id?: string;
  page_count: number;
  element_count: number;
  content_hash: string;
  quality: QualityInfo;
  pages: ParsedPage[];
  warnings: string[];
  parser: ParserInfo;
  artifact_ref?: string;
  created_at?: string;
}

/** 解析实验室 preview 接口中的 EvidenceUnit */
export interface EvidenceUnitPreview {
  id: string;
  content: string;
  page_number: number;
  element_indices: number[];
  source_version_id?: string;
  structure_type?: string;
}

export interface ParsingPreviewResult {
  bundle: ParsedBundle;
  evidence_units: EvidenceUnitPreview[];
  elapsed_ms: number;
}

/** 向后兼容别名 */
export type ParsedElementRaw = ParsedElement;
export type PageRaw = ParsedPage;
export type BundleRaw = ParsedBundle;

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function normalizePageSize(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length < 2) return null;
  const width = Number(value[0]);
  const height = Number(value[1]);
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return null;
  }
  return [width, height];
}

function normalizePages(rawPages: unknown): ParsedPage[] {
  if (!Array.isArray(rawPages)) return [];
  return rawPages.map((pageValue) => {
    const page = asRecord(pageValue) ?? {};
    const elementsRaw = Array.isArray(page.elements) ? page.elements : [];
    const elements: ParsedElement[] = elementsRaw.map((elementValue) => {
      const element = asRecord(elementValue) ?? {};
      const bboxValue = element.bbox;
      const bboxRecord = asRecord(bboxValue);
      const bbox = bboxRecord
        ? {
            x0: Number(bboxRecord.x0),
            y0: Number(bboxRecord.y0),
            x1: Number(bboxRecord.x1),
            y1: Number(bboxRecord.y1),
          }
        : null;
      return {
        type: String(element.type ?? "paragraph"),
        text: String(element.text ?? ""),
        bbox,
        heading_level:
          element.heading_level === null || element.heading_level === undefined
            ? null
            : Number(element.heading_level),
        confidence:
          element.confidence === null || element.confidence === undefined
            ? null
            : Number(element.confidence),
        extra: asRecord(element.extra),
      };
    });
    return {
      page_number: Number(page.page_number ?? 0),
      original_label:
        page.original_label === null || page.original_label === undefined
          ? null
          : String(page.original_label),
      page_size: normalizePageSize(page.page_size),
      elements,
      warnings: Array.isArray(page.warnings)
        ? page.warnings.map((item) => String(item))
        : [],
    };
  });
}

/** 归一化后端/旧 artifact 返回的 ParsedBundle，补齐 page_count / element_count。 */
export function normalizeParsedBundle(raw: unknown): ParsedBundle | null {
  const bundle = asRecord(raw);
  if (!bundle) return null;

  const pages = normalizePages(bundle.pages);
  const pageCount =
    typeof bundle.page_count === "number" ? bundle.page_count : pages.length;
  const elementCount =
    typeof bundle.element_count === "number"
      ? bundle.element_count
      : pages.reduce((sum, page) => sum + page.elements.length, 0);

  const qualityRaw = asRecord(bundle.quality) ?? {};
  const parserRaw = asRecord(bundle.parser) ?? {};

  return {
    id: String(bundle.id ?? ""),
    source_version_id: bundle.source_version_id
      ? String(bundle.source_version_id)
      : undefined,
    page_count: pageCount,
    element_count: elementCount,
    content_hash: String(bundle.content_hash ?? ""),
    quality: {
      score:
        qualityRaw.score === null || qualityRaw.score === undefined
          ? null
          : Number(qualityRaw.score),
      text_page_ratio:
        qualityRaw.text_page_ratio === null || qualityRaw.text_page_ratio === undefined
          ? null
          : Number(qualityRaw.text_page_ratio),
      garbled_ratio:
        qualityRaw.garbled_ratio === null || qualityRaw.garbled_ratio === undefined
          ? null
          : Number(qualityRaw.garbled_ratio),
    },
    pages,
    warnings: Array.isArray(bundle.warnings)
      ? bundle.warnings.map((item) => String(item))
      : [],
    parser: {
      name: String(parserRaw.name ?? "unknown"),
      version: String(parserRaw.version ?? ""),
    },
    artifact_ref: bundle.artifact_ref ? String(bundle.artifact_ref) : undefined,
    created_at: bundle.created_at ? String(bundle.created_at) : undefined,
  };
}

export function normalizeParsingPreviewResult(raw: unknown): ParsingPreviewResult | null {
  const payload = asRecord(raw);
  if (!payload) return null;
  const bundle = normalizeParsedBundle(payload.bundle);
  if (!bundle) return null;

  const evidenceRaw = Array.isArray(payload.evidence_units) ? payload.evidence_units : [];
  const evidence_units: EvidenceUnitPreview[] = evidenceRaw.map((item) => {
    const evidence = asRecord(item) ?? {};
    return {
      id: String(evidence.id ?? ""),
      content: String(evidence.content ?? ""),
      page_number: Number(evidence.page_number ?? 0),
      element_indices: Array.isArray(evidence.element_indices)
        ? evidence.element_indices.map((index) => Number(index))
        : [],
      source_version_id: evidence.source_version_id
        ? String(evidence.source_version_id)
        : undefined,
      structure_type: evidence.structure_type
        ? String(evidence.structure_type)
        : undefined,
    };
  });

  return {
    bundle,
    evidence_units,
    elapsed_ms: Number(payload.elapsed_ms ?? 0),
  };
}
