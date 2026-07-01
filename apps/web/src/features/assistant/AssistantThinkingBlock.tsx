import { Sparkles } from "lucide-react";

import { AssistantMarkdown } from "./AssistantMarkdown";
import type { AssistantThinkingBlock } from "./assistantTypes";

/**
 * 思考块：对齐插件 ThinkingBlock 的折叠标题与进行中扫光效果。
 */
export function AssistantThinkingBlock({ block }: { block: AssistantThinkingBlock }) {
  const inProgress = block.status === "processing";
  if (!block.content.trim() && !inProgress) return null;

  return (
    <details
      className={`ai-chat-thinking-block ai-chat-assistant-segment${inProgress ? " is-progressing" : " is-done"}`}
      open={inProgress}
    >
      <summary>
        <span className="ai-chat-thinking-icon" aria-hidden>
          <Sparkles size={14} />
        </span>
        <span
          className={`ai-chat-thinking-title${inProgress ? " status-processing" : ""}`}
          data-text="思考过程"
        >
          思考过程
        </span>
      </summary>
      {block.content.trim() ? (
        <div className="ai-chat-thinking-content">
          <AssistantMarkdown content={block.content} />
        </div>
      ) : null}
    </details>
  );
}
