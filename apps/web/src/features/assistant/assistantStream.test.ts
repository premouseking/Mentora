import { describe, expect, it } from "vitest";

import {
  flushAssistantStreamBuffer,
  parseAssistantStreamChunk,
  parseStreamDataLine,
} from "./assistantStream";

describe("parseStreamDataLine", () => {
  it("maps code envelope to error", () => {
    expect(parseStreamDataLine({ code: 1, msg: "余额不足" })).toEqual({
      type: "error",
      message: "余额不足",
    });
  });

  it("parses content frames", () => {
    expect(parseStreamDataLine({ type: "content", content: "hi" })).toEqual({
      type: "content",
      content: "hi",
    });
  });

  it("normalizes legacy chunk frames as content", () => {
    expect(parseStreamDataLine({ type: "chunk", content: "hi" })).toEqual({
      type: "content",
      content: "hi",
    });
  });
});

describe("parseAssistantStreamChunk", () => {
  it("parses content events and skips malformed JSON", () => {
    const result = parseAssistantStreamChunk(
      [
        'data: {"type":"content","content":"hello"}',
        'data: {"type":"chunk","content":" world"}',
        "data: not-json",
        'data: {"type":"done"}',
        "",
      ].join("\n"),
    );

    expect(result.events).toEqual([
      { type: "content", content: "hello" },
      { type: "content", content: " world" },
      { type: "done" },
    ]);
    expect(result.buffer).toBe("");
  });

  it("preserves incomplete trailing lines for the next read", () => {
    const first = parseAssistantStreamChunk('data: {"type":"content","content":"hel');
    expect(first.events).toEqual([]);
    expect(first.buffer).toBe('data: {"type":"content","content":"hel');

    const second = parseAssistantStreamChunk('lo"}\n', first.buffer);
    expect(second.events).toEqual([{ type: "content", content: "hello" }]);
    expect(second.buffer).toBe("");
  });
});

describe("flushAssistantStreamBuffer", () => {
  it("parses trailing data line when stream ends without newline", () => {
    const events = flushAssistantStreamBuffer('data: {"type":"done"}');
    expect(events).toEqual([{ type: "done" }]);
  });
});
