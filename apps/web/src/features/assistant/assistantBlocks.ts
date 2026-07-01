import type { ChatStreamEvent } from "./assistantStream";
import { buildToolBlockTitle, mapStreamStateToProgress } from "./assistantToolDisplay";
import type {
  AssistantBlock,
  AssistantChatMessage,
  AssistantTextBlock,
  AssistantThinkingBlock,
  AssistantToolBlock,
} from "./assistantTypes";
import { TOOL_PROGRESS } from "./assistantTypes";

export function flattenAssistantBlocksContent(blocks: AssistantBlock[] | undefined): string {
  if (!blocks?.length) return "";
  return blocks
    .filter((block): block is AssistantTextBlock => block.type === "text")
    .map((block) => block.content)
    .join("");
}

/** 流式正文：最后一个 block 是 text 则追加，否则新建 text block。 */
export function appendAssistantTextChunk(blocks: AssistantBlock[], chunk: string): AssistantBlock[] {
  if (!chunk) return blocks;
  const list = [...blocks];
  const last = list[list.length - 1];
  if (last?.type === "text") {
    list[list.length - 1] = { ...last, content: last.content + chunk };
    return list;
  }
  return [...list, { type: "text", content: chunk }];
}

/** 流式思考：与插件 onReasoning 一致，追加到最后一个 thinking 块或新建。 */
export function appendAssistantThinkingChunk(blocks: AssistantBlock[], chunk: string): AssistantBlock[] {
  if (!chunk) return blocks;
  const list = blocks.map((block) => (
    block.type === "thinking" && block.status !== "processing"
      ? { ...block, status: "success" as const }
      : block
  ));
  const last = list[list.length - 1];
  if (last?.type === "thinking" && last.status === "processing") {
    list[list.length - 1] = { ...last, content: last.content + chunk };
    return list;
  }
  return [...list, { type: "thinking", content: chunk, status: "processing" }];
}

export function finalizeAssistantThinkingBlocks(blocks: AssistantBlock[]): AssistantBlock[] {
  return blocks.map((block) => (
    block.type === "thinking" && block.status === "processing"
      ? { ...block, status: "success" as const }
      : block
  ));
}

function upsertToolBlock(
  blocks: AssistantBlock[],
  payload: {
    id: string;
    toolName: string;
    progress: number;
    title: string;
    arguments?: Record<string, unknown>;
    preview?: string;
  },
): AssistantBlock[] {
  const list = [...blocks];
  const index = list.findIndex((block) => block.type === "tool" && block.id === payload.id);
  const nextBlock: AssistantToolBlock = {
    type: "tool",
    id: payload.id,
    toolName: payload.toolName,
    title: payload.title,
    progress: payload.progress,
    arguments: payload.arguments,
    preview: payload.preview,
  };
  if (index >= 0) {
    const prev = list[index] as AssistantToolBlock;
    list[index] = {
      ...prev,
      ...nextBlock,
      arguments: payload.arguments ?? prev.arguments,
    };
    return list;
  }
  return [...list, nextBlock];
}

function applyToolStatusEvent(blocks: AssistantBlock[], event: Extract<ChatStreamEvent, { type: "status" }>) {
  const toolName = event.tool_name?.trim() || "unknown";
  const blockId = event.status_key?.trim() || `tool:${toolName}`;
  const progress = mapStreamStateToProgress(event.state, event.success);
  const existing = blocks.find(
    (block): block is AssistantToolBlock => block.type === "tool" && block.id === blockId,
  );
  const mergedArguments = event.arguments ?? existing?.arguments;
  const title = buildToolBlockTitle(toolName, progress, mergedArguments, event.message);
  return upsertToolBlock(blocks, {
    id: blockId,
    toolName,
    progress,
    title,
    arguments: mergedArguments,
    preview: event.preview,
  });
}

export function applyAssistantStreamEvent(
  message: AssistantChatMessage,
  event: ChatStreamEvent,
): AssistantChatMessage {
  if (event.type === "content") {
    let blocks = finalizeAssistantThinkingBlocks(message.blocks);
    blocks = appendAssistantTextChunk(blocks, event.content);
    return { ...message, blocks };
  }

  if (event.type === "reasoning") {
    let blocks = finalizeAssistantThinkingBlocks(
      message.blocks.filter((block) => block.type !== "thinking" || block.status === "processing"),
    );
    blocks = appendAssistantThinkingChunk(blocks, event.content);
    return { ...message, blocks };
  }

  if (event.type === "status") {
    let blocks = finalizeAssistantThinkingBlocks(message.blocks);
    if (event.phase === "thinking" && event.state === "running") {
      const last = blocks[blocks.length - 1];
      if (last?.type !== "thinking" || last.status !== "processing") {
        blocks = [
          ...blocks,
          { type: "thinking", content: event.message || "正在思考…", status: "processing" },
        ];
      }
      return { ...message, blocks };
    }
    if (event.event.includes("tool")) {
      blocks = applyToolStatusEvent(blocks, event);
    }
    return { ...message, blocks };
  }

  if (event.type === "citations") {
    return {
      ...message,
      citations: [...(message.citations ?? []), ...event.citations],
    };
  }

  if (event.type === "error") {
    let blocks = finalizeAssistantThinkingBlocks(message.blocks);
    const fallback = event.message.trim() || "未知错误";
    const last = blocks[blocks.length - 1];
    if (last?.type === "text" && last.content.trim()) {
      return { ...message, blocks };
    }
    blocks = appendAssistantTextChunk(blocks, blocks.length ? `\n\n错误: ${fallback}` : `错误: ${fallback}`);
    return { ...message, blocks };
  }

  return message;
}

export function markRunningToolsCancelled(blocks: AssistantBlock[]): AssistantBlock[] {
  return blocks.map((block) => {
    if (block.type !== "tool") return block;
    if (block.progress === TOOL_PROGRESS.COMPLETED || block.progress === TOOL_PROGRESS.FAILED) {
      return block;
    }
    return {
      ...block,
      progress: TOOL_PROGRESS.CANCELLED,
      title: `${block.title.replace(/^正在/, "已中断")}`,
    };
  });
}

export type { AssistantBlock, AssistantThinkingBlock, AssistantToolBlock };
