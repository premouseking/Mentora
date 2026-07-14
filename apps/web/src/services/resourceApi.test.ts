import { describe, expect, it } from "vitest";

import { normalizePdfBlock, normalizeReaderDocument, normalizeResourceItem } from "./resourceApi";

describe("resourceApi", () => {
  it("normalizes ResourceItem from snake_case", () => {
    const item = normalizeResourceItem({
      resource_id: "res-1",
      resource_name: "Sample",
      resource_type: "pdf",
      open_method: "pdf",
      pages: 10,
      file_size: 2048,
      processing_status: "completed",
      meta: { filename: "sample.pdf", source_id: "src-1" },
    });
    expect(item.resource_id).toBe("res-1");
    expect(item.meta.source_id).toBe("src-1");
    expect(item.pages).toBe(10);
  });

  it("normalizes PdfBlock bbox array", () => {
    const block = normalizePdfBlock({
      idx: "block-0",
      type: "paragraph",
      page: 1,
      bbox: [10, 20, 100, 200],
      text: "hello",
    });
    expect(block.bbox).toEqual([10, 20, 100, 200]);
  });

  it("normalizes ReaderDocument with outline", () => {
    const doc = normalizeReaderDocument({
      resource: { resource_id: "res-1", resource_name: "Doc" },
      pdf_url: "/api/resources/res-1/pdf/",
      pages: [{ page: 1, width: 595, height: 842 }],
      blocks: [],
      outline: [{ id: "o1", title: "Intro", page: 1, level: 1 }],
      source_version_id: "res-1",
    });
    expect(doc.pdf_url).toContain("/pdf/");
    expect(doc.outline[0].title).toBe("Intro");
    expect(doc.pages[0].width).toBe(595);
  });
});
