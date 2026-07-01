import { X } from "lucide-react";

/** 复用 AI 对话 @引用 pill 样式，用于关键词标签。 */
export function AiKeywordPill({
  label,
  onRemove,
}: {
  label: string;
  onRemove?: () => void;
}) {
  return (
    <div className="ai-mentioned-context-pill">
      <span className="ai-mentioned-context-label">{label}</span>
      {onRemove ? (
        <button type="button" onClick={onRemove} aria-label={`删除标签 ${label}`}>
          <X size={13} />
        </button>
      ) : null}
    </div>
  );
}
