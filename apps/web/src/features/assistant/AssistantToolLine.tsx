import { Search } from "lucide-react";

import type { AssistantToolBlock } from "./assistantTypes";
import { TOOL_PROGRESS } from "./assistantTypes";
import { isHeaderOnlyTool } from "./assistantToolDisplay";

function resolveStatusClass(progress: number): string {
  if (progress === TOOL_PROGRESS.PROCESSING || progress === TOOL_PROGRESS.GENERATING) {
    return "status-processing";
  }
  if (progress === TOOL_PROGRESS.FAILED || progress === TOOL_PROGRESS.PARAM_ERROR) {
    return "status-error";
  }
  if (progress === TOOL_PROGRESS.CANCELLED) return "status-cancelled";
  return "status-completed";
}

/**
 * 工具调用行：对齐插件 AISearchLite header-only 样式（小字灰色 + 左侧放大镜）。
 */
export function AssistantToolLine({ block }: { block: AssistantToolBlock }) {
  const statusClass = resolveStatusClass(block.progress);
  const headerOnly = isHeaderOnlyTool(block.toolName);

  return (
    <div
      className={`ai-chat-tool-line${headerOnly ? " ai-chat-tool-line--header-only" : ""}`}
      aria-label={block.title}
    >
      <span className="ai-chat-tool-line-icon" aria-hidden>
        <Search size={14} strokeWidth={2.25} />
      </span>
      <span className={`ai-chat-tool-line-title ${statusClass}`} data-text={block.title}>
        {block.title}
      </span>
    </div>
  );
}
