import { describe, expect, it } from "vitest";

import type { SourceDetail } from "../../services/documentApi";
import type { PdfBlock } from "../../services/resourceTypes";
import {
  buildMinimalPdfReaderDoc,
  blocksToFlashRects,
  filterInteractiveBlocks,
  isInteractiveBlockType,
  isSourceDetailPdf,
  PDF_LOAD_ERROR_MESSAGE,
  resolveEvidenceFlashRects,
} from "./resourceReaderUtils";

function sampleDetail(overrides: Partial<SourceDetail> = {}): SourceDetail {
  return {
    source: { id: "src-1", displayTitle: "PPT 课件", status: "active" },
    version: {
      id: "sv-1",
      versionNumber: 1,
      processingStatus: "completed",
      byteSize: 1024,
      originalFilename: "slides.pdf",
      mediaType: "application/pdf",
      objectKey: "uploads/x/slides.pdf",
      parserName: "pymupdf",
      parserVersion: "1.0",
      errorCode: "",
      errorMessage: "",
    },
    bundle: {
      id: "bundle-1",
      source_version_id: "sv-1",
      content_hash: "abc",
      page_count: 1,
      element_count: 3,
      pages: [
        {
          page_number: 1,
          page_size: [960, 540] as [number, number],
          elements: [
            { type: "image", text: "", heading_level: null, bbox: { x0: 0, y0: 0, x1: 960, y1: 540 } },
            { type: "paragraph", text: "标题文字", heading_level: null, bbox: { x0: 100, y0: 400, x1: 300, y1: 420 } },
            { type: "heading", text: "第一章", heading_level: 1, bbox: { x0: 100, y0: 450, x1: 200, y1: 470 } },
          ],
          warnings: [],
        },
      ],
      warnings: [],
      quality: { score: 0.9 },
      parser: { name: "pymupdf", version: "1.0" },
    },
    ...overrides,
  };
}

describe("resourceReaderUtils", () => {
  it("detects PDF from source detail", () => {
    expect(isSourceDetailPdf(sampleDetail())).toBe(true);
    expect(
      isSourceDetailPdf(
        sampleDetail({
          version: {
            ...sampleDetail().version,
            mediaType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            originalFilename: "doc.docx",
          },
        }),
      ),
    ).toBe(false);
  });

  it("builds minimal pdf reader doc with blocks and pdf url", () => {
    const doc = buildMinimalPdfReaderDoc("sv-1", sampleDetail());
    expect(doc.resource.open_method).toBe("pdf");
    expect(doc.pdf_url).toContain("/api/resources/sv-1/pdf/");
    expect(doc.pages[0].width).toBe(960);
    expect(doc.blocks).toHaveLength(3);
    expect(doc.outline[0].title).toBe("第一章");
  });

  it("filters image blocks from interactive overlay", () => {
    const blocks: PdfBlock[] = [
      { idx: "0", type: "image", page: 1, bbox: [0, 0, 1, 1], text: "", level: null, evidence_unit_id: null, children: [] },
      { idx: "1", type: "paragraph", page: 1, bbox: [1, 2, 3, 4], text: "x", level: null, evidence_unit_id: null, children: [] },
    ];
    expect(isInteractiveBlockType("image")).toBe(false);
    expect(isInteractiveBlockType("paragraph")).toBe(true);
    expect(filterInteractiveBlocks(blocks)).toHaveLength(1);
    expect(filterInteractiveBlocks(blocks)[0].type).toBe("paragraph");
  });

  it("exposes pdf load error message", () => {
    expect(PDF_LOAD_ERROR_MESSAGE).toContain("原始 PDF 加载失败");
  });

  it("maps evidence id to multiple block flash rects", () => {
    const blocks: PdfBlock[] = [
      {
        idx: "block-0",
        type: "heading",
        page: 2,
        bbox: [10, 20, 30, 40],
        text: "标题",
        level: 1,
        evidence_unit_id: "ev-1",
        children: [],
      },
      {
        idx: "block-1",
        type: "paragraph",
        page: 2,
        bbox: [10, 50, 90, 70],
        text: "正文",
        level: null,
        evidence_unit_id: "ev-1",
        children: [],
      },
      {
        idx: "block-2",
        type: "paragraph",
        page: 2,
        bbox: [1, 2, 3, 4],
        text: "其他",
        level: null,
        evidence_unit_id: "ev-2",
        children: [],
      },
    ];

    expect(blocksToFlashRects(blocks, "ev-1")).toEqual([
      { page: 2, bbox: [10, 20, 30, 40] },
      { page: 2, bbox: [10, 50, 90, 70] },
    ]);
  });

  it("falls back to evidence bbox when no matching blocks", () => {
    const rects = resolveEvidenceFlashRects(
      {
        evidenceId: "ev-missing",
        pageNumber: 3,
        bbox: { x0: 1, y0: 2, x1: 3, y1: 4 },
      },
      [],
      { pageBlocksLoaded: true },
    );
    expect(rects).toEqual([{ page: 3, bbox: [1, 2, 3, 4] }]);
  });

  it("waits for blocks before falling back to evidence bbox", () => {
    const rects = resolveEvidenceFlashRects(
      {
        evidenceId: "ev-missing",
        pageNumber: 3,
        bbox: { x0: 1, y0: 2, x1: 3, y1: 4 },
      },
      [],
      { pageBlocksLoaded: false },
    );
    expect(rects).toEqual([]);
  });

  it("merges same-page block rects into one flash rect", () => {
    const blocks: PdfBlock[] = [
      {
        idx: "block-0",
        type: "paragraph",
        page: 2,
        bbox: [10, 50, 90, 70],
        text: "第一句",
        level: null,
        evidence_unit_id: "ev-1",
        children: [],
      },
      {
        idx: "block-1",
        type: "paragraph",
        page: 2,
        bbox: [10, 20, 90, 40],
        text: "第二句",
        level: null,
        evidence_unit_id: "ev-1",
        children: [],
      },
    ];

    const rects = resolveEvidenceFlashRects(
      { evidenceId: "ev-1", pageNumber: 2, bbox: null },
      blocks,
      { pageBlocksLoaded: true },
    );
    expect(rects).toEqual([{ page: 2, bbox: [10, 20, 90, 70] }]);
  });
});
