import { describe, expect, it } from "vitest";

import {
  buildLibraryReaderPath,
  evidenceHighlightToFlashRect,
  resolveReaderResourceId,
} from "./resourceCompat";

describe("resourceCompat", () => {
  it("resolves resource id from sourceVersionId", () => {
    expect(resolveReaderResourceId({ sourceVersionId: "sv-1" })).toBe("sv-1");
    expect(resolveReaderResourceId({ resourceId: "res-1" })).toBe("res-1");
  });

  it("builds library reader path with returnTo", () => {
    expect(buildLibraryReaderPath("id-1", { returnTo: "/library" })).toBe(
      "/library/read/id-1?returnTo=%2Flibrary",
    );
  });

  it("converts evidence bbox to flash rect", () => {
    const rect = evidenceHighlightToFlashRect(2, { x0: 1, y0: 2, x1: 3, y1: 4 });
    expect(rect).toEqual({ page: 2, bbox: [1, 2, 3, 4] });
  });
});
