import { Check } from "lucide-react";

import { AssistantThinkingBlock } from "./AssistantThinkingBlock";
import { AssistantToolLine } from "./AssistantToolLine";
import { AssistantMarkdown } from "./AssistantMarkdown";
import type { AssistantChatMessage } from "./assistantTypes";

export function AssistantMessageBody({ message }: { message: AssistantChatMessage }) {
  return (
    <>
      {message.blocks.map((block, index) => {
        if (block.type === "text") {
          if (!block.content.trim()) return null;
          return (
            <div className="ai-chat-assistant-segment ai-chat-text-segment" key={`text-${index}`}>
              <AssistantMarkdown content={block.content} />
            </div>
          );
        }

        if (block.type === "thinking") {
          return <AssistantThinkingBlock block={block} key={`thinking-${index}`} />;
        }

        return <AssistantToolLine block={block} key={block.id} />;
      })}
      {message.citations?.length ? (
        <div className="ai-chat-citations ai-chat-assistant-segment" aria-label="引用来源">
          {message.citations.map((citation, index) => (
            <div
              className="ai-chat-citation"
              key={`${citation.evidence_id ?? "source"}-${index}`}
            >
              <Check size={12} />
              <span>
                {citation.source_title ? `${citation.source_title}: ` : ""}
                {citation.content_preview}
                {citation.page_number ? ` · p.${citation.page_number}` : ""}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </>
  );
}
