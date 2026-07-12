import type { ChatCitation } from "./assistantStorage";

export type ChatStreamEvent =
  | { type: "chunk"; content: string }
  | { type: "status"; event: string; message: string; tool_name?: string; success?: boolean }
  | { type: "citations"; tool_name?: string; citations: ChatCitation[] }
  | { type: "session_created"; session_id: string; title?: string; course_id?: string }
  | { type: "error"; message: string }
  | { type: "done" };

function isChatStreamEvent(value: unknown): value is ChatStreamEvent {
  if (!value || typeof value !== "object") return false;
  const type = (value as { type?: unknown }).type;
  return (
    type === "chunk"
    || type === "status"
    || type === "citations"
    || type === "session_created"
    || type === "error"
    || type === "done"
  );
}

export function parseAssistantStreamChunk(chunk: string, previousBuffer = "") {
  const lines = `${previousBuffer}${chunk}`.split(/\r?\n/);
  const buffer = lines.pop() ?? "";
  const events: ChatStreamEvent[] = [];

  for (const line of lines) {
    if (!line.startsWith("data: ")) continue;
    const payload = line.slice(6).trim();
    if (!payload) continue;
    try {
      const parsed = JSON.parse(payload) as unknown;
      if (isChatStreamEvent(parsed)) events.push(parsed);
    } catch {
      // Ignore malformed stream events and keep processing later events.
    }
  }

  return { events, buffer };
}

/** 消费 ReadableStream SSE 响应，统一 buffer 与末尾 flush。 */
export async function consumeAssistantStream(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: ChatStreamEvent) => void,
): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const parsed = parseAssistantStreamChunk(decoder.decode(value, { stream: true }), buffer);
      buffer = parsed.buffer;
      for (const event of parsed.events) {
        onEvent(event);
      }
    }

    if (buffer.trim()) {
      const parsed = parseAssistantStreamChunk("\n", buffer);
      for (const event of parsed.events) {
        onEvent(event);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
