import { describe, expect, it } from "vitest";

import type { ConversationSnapshot } from "./assistantStorage";
import {
  applyStreamEventToConversation,
  isWelcomeOnlyConversation,
  updateConversationById,
} from "./assistantPanelStream";

function sampleConversation(overrides: Partial<ConversationSnapshot> = {}): ConversationSnapshot {
  return {
    id: "conv-1",
    title: "新对话",
    updatedAt: 1,
    agentSessionId: null,
    messages: [{ role: "assistant", content: "欢迎" }],
    ...overrides,
  };
}

describe("assistantPanelStream", () => {
  it("appends chunk content to the last assistant message", () => {
    const conversation = sampleConversation({
      messages: [
        { role: "user", content: "问题" },
        { role: "assistant", content: "部分" },
      ],
    });

    const next = applyStreamEventToConversation(conversation, {
      type: "chunk",
      content: "回答",
    });

    expect(next.messages.at(-1)?.content).toBe("部分回答");
  });

  it("binds session_created to the target conversation", () => {
    const conversation = sampleConversation();
    const next = applyStreamEventToConversation(conversation, {
      type: "session_created",
      session_id: "session-1",
      title: "总结任务",
    });

    expect(next.agentSessionId).toBe("session-1");
    expect(next.title).toBe("总结任务");
  });

  it("updates only the matching conversation id", () => {
    const conversations = [
      sampleConversation({ id: "conv-1" }),
      sampleConversation({
        id: "conv-2",
        messages: [
          { role: "user", content: "另一个" },
          { role: "assistant", content: "" },
        ],
      }),
    ];

    const next = updateConversationById(conversations, "conv-2", (conversation) =>
      applyStreamEventToConversation(conversation, { type: "chunk", content: "流式" }),
    );

    expect(next.find((conversation) => conversation.id === "conv-1")?.messages.at(-1)?.content).toBe("欢迎");
    expect(next.find((conversation) => conversation.id === "conv-2")?.messages.at(-1)?.content).toBe("流式");
  });

  it("detects welcome-only conversations", () => {
    expect(isWelcomeOnlyConversation(sampleConversation())).toBe(true);
    expect(
      isWelcomeOnlyConversation(
        sampleConversation({
          messages: [
            { role: "assistant", content: "欢迎" },
            { role: "user", content: "你好" },
          ],
        }),
      ),
    ).toBe(false);
    expect(isWelcomeOnlyConversation(sampleConversation({ agentSessionId: "session-1" }))).toBe(false);
  });
});
