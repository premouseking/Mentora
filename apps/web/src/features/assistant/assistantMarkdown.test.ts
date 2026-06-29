import { describe, expect, it } from "vitest";

import { normalizeAssistantMarkdown } from "./assistantMarkdownUtils";

describe("normalizeAssistantMarkdown", () => {
  it("converts bracketed LaTeX delimiters while preserving markdown tables", () => {
    const input = [
      "行内公式：\\(a^2+b^2=c^2\\)",
      "",
      "\\[",
      "E = mc^2",
      "\\]",
      "",
      "| 概念 | 说明 |",
      "| --- | --- |",
      "| Cache | 高速缓存 |",
    ].join("\n");

    expect(normalizeAssistantMarkdown(input)).toBe([
      "行内公式：$a^2+b^2=c^2$",
      "",
      "$$",
      "E = mc^2",
      "$$",
      "",
      "| 概念 | 说明 |",
      "| --- | --- |",
      "| Cache | 高速缓存 |",
    ].join("\n"));
  });

  it("returns an empty string for blank content", () => {
    expect(normalizeAssistantMarkdown(" \n\t ")).toBe("");
    expect(normalizeAssistantMarkdown(undefined)).toBe("");
  });
});
