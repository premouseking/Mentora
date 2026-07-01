import { apiClient, ApiError } from "../../services/client";
import { applyAssistantStreamEvent, finalizeAssistantThinkingBlocks } from "./assistantBlocks";
import type { AssistantChatMessage } from "./assistantTypes";
import {
  flushAssistantStreamBuffer,
  parseAssistantStreamChunk,
  type ChatStreamEvent,
} from "./assistantStream";

export interface AssistantChatStreamRequest {
  message: string;
  history: Array<{ role: "user" | "assistant"; content: string }>;
  mentions?: unknown[];
  signal?: AbortSignal;
}

function applyEvents(
  assistant: AssistantChatMessage,
  events: ChatStreamEvent[],
  onUpdate: (message: AssistantChatMessage) => void,
): { message: AssistantChatMessage; done: boolean } {
  let current = assistant;
  for (const event of events) {
    if (event.type === "done") {
      current = { ...current, blocks: finalizeAssistantThinkingBlocks(current.blocks) };
      onUpdate(current);
      return { message: current, done: true };
    }
    current = applyAssistantStreamEvent(current, event);
    onUpdate(current);
  }
  return { message: current, done: false };
}

/**
 * 消费 /api/chat/stream/ SSE，按事件顺序更新 assistant blocks。
 * 传输与解析对齐 LightRead llmChatStream / 插件 useSendMessage。
 */
export async function runAssistantChatStream(
  request: AssistantChatStreamRequest,
  onUpdate: (message: AssistantChatMessage) => void,
): Promise<AssistantChatMessage> {
  let resp: Response;
  try {
    resp = await apiClient.streamPost(
      "/api/chat/stream/",
      {
        message: request.message,
        history: request.history,
        mentions: request.mentions,
      },
      { signal: request.signal },
    );
  } catch (err) {
    if (err instanceof ApiError) {
      throw new Error(err.message || `HTTP ${err.status}`);
    }
    throw err;
  }

  if (!resp.body) {
    throw new Error("流式响应无 body");
  }

  let assistant: AssistantChatMessage = { role: "assistant", blocks: [] };
  onUpdate(assistant);

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunkText = decoder.decode(value, { stream: true });
      const parsed = parseAssistantStreamChunk(chunkText, buffer);
      buffer = parsed.buffer;

      const result = applyEvents(assistant, parsed.events, onUpdate);
      assistant = result.message;
      if (result.done) return assistant;
    }

    // 尾包：连接关闭前可能还有未换行结束的 data 行
    const tailEvents = flushAssistantStreamBuffer(buffer);
    const tailResult = applyEvents(assistant, tailEvents, onUpdate);
    assistant = tailResult.message;
    if (tailResult.done) return assistant;

    // LightRead：未收到 type:done 但连接正常关闭 → 视为完成
    assistant = {
      ...assistant,
      blocks: finalizeAssistantThinkingBlocks(assistant.blocks),
    };
    onUpdate(assistant);
    return assistant;
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") {
      assistant = {
        ...assistant,
        blocks: finalizeAssistantThinkingBlocks(assistant.blocks),
      };
      onUpdate(assistant);
      return assistant;
    }
    throw err;
  }
}
