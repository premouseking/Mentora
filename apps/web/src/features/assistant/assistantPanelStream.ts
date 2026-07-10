import type { CourseAgentStreamEvent } from "../../services/courseAgentApi";
import type { ChatMessage, ConversationSnapshot } from "./assistantStorage";
import type { ChatStreamEvent } from "./assistantStream";

/** 按 conversationId 更新单条会话，找不到时原样返回。 */
export function updateConversationById(
  conversations: ConversationSnapshot[],
  conversationId: string,
  updater: (conversation: ConversationSnapshot) => ConversationSnapshot,
): ConversationSnapshot[] {
  const index = conversations.findIndex((conversation) => conversation.id === conversationId);
  if (index === -1) return conversations;

  const nextConversation = updater(conversations[index]);
  const next = [...conversations];
  next[index] = nextConversation;
  return next.sort((left, right) => right.updatedAt - left.updatedAt);
}

/** 将 SSE 事件应用到单条会话（纯函数，便于单测）。 */
export function applyStreamEventToConversation(
  conversation: ConversationSnapshot,
  data: ChatStreamEvent | CourseAgentStreamEvent,
): ConversationSnapshot {
  if (data.type === "session_created") {
    return {
      ...conversation,
      agentSessionId: data.session_id,
      title: data.title || conversation.title,
      updatedAt: Date.now(),
    };
  }

  const nextMessages = [...conversation.messages];
  const lastIndex = nextMessages.length - 1;
  const last = nextMessages[lastIndex];
  if (!last || last.role !== "assistant") {
    return conversation;
  }

  if (data.type === "chunk") {
    nextMessages[lastIndex] = { ...last, content: last.content + data.content };
  } else if (data.type === "status") {
    nextMessages[lastIndex] = {
      ...last,
      statuses: [
        ...(last.statuses ?? []),
        {
          event: data.event,
          message: data.message,
          toolName: data.tool_name,
          success: data.success,
        },
      ],
    };
  } else if (data.type === "citations") {
    nextMessages[lastIndex] = {
      ...last,
      citations: [...(last.citations ?? []), ...data.citations],
    };
  } else if (data.type === "error") {
    nextMessages[lastIndex] = {
      ...last,
      content: last.content || `错误：${data.message}`,
    };
  } else {
    return conversation;
  }

  return {
    ...conversation,
    updatedAt: Date.now(),
    messages: nextMessages,
  };
}

export function updateLastAssistantInConversation(
  conversation: ConversationSnapshot,
  update: (message: ChatMessage) => ChatMessage,
): ConversationSnapshot {
  const nextMessages = [...conversation.messages];
  const last = nextMessages[nextMessages.length - 1];
  if (!last || last.role !== "assistant") return conversation;
  nextMessages[nextMessages.length - 1] = update(last);
  return {
    ...conversation,
    updatedAt: Date.now(),
    messages: nextMessages,
  };
}

export function isWelcomeOnlyConversation(conversation: ConversationSnapshot | undefined): boolean {
  if (!conversation || conversation.agentSessionId) return false;
  return conversation.messages.every((message) => message.role === "assistant");
}
