import { Bot, Minus, Square, X } from "lucide-react";
import { Link } from "react-router-dom";

import { getDesktopApi } from "../lib/desktop";

function MentoraMark() {
  return (
    <svg
      aria-hidden="true"
      className="mentora-mark"
      fill="none"
      viewBox="0 0 24 24"
    >
      <path
        d="M5 18.5V5.5l7 5 7-5v13"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />
      <path
        d="M12 10.5V20.5l2-1.45 2 1.45V8.65"
        stroke="currentColor"
        strokeLinejoin="round"
        strokeWidth="1.55"
      />
      <path
        d="M8 17.5h8"
        stroke="currentColor"
        strokeLinecap="round"
        strokeWidth="1.8"
      />
    </svg>
  );
}

export function DesktopTitleBar({
  aiOpen,
  onToggleAi,
}: {
  aiOpen?: boolean;
  onToggleAi?: () => void;
}) {
  const windowApi = getDesktopApi()?.window;

  function toggleMaximize() {
    void windowApi?.toggleMaximize();
  }

  return (
    <header
      className="window-bar"
      data-desktop-titlebar
      data-desktop-drag-region
      onDoubleClick={toggleMaximize}
    >
      <Link
        className="brand"
        data-desktop-no-drag
        to="/courses"
        aria-label="Mentora 课程首页"
      >
        <span className="brand-mark">
          <MentoraMark />
        </span>
        <span>Mentora</span>
      </Link>

      <div className="window-bar-right" data-desktop-no-drag>
        {onToggleAi && (
          <button
            className={`ai-toggle-button${aiOpen ? " active" : ""}`}
            type="button"
            onClick={onToggleAi}
            aria-label={aiOpen ? "关闭 AI 对话" : "打开 AI 对话"}
            title="AI 对话"
          >
            <Bot size={17} />
          </button>
        )}
        <div className="window-controls" aria-label="窗口控制">
          <button
            type="button"
            onClick={() => void windowApi?.minimize()}
            aria-label="最小化"
          >
            <Minus size={16} />
          </button>
          <button
            type="button"
            onClick={toggleMaximize}
            aria-label="最大化或还原"
          >
            <Square size={13} />
          </button>
          <button
            className="window-close-button"
            type="button"
            onClick={() => void windowApi?.close()}
            aria-label="关闭"
          >
            <X size={17} />
          </button>
        </div>
      </div>
    </header>
  );
}
