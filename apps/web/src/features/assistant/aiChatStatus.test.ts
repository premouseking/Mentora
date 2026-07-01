import { describe, expect, it } from "vitest";

import {
  appendAssistantTextChunk,
  applyAssistantStreamEvent,
  flattenAssistantBlocksContent,
} from "./assistantBlocks";
import type { AssistantChatMessage } from "./assistantTypes";

describe("assistantBlocks", () => {
  it("keeps streamed text before tool status and appends post-tool text after tools", () => {
    let message: AssistantChatMessage = { role: "assistant", blocks: [] };

    message = applyAssistantStreamEvent(message, { type: "content", content: "我先查看资料范围。" });
    message = applyAssistantStreamEvent(message, {
      type: "status",
      status_key: "tool:query_course_scope",
      event: "agent.tool.result",
      message: "资料范围查询失败",
      tool_name: "query_course_scope",
      phase: "tool",
      state: "failed",
      success: false,
    });
    message = applyAssistantStreamEvent(message, {
      type: "content",
      content: "根据已有资料，柯西中值定理是……",
    });

    expect(message.blocks).toHaveLength(3);
    expect(message.blocks[0]).toMatchObject({ type: "text", content: "我先查看资料范围。" });
    expect(message.blocks[1]).toMatchObject({
      type: "tool",
      toolName: "query_course_scope",
      progress: -1,
    });
    expect(message.blocks[2]).toMatchObject({
      type: "text",
      content: "根据已有资料，柯西中值定理是……",
    });
  });

  it("updates the same tool block from running to completed", () => {
    let message: AssistantChatMessage = { role: "assistant", blocks: [] };
    message = applyAssistantStreamEvent(message, {
      type: "status",
      status_key: "tool:retrieve_evidence",
      event: "agent.tool.call",
      message: "正在检索资料",
      tool_name: "retrieve_evidence",
      phase: "tool",
      state: "running",
      arguments: { query: "柯西中值定理" },
    });
    message = applyAssistantStreamEvent(message, {
      type: "status",
      status_key: "tool:retrieve_evidence",
      event: "agent.tool.result",
      message: "资料检索完成",
      tool_name: "retrieve_evidence",
      phase: "tool",
      state: "completed",
      success: true,
    });

    expect(message.blocks).toHaveLength(1);
    expect(message.blocks[0]).toMatchObject({
      type: "tool",
      progress: 2,
      title: "已检索资料：柯西中值定理",
    });
  });

  it("appends reasoning into a thinking block before answer text", () => {
    let message: AssistantChatMessage = { role: "assistant", blocks: [] };
    message = applyAssistantStreamEvent(message, { type: "reasoning", content: "先确认资料范围。" });
    message = applyAssistantStreamEvent(message, { type: "content", content: "柯西中值定理是……" });

    expect(message.blocks[0]).toMatchObject({ type: "thinking", status: "success" });
    expect(message.blocks[1]).toMatchObject({ type: "text" });
    expect(flattenAssistantBlocksContent(message.blocks)).toBe("柯西中值定理是……");
  });

  it("appendAssistantTextChunk merges into the last text block only", () => {
    const blocks = appendAssistantTextChunk(
      appendAssistantTextChunk([], "你好"),
      "，世界",
    );
    expect(blocks).toEqual([{ type: "text", content: "你好，世界" }]);
  });
});
