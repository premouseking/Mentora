import { describe, expect, it } from "vitest";

import {
  isQuizGenerationJob,
  QUIZ_GENERATION_TIMEOUT_MS,
  TASK_QUIZ_DEFAULT_COUNT,
} from "../services/assessmentApi";

describe("assessmentApi", () => {
  it("uses fast-path friendly defaults", () => {
    expect(TASK_QUIZ_DEFAULT_COUNT).toBe(5);
    expect(QUIZ_GENERATION_TIMEOUT_MS).toBeGreaterThanOrEqual(300_000);
  });

  it("detects async generation jobs", () => {
    expect(isQuizGenerationJob({ job_id: "j1", status: "pending", progress: "", progress_pct: 0 })).toBe(true);
    expect(
      isQuizGenerationJob({
        session_id: "s1",
        course_session_id: "c1",
        status: "created",
        total_items: 1,
        correct_count: 0,
        score_pct: 0,
        items: [],
      }),
    ).toBe(false);
  });
});
