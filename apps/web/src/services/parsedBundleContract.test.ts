import { describe, expect, it } from "vitest";

import { normalizeParsedBundle, normalizeParsingPreviewResult } from "./parsedBundleContract";

describe("parsedBundleContract", () => {
  it("fills missing page_count and element_count from pages", () => {
    const bundle = normalizeParsedBundle({
      id: "bundle-1",
      content_hash: "a".repeat(64),
      parser: { name: "pymupdf", version: "1.0.0" },
      quality: { score: 0.9 },
      pages: [
        {
          page_number: 1,
          elements: [{ type: "heading", text: "标题", bbox: null, heading_level: 1 }],
          warnings: [],
        },
        {
          page_number: 2,
          elements: [
            { type: "paragraph", text: "正文", bbox: null, heading_level: null },
            { type: "list_item", text: "条目", bbox: null, heading_level: null },
          ],
          warnings: [],
        },
      ],
      warnings: [],
    });

    expect(bundle).not.toBeNull();
    expect(bundle!.page_count).toBe(2);
    expect(bundle!.element_count).toBe(3);
  });

  it("normalizes parsing preview payload", () => {
    const preview = normalizeParsingPreviewResult({
      bundle: {
        id: "bundle-2",
        page_count: 1,
        element_count: 1,
        content_hash: "b".repeat(64),
        quality: { score: 1 },
        parser: { name: "pymupdf", version: "1.0.0" },
        pages: [{
          page_number: 1,
          elements: [{ type: "paragraph", text: "hello", bbox: null, heading_level: null }],
          warnings: [],
        }],
        warnings: [],
      },
      evidence_units: [{
        id: "ev-1",
        content: "hello",
        page_number: 1,
        element_indices: [0],
      }],
      elapsed_ms: 12.5,
    });

    expect(preview?.bundle.page_count).toBe(1);
    expect(preview?.evidence_units).toHaveLength(1);
    expect(preview?.elapsed_ms).toBe(12.5);
  });
});
