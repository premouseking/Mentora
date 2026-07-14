import { describe, expect, it } from "vitest";

import { consumeAssistantStream, parseAssistantStreamChunk } from "./assistantStream";
import type { ChatStreamEvent } from "./assistantStream";

function streamFromString(text: string): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      controller.enqueue(encoder.encode(text));
      controller.close();
    },
  });
}

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

  it("normalizes content frames from older chat endpoints", () => {
    const result = parseAssistantStreamChunk(
      'data: {"type":"content","content":"legacy"}\n',
    );

    expect(result.events).toEqual([{ type: "chunk", content: "legacy" }]);
  });

  it("parses session_created events for course agent streams", () => {
    const result = parseAssistantStreamChunk(
      'data: {"type":"session_created","session_id":"abc-123","title":"总结任务"}\n',
    );

    expect(result.events).toEqual([
      {
        type: "session_created",
        session_id: "abc-123",
        title: "总结任务",
      },
    ]);
  });
});

describe("consumeAssistantStream", () => {
  it("flushes the final event when the stream has no trailing newline", async () => {
    const events: ChatStreamEvent[] = [];
    await consumeAssistantStream(
      streamFromString('data: {"type":"chunk","content":"tail"}'),
      (event) => events.push(event),
    );

    expect(events).toEqual([{ type: "chunk", content: "tail" }]);
  });

  it("parses CRLF-delimited SSE lines", async () => {
    const events: ChatStreamEvent[] = [];
    await consumeAssistantStream(
      streamFromString('data: {"type":"done"}\r\n'),
      (event) => events.push(event),
    );

    expect(events).toEqual([{ type: "done" }]);
  });
});
