import type { ChatCitation } from "./assistantStorage";

export type ChatStreamEvent =
  | { type: "chunk"; content: string }
  | { type: "status"; event: string; message: string; tool_name?: string; success?: boolean }
  | { type: "citations"; tool_name?: string; citations: ChatCitation[] }
  | { type: "error"; message: string }
  | { type: "done" };

function isChatStreamEvent(value: unknown): value is ChatStreamEvent {
  if (!value || typeof value !== "object") return false;
  const type = (value as { type?: unknown }).type;
  return type === "chunk" || type === "status" || type === "citations" || type === "error" || type === "done";
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
