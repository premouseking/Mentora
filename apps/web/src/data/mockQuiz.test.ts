import { describe, expect, it } from "vitest";
import { isMockQuizEnabled } from "./mockQuiz";

describe("isMockQuizEnabled", () => {
  it("keeps mock quiz disabled unless explicitly enabled", () => {
    expect(isMockQuizEnabled({})).toBe(false);
    expect(isMockQuizEnabled({ VITE_USE_MOCK_QUIZ: "false" })).toBe(false);
    expect(isMockQuizEnabled({ VITE_USE_MOCK_QUIZ: "true" })).toBe(true);
  });
});
