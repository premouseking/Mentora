import type { ReactNode } from "react";
import { Sparkles } from "lucide-react";

interface AiMessageBubbleProps {
  children: ReactNode;
  visible?: boolean;
  showIcon?: boolean;
}

export function AiMessageBubble({ children, visible = true, showIcon = false }: AiMessageBubbleProps) {
  if (!visible) return null;

  return (
    <div className="ai-message-bubble-area">
      {showIcon && (
        <div className="ai-message-icon">
          <Sparkles size={16} />
        </div>
      )}
      <div className={`ai-message-bubble${showIcon ? "" : " no-icon"}`}>
        <p className="ai-message-text">{children}</p>
      </div>
    </div>
  );
}
