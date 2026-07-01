import type { ChatCitation } from "./assistantTypes";

/**
 * /api/chat/stream/ SSE 事件契约（对齐 LightRead llmChatStream wire 格式）。
 *
 * 基础帧：content / reasoning / done / error（及 code!==0 错误包）
 * Mentora 扩展：status（工具与思考态）、citations（资料引用）
 *
 * @see d:/AllCode/LightRead/src/api/llm.ts
 * @see d:/AllCode/WebScraperPlugin-private/sidepanel/aichat/lib/llmApi.ts
 */

export type ChatStreamEvent =
  | { type: "content"; content: string }
  | { type: "reasoning"; content: string }
  | {
      type: "status";
      status_key?: string;
      event: string;
      message: string;
      tool_name?: string;
      success?: boolean;
      phase?: "thinking" | "tool";
      state?: "running" | "completed" | "failed";
      preview?: string;
      arguments?: Record<string, unknown>;
    }
  | { type: "citations"; tool_name?: string; citations: ChatCitation[] }
  | { type: "error"; message: string }
  | { type: "done" };

type WireFrame = Record<string, unknown>;

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

/** 解析单行 `data:` JSON 为 SSE 事件；无法识别或空帧返回 null。 */
export function parseStreamDataLine(raw: unknown): ChatStreamEvent | null {
  if (!raw || typeof raw !== "object") return null;

  const frame = raw as WireFrame;

  if (frame.code !== undefined && frame.code !== 0) {
    let message = asString(frame.msg) || asString(frame.message) || "未知错误";
    const upstream = asRecord(frame.upstream_error);
    if (upstream) {
      const nested = asRecord(upstream.error) ?? upstream;
      message = asString(nested.message) || asString(nested.code) || message;
    }
    return { type: "error", message };
  }

  const wireType = asString(frame.type);

  if (wireType === "done") return { type: "done" };

  if (wireType === "error") {
    return {
      type: "error",
      message: asString(frame.message) || asString(frame.msg) || "未知错误",
    };
  }

  if (wireType === "content") {
    const content = asString(frame.content);
    return content ? { type: "content", content } : null;
  }

  if (wireType === "reasoning") {
    return { type: "reasoning", content: asString(frame.content) };
  }

  if (wireType === "status" && asString(frame.event) && asString(frame.message)) {
    return {
      type: "status",
      status_key: asString(frame.status_key) || undefined,
      event: asString(frame.event),
      message: asString(frame.message),
      tool_name: asString(frame.tool_name) || undefined,
      success: typeof frame.success === "boolean" ? frame.success : undefined,
      phase: frame.phase === "thinking" || frame.phase === "tool" ? frame.phase : undefined,
      state:
        frame.state === "running" || frame.state === "completed" || frame.state === "failed"
          ? frame.state
          : undefined,
      preview: asString(frame.preview) || undefined,
      arguments: asRecord(frame.arguments),
      ...(Array.isArray(frame.citations) ? {} : {}),
    };
  }

  if (wireType === "citations" && Array.isArray(frame.citations)) {
    return {
      type: "citations",
      tool_name: asString(frame.tool_name) || undefined,
      citations: frame.citations as ChatCitation[],
    };
  }

  return null;
}

export function parseAssistantStreamChunk(chunk: string, previousBuffer = "") {
  const combined = `${previousBuffer}${chunk}`;
  const lines = combined.split(/\r?\n/);
  const buffer = lines.pop() ?? "";
  const events: ChatStreamEvent[] = [];

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || !trimmed.startsWith("data: ")) continue;
    const payload = trimmed.slice(6).trim();
    if (!payload) continue;
    try {
      const event = parseStreamDataLine(JSON.parse(payload) as unknown);
      if (event) events.push(event);
    } catch {
      // 忽略畸形 SSE 行，继续处理后续事件。
    }
  }

  return { events, buffer };
}

/** 流结束时冲刷可能残留的半行 `data:` JSON。 */
export function flushAssistantStreamBuffer(buffer: string): ChatStreamEvent[] {
  const trimmed = buffer.trim();
  if (!trimmed.startsWith("data: ")) return [];
  const payload = trimmed.slice(6).trim();
  if (!payload) return [];
  try {
    const event = parseStreamDataLine(JSON.parse(payload) as unknown);
    return event ? [event] : [];
  } catch {
    return [];
  }
}
