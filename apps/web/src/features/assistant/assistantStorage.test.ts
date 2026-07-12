import { describe, expect, it } from "vitest";

import { sanitizeConversationsForStorage, type ConversationSnapshot } from "./assistantStorage";

describe("sanitizeConversationsForStorage", () => {
  it("removes attachment data URLs before persisting conversations", () => {
    const conversations: ConversationSnapshot[] = [
      {
        id: "conv-1",
        title: "图片问题",
        updatedAt: 1,
        messages: [
          {
            role: "user",
            content: "看这张图",
            attachments: [
              {
                id: "att-1",
                name: "chart.png",
                kind: "image",
                mimeType: "image/png",
                size: 1024,
                dataUrl: "data:image/png;base64,large-payload",
              },
            ],
          },
        ],
      },
    ];

    const sanitized = sanitizeConversationsForStorage(conversations);

    expect(sanitized[0].messages[0].attachments?.[0]).toEqual({
      id: "att-1",
      name: "chart.png",
      kind: "image",
      mimeType: "image/png",
      size: 1024,
    });
    expect(conversations[0].messages[0].attachments?.[0].dataUrl).toBe("data:image/png;base64,large-payload");
  });

  it("keeps only the most recent 20 conversations", () => {
    const conversations = Array.from({ length: 25 }, (_, index) => ({
      id: `conv-${index}`,
      title: `对话 ${index}`,
      updatedAt: index,
      messages: [],
    }));

    expect(sanitizeConversationsForStorage(conversations)).toHaveLength(20);
  });
});
