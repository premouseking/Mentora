import { describe, expect, it } from "vitest";

import { mapByteProgress, resolveFetchStageProgress } from "./readerLoadingUtils";

describe("readerLoadingUtils", () => {
  it("maps byte progress into target range", () => {
    expect(mapByteProgress(500, 1000, 10, 90)).toBe(50);
    expect(mapByteProgress(1000, 1000, 10, 90)).toBe(90);
  });

  it("returns stage labels for fetch phases", () => {
    expect(resolveFetchStageProgress("meta").label).toContain("索引");
    expect(resolveFetchStageProgress("blocks").label).toContain("结构");
  });
});
