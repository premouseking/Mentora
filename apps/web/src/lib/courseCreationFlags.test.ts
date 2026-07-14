import { describe, expect, it } from "vitest";

import { skipCourseInquiry } from "./courseCreationFlags";

describe("courseCreationFlags", () => {
  it("defaults skipCourseInquiry to false in test env", () => {
    expect(skipCourseInquiry).toBe(false);
  });
});
