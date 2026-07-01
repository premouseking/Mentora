/**
 * AI 助手消息 blocks 类型（对齐 Lightread 侧栏 ai_answer.blocks 语义）。
 *
 * @see d:/AllCode/WebScraperPlugin-private/sidepanel/aichat/types.ts
 */

export const TOOL_PROGRESS = {
  GENERATING: -5,
  PROCESSING: 1,
  COMPLETED: 2,
  FAILED: -1,
  CANCELLED: -3,
  PARAM_ERROR: -2,
} as const;

export interface AssistantTextBlock {
  type: "text";
  content: string;
}

export interface AssistantThinkingBlock {
  type: "thinking";
  content: string;
  /** processing=流式进行中；success=本段思考结束 */
  status: "processing" | "success" | "failed" | "interrupt";
}

export interface AssistantToolBlock {
  type: "tool";
  id: string;
  toolName: string;
  title: string;
  /** 与插件 function_call_progress 对齐：-5/1 进行中，2 完成，-1 失败 */
  progress: number;
  arguments?: Record<string, unknown>;
  preview?: string;
}

export type AssistantBlock = AssistantTextBlock | AssistantThinkingBlock | AssistantToolBlock;

export interface ChatCitation {
  content_preview: string;
  page_number?: number | null;
  evidence_id?: string;
  source_title?: string;
}

export interface UserChatMessage {
  role: "user";
  content: string;
}

export interface AssistantChatMessage {
  role: "assistant";
  blocks: AssistantBlock[];
  citations?: ChatCitation[];
  saveState?: "idle" | "previewing" | "saved";
  savedDocId?: string;
}

export type ChatMessage = UserChatMessage | AssistantChatMessage;

export function isAssistantMessage(message: ChatMessage): message is AssistantChatMessage {
  return message.role === "assistant";
}

export function isUserMessage(message: ChatMessage): message is UserChatMessage {
  return message.role === "user";
}
