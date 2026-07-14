/**
 * ResourceReader 辅助：PDF 原文渲染与 ParsedBundle 索引边界。
 *
 * 约定：
 * - PDF 展示始终走 pdf.js + 原文件
 * - ParsedBundle 仅用于 blocks/outline 与检索，不用于 PDF DOM 重建
 */
import type { BundleRaw } from "../../services/documentApi";
import { isPdfMediaType, type SourceDetail } from "../../services/documentApi";
import { buildResourcePdfUrl } from "../../services/resourceApi";
import type { PdfBlock, PdfPageInfo, PdfReaderDocument } from "../../services/resourceTypes";
import type { FlashRect } from "./pdfReaderStateStore";
import type { EvidenceHighlight } from "./types";

/** 高亮层可交互块类型；image 不参与 hover/click，避免 PPT 背景图遮挡文本。 */
export const INTERACTIVE_BLOCK_TYPES = new Set([
  "heading",
  "paragraph",
  "list_item",
  "table",
  "formula",
]);

export function isInteractiveBlockType(type: string): boolean {
  return INTERACTIVE_BLOCK_TYPES.has(type);
}

export function filterInteractiveBlocks(blocks: PdfBlock[]): PdfBlock[] {
  return blocks.filter((block) => isInteractiveBlockType(block.type));
}

/** 按 evidence_unit_id 收集块级闪烁矩形。 */
export function blocksToFlashRects(blocks: PdfBlock[], evidenceId: string): FlashRect[] {
  return blocks
    .filter((block) => block.evidence_unit_id === evidenceId && block.bbox)
    .map((block) => ({
      page: block.page,
      bbox: block.bbox as [number, number, number, number],
    }));
}

function unionFlashBbox(bboxes: Array<[number, number, number, number]>): [number, number, number, number] {
  return [
    Math.min(...bboxes.map((bbox) => bbox[0])),
    Math.min(...bboxes.map((bbox) => bbox[1])),
    Math.max(...bboxes.map((bbox) => bbox[2])),
    Math.max(...bboxes.map((bbox) => bbox[3])),
  ];
}

/** 同页多块 rect 合并为外接矩形，避免句级碎片闪烁。 */
export function mergeFlashRects(rects: FlashRect[]): FlashRect[] {
  if (rects.length <= 1) return rects;

  const byPage = new Map<number, FlashRect[]>();
  for (const rect of rects) {
    const group = byPage.get(rect.page) ?? [];
    group.push(rect);
    byPage.set(rect.page, group);
  }

  const merged: FlashRect[] = [];
  for (const [page, pageRects] of byPage) {
    if (pageRects.length === 1) {
      merged.push(pageRects[0]);
      continue;
    }
    merged.push({
      page,
      bbox: unionFlashBbox(pageRects.map((rect) => rect.bbox)),
    });
  }

  return merged.sort((left, right) => left.page - right.page);
}

export type ResolveEvidenceFlashRectsOptions = {
  /** 目标页 blocks 已拉取完成；false 时不回退 EvidenceUnit bbox。 */
  pageBlocksLoaded?: boolean;
};

/**
 * 优先用 PdfBlock 块 bbox 定位 evidence；无匹配块且 blocks 已就绪时回退 EvidenceUnit bbox。
 */
export function resolveEvidenceFlashRects(
  highlight: Pick<EvidenceHighlight, "evidenceId" | "pageNumber" | "bbox">,
  blocks: PdfBlock[],
  options?: ResolveEvidenceFlashRectsOptions,
): FlashRect[] {
  const fromBlocks = mergeFlashRects(blocksToFlashRects(blocks, highlight.evidenceId));
  if (fromBlocks.length > 0) return fromBlocks;
  if (options?.pageBlocksLoaded === false) return [];
  if (!highlight.bbox) return [];
  return [{
    page: highlight.pageNumber,
    bbox: [highlight.bbox.x0, highlight.bbox.y0, highlight.bbox.x1, highlight.bbox.y1],
  }];
}

export function isSourceDetailPdf(detail: Pick<SourceDetail, "version">): boolean {
  return isPdfMediaType(detail.version.mediaType, detail.version.originalFilename);
}

function bundleToPages(bundle: BundleRaw | null): PdfPageInfo[] {
  if (!bundle?.pages?.length) return [];
  return bundle.pages.map((page) => ({
    page: page.page_number,
    width: page.page_size?.[0] ?? null,
    height: page.page_size?.[1] ?? null,
  }));
}

function bundleToBlocks(bundle: BundleRaw | null): PdfBlock[] {
  if (!bundle?.pages?.length) return [];
  const blocks: PdfBlock[] = [];
  let flatIndex = 0;
  for (const page of bundle.pages) {
    for (const element of page.elements) {
      let bbox: PdfBlock["bbox"] = null;
      if (element.bbox) {
        bbox = [element.bbox.x0, element.bbox.y0, element.bbox.x1, element.bbox.y1];
      }
      blocks.push({
        idx: `block-${flatIndex}`,
        type: element.type,
        page: page.page_number,
        bbox,
        text: element.text ?? "",
        level: element.heading_level ?? null,
        evidence_unit_id: null,
        children: [],
      });
      flatIndex += 1;
    }
  }
  return blocks;
}

function bundleToOutline(bundle: BundleRaw | null): PdfReaderDocument["outline"] {
  if (!bundle?.pages?.length) return [];
  const outline: PdfReaderDocument["outline"] = [];
  let flatIndex = 0;
  for (const page of bundle.pages) {
    for (const element of page.elements) {
      if (element.type === "heading" && element.text?.trim()) {
        outline.push({
          id: `outline-${page.page_number}-${flatIndex}`,
          title: element.text.trim(),
          page: page.page_number,
          level: element.heading_level ?? 1,
          block_idx: `block-${flatIndex}`,
          children: [],
        });
      }
      flatIndex += 1;
    }
  }
  return outline;
}

/** Reader API 不可用时，从 SourceDetail 构造最小 PdfReaderDocument。 */
export function buildMinimalPdfReaderDoc(
  resourceId: string,
  detail: SourceDetail,
): PdfReaderDocument {
  const title = detail.source.displayTitle || detail.version.originalFilename || "资料预览";
  const filename = detail.version.originalFilename || "";
  return {
    resource: {
      resource_id: resourceId,
      resource_name: title,
      resource_type: "pdf",
      open_method: "pdf",
      pages: detail.bundle?.page_count ?? detail.bundle?.pages.length ?? 0,
      file_size: detail.version.byteSize,
      processing_status: detail.version.processingStatus,
      updated_at: null,
      meta: {
        filename,
        media_type: detail.version.mediaType,
        byte_size: detail.version.byteSize,
        source_id: detail.source.id,
        parser_name: detail.version.parserName,
        parser_version: detail.version.parserVersion,
      },
    },
    pdf_url: buildResourcePdfUrl(resourceId),
    pages: bundleToPages(detail.bundle),
    blocks: bundleToBlocks(detail.bundle),
    outline: bundleToOutline(detail.bundle),
    parsed_bundle_ref: "",
    layout_ref: "",
    source_version_id: resourceId,
  };
}

export const PDF_LOAD_ERROR_MESSAGE =
  "原始 PDF 加载失败，请检查原文件或对象存储配置。解析索引仍可用于检索，但无法预览原文版式。";
