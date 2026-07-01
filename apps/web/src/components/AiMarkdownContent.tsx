import { AssistantMarkdown } from "../features/assistant/AssistantMarkdown";

/** 复用 AI 对话 Markdown（含 KaTeX），供聊天与 AI 讲解正文共用。 */
export function AiMarkdownContent({ content }: { content: string }) {
  return (
    <div className="ai-chat-markdown">
      <AssistantMarkdown content={content} />
    </div>
  );
}
