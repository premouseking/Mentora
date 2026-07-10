export interface ChatCitation {
  content?: string;
  content_preview: string;
  page_number?: number | null;
  source_title?: string;
}

export interface ChatStatus {
  event: string;
  message: string;
  toolName?: string;
  success?: boolean;
}

export interface AssistantAttachment {
  id: string;
  name: string;
  kind: "image" | "file";
  mimeType: string;
  size: number;
  dataUrl?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  statuses?: ChatStatus[];
  citations?: ChatCitation[];
  attachments?: AssistantAttachment[];
}

export interface ConversationSnapshot {
  id: string;
  title: string;
  updatedAt: number;
  messages: ChatMessage[];
  agentSessionId?: string | null;
}

export function sanitizeConversationsForStorage(conversations: ConversationSnapshot[]): ConversationSnapshot[] {
  return conversations.slice(0, 20).map((conversation) => ({
    ...conversation,
    messages: conversation.messages.map((message) => ({
      ...message,
      attachments: message.attachments?.map(({ dataUrl: _dataUrl, ...attachment }) => attachment),
    })),
  }));
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
