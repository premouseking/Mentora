import { describe, expect, it } from "vitest";

import { buildReaderPageWindow, READER_PAGE_WINDOW_RADIUS } from "./readerPageWindow";

describe("buildReaderPageWindow", () => {
  it("returns centered window with radius", () => {
    expect(buildReaderPageWindow(5, 10, READER_PAGE_WINDOW_RADIUS)).toEqual([3, 4, 5, 6, 7]);
  });

  it("clamps to document bounds", () => {
    expect(buildReaderPageWindow(1, 3, 2)).toEqual([1, 2, 3]);
    expect(buildReaderPageWindow(3, 3, 2)).toEqual([1, 2, 3]);
  });
});
