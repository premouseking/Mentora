import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "./client";
import { commitExplanationSave, previewExplanationSave } from "./learningApi";

describe("learningApi explanation save flow", () => {
  afterEach(() => vi.restoreAllMocks());

  it("previews an assistant answer with its course context", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({
      preview_id: "preview-1",
      action: "create",
      target_doc_id: null,
      target_title: "Bayes theorem",
      keywords: ["bayes"],
      overlap_count: 0,
      summary_md: "summary",
      doc_type: "知识点讲解",
    });

    await previewExplanationSave({
      course_id: "course-1",
      user_message: "Explain Bayes theorem",
      assistant_message: "Bayes theorem relates conditional probabilities.",
    });

    expect(post).toHaveBeenCalledWith(
      "/api/learning/explanations/preview/",
      expect.objectContaining({ course_id: "course-1" }),
      { timeoutMs: 60_000 },
    );
  });

  it("commits the selected preview", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({
      doc_id: "doc-1",
      action: "create",
      title: "Bayes theorem",
    });

    await commitExplanationSave("course-1", "preview-1");

    expect(post).toHaveBeenCalledWith("/api/learning/explanations/commit/", {
      course_id: "course-1",
      preview_id: "preview-1",
    });
  });
});
