import { useState } from "react";
import { Check, ChevronDown, ChevronRight } from "lucide-react";

import type { ChatCitation } from "./assistantStorage";

interface ChatCitationBlockProps {
  citation: ChatCitation;
}

/** 单条引用卡片：标题始终可见，正文默认收起。 */
function ChatCitationBlock({ citation }: ChatCitationBlockProps) {
  const [expanded, setExpanded] = useState(false);
  const content = citation.content || citation.content_preview;

  return (
    <div className={`ai-chat-citation${expanded ? " is-expanded" : ""}`}>
      <button
        type="button"
        className="ai-chat-citation-toggle"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        aria-label={expanded ? "收起引用正文" : "展开引用正文"}
      >
        <span className="ai-chat-citation-chevron" aria-hidden="true">
          {expanded ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        </span>
        <Check size={12} />
        <span className="ai-chat-citation-label">
          {citation.source_title || "引用资料"}
          {citation.page_number ? ` · p.${citation.page_number}` : ""}
        </span>
      </button>
      {expanded ? <blockquote>{content}</blockquote> : null}
    </div>
  );
}

interface ChatCitationListProps {
  citations: ChatCitation[];
}

/** 消息下方的引用来源列表。 */
export function ChatCitationList({ citations }: ChatCitationListProps) {
  return (
    <div className="ai-chat-citations" aria-label="引用来源">
      {citations.map((citation, index) => (
        <ChatCitationBlock
          key={`${citation.source_title ?? "source"}-${index}`}
          citation={citation}
        />
      ))}
    </div>
  );
}
