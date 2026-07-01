import { describe, expect, it } from "vitest";

import { sanitizeConversationsForStorage, type ConversationSnapshot } from "./assistantStorage";

describe("sanitizeConversationsForStorage", () => {
  it("keeps only the most recent 20 conversations", () => {
    const conversations = Array.from({ length: 25 }, (_, index) => ({
      id: `conv-${index}`,
      title: `对话 ${index}`,
      updatedAt: index,
      messages: [],
    }));

    expect(sanitizeConversationsForStorage(conversations)).toHaveLength(20);
  });

  it("preserves assistant blocks structure", () => {
    const conversations: ConversationSnapshot[] = [
      {
        id: "conv-1",
        title: "测试",
        updatedAt: 1,
        messages: [
          {
            role: "assistant",
            blocks: [
              { type: "text", content: "你好" },
              {
                type: "tool",
                id: "tool:retrieve_evidence",
                toolName: "retrieve_evidence",
                title: "正在检索资料",
                progress: 1,
              },
            ],
          },
        ],
      },
    ];

    expect(sanitizeConversationsForStorage(conversations)).toEqual(conversations);
  });
});
