import { flattenAssistantBlocksContent } from "./assistantBlocks";
import type { ChatMessage } from "./assistantTypes";
import { isAssistantMessage } from "./assistantTypes";

export type { ChatMessage, ChatCitation, UserChatMessage, AssistantChatMessage } from "./assistantTypes";

export interface ConversationSnapshot {
  id: string;
  title: string;
  updatedAt: number;
  messages: ChatMessage[];
}

export function sanitizeConversationsForStorage(conversations: ConversationSnapshot[]): ConversationSnapshot[] {
  return conversations.slice(0, 20);
}

export function loadStoredConversations(storage: Storage, key: string): ConversationSnapshot[] {
  try {
    const raw = storage.getItem(key);
    const parsed = raw ? JSON.parse(raw) : null;
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((item): item is ConversationSnapshot => {
      return Boolean(item?.id && Array.isArray(item.messages));
    });
  } catch {
    return [];
  }
}

export function saveStoredConversations(
  storage: Storage,
  key: string,
  conversations: ConversationSnapshot[],
): boolean {
  try {
    storage.setItem(key, JSON.stringify(sanitizeConversationsForStorage(conversations)));
    return true;
  } catch {
    return false;
  }
}

export function getAssistantMessagePlainText(message: ChatMessage): string {
  if (!isAssistantMessage(message)) return message.content;
  return flattenAssistantBlocksContent(message.blocks);
}
