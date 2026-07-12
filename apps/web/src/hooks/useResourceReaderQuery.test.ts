import { describe, expect, it } from "vitest";

import { mergeReaderBlocks } from "./useResourceReaderQuery";
import type { PdfBlock } from "../services/resourceTypes";

function block(idx: string, page: number): PdfBlock {
  return {
    idx,
    type: "text",
    page,
    bbox: null,
    text: idx,
    level: null,
    evidence_unit_id: null,
    children: [],
  };
}

describe("mergeReaderBlocks", () => {
  it("merges by idx and sorts by page", () => {
    const merged = mergeReaderBlocks([block("a", 2)], [block("b", 1)]);
    expect(merged.map((item) => item.idx)).toEqual(["b", "a"]);
  });

  it("limits overlay blocks to a page window around center", () => {
    const existing = [block("p1", 1), block("p10", 10)];
    const incoming = [block("p5", 5), block("p6", 6)];
    const merged = mergeReaderBlocks(existing, incoming, 5, 1);
    expect(merged.map((item) => item.page)).toEqual([5, 6]);
  });
});
