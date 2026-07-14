import { describe, expect, it } from "vitest";

import { shouldCreateFreshCourseSession } from "./courseCreationStorage";

describe("courseCreationStorage", () => {
  it("creates fresh session when no session id exists", () => {
    expect(shouldCreateFreshCourseSession(null, "", "计算机组成原理")).toBe(true);
  });

  it("creates fresh session when stored goal differs from next goal", () => {
    expect(
      shouldCreateFreshCourseSession("session-1", "毛概", "计算机组成原理"),
    ).toBe(true);
  });

  it("reuses session when stored goal matches next goal", () => {
    expect(
      shouldCreateFreshCourseSession("session-1", "计算机组成原理", "计算机组成原理"),
    ).toBe(false);
  });

  it("reuses session when stored goal marker is missing", () => {
    expect(shouldCreateFreshCourseSession("session-1", "", "计算机组成原理")).toBe(false);
  });
});
