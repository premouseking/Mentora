import { describe, expect, it } from "vitest";

import type { BundleRaw } from "../../services/documentApi";
import {
  buildHighlightNeedle,
  clampPageNumber,
  extractTocItems,
  findHighlightIndex,
  getNextPageNumber,
  getPageNumbers,
  getPreviousPageNumber,
  headingAnchorId,
  pageAnchorId,
} from "./readerUtils";

const sampleBundle: BundleRaw = {
  id: "bundle-1",
  page_count: 2,
  element_count: 4,
  content_hash: "hash",
  quality: { score: 1 },
  warnings: [],
  parser: { name: "test", version: "1" },
  pages: [
    {
      page_number: 1,
      warnings: [],
      elements: [
        { type: "heading", text: "Cache 基础", bbox: null, heading_level: 2 },
        { type: "paragraph", text: "Cache 位于 CPU 和主存之间。", bbox: null, heading_level: null },
      ],
    },
    {
      page_number: 2,
      warnings: [],
      elements: [
        { type: "heading", text: "映射方式", bbox: null, heading_level: 2 },
        { type: "paragraph", text: "直接映射将主存块映射到固定行。", bbox: null, heading_level: null },
      ],
    },
  ],
};

describe("readerUtils", () => {
  it("builds stable page and heading anchors", () => {
    expect(pageAnchorId(3)).toBe("doc-page-3");
    expect(headingAnchorId(2, 1)).toBe("doc-heading-2-1");
  });

  it("extracts toc items from headings", () => {
    const items = extractTocItems(sampleBundle);
    expect(items).toHaveLength(2);
    expect(items[0]).toMatchObject({
      text: "Cache 基础",
      level: 2,
      pageNumber: 1,
      elementIndex: 0,
    });
    expect(items[1].pageNumber).toBe(2);
  });

  it("navigates page numbers", () => {
    const pages = getPageNumbers(sampleBundle);
    expect(pages).toEqual([1, 2]);
    expect(clampPageNumber(99, pages)).toBe(2);
    expect(getPreviousPageNumber(pages, 2)).toBe(1);
    expect(getNextPageNumber(pages, 1)).toBe(2);
    expect(getNextPageNumber(pages, 2)).toBeNull();
  });

  it("finds highlight needle and partial matches", () => {
    expect(buildHighlightNeedle("  直接映射方式  ")).toBe("直接映射方式");
    expect(findHighlightIndex("这是直接映射方式的说明。", "直接映射方式")).toEqual({
      start: 2,
      length: 6,
    });
    expect(findHighlightIndex("没有匹配", "abc")).toBeNull();
  });
});
