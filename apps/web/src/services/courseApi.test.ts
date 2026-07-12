import { describe, expect, it, vi, afterEach } from "vitest";

import { generatePlan } from "../services/courseApi";

describe("generatePlan scope options", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends allow_partial_plan when requested", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ title: "测试", phases: [], revision_id: "rev-1" }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await generatePlan("session-1", { allow_partial_plan: true });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/courses/sessions/session-1/plan/",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ allow_partial_plan: true }),
      }),
    );
  });
});
