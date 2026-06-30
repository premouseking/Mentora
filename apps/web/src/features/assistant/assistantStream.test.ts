import { describe, expect, it } from "vitest";

import { parseAssistantStreamChunk } from "./assistantStream";

describe("parseAssistantStreamChunk", () => {
  it("parses valid SSE data lines and skips malformed JSON events", () => {
    const result = parseAssistantStreamChunk(
      [
        'data: {"type":"chunk","content":"hello"}',
        "data: not-json",
        'data: {"type":"done"}',
        "",
      ].join("\n"),
    );

    expect(result.events).toEqual([
      { type: "chunk", content: "hello" },
      { type: "done" },
    ]);
    expect(result.buffer).toBe("");
  });

  it("preserves incomplete trailing lines for the next chunk", () => {
    const first = parseAssistantStreamChunk('data: {"type":"chunk","content":"hel');
    expect(first.events).toEqual([]);
    expect(first.buffer).toBe('data: {"type":"chunk","content":"hel');

    const second = parseAssistantStreamChunk('lo"}\n', first.buffer);
    expect(second.events).toEqual([{ type: "chunk", content: "hello" }]);
    expect(second.buffer).toBe("");
  });
});
