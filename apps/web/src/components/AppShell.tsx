import { type ReactNode, useEffect, useRef, useState } from "react";
import {
  Bell,
  BookOpen,
  Bot,
  Check,
  ChevronLeft,
  FolderClosed,
  GraduationCap,
  GripVertical,
  History,
  Send,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import { Link, NavLink } from "react-router-dom";

const navItems = [
  { to: "/courses", label: "课程", icon: BookOpen },
  { to: "/library", label: "资源库", icon: FolderClosed },
  { to: "/history", label: "学习记录", icon: History },
  { to: "/notifications", label: "通知", icon: Bell },
  { to: "/settings", label: "设置", icon: Settings },
];

const setupSteps = ["描述目标", "补充信息", "添加资料", "确认需求", "确认方案"];

const MIN_SIDEBAR = 160;
const MAX_SIDEBAR = 320;
const MIN_PANEL = 260;
const MAX_PANEL = 600;
const SIDEBAR_DEFAULT = 196;
const PANEL_DEFAULT = 360;

function Brand() {
  return (
    <Link className="brand" to="/courses" aria-label="Mentora 课程首页">
      <span className="brand-mark">
        <GraduationCap size={18} strokeWidth={2.2} />
      </span>
      <span>Mentora</span>
    </Link>
  );
}

function WindowBar({
  aiOpen,
  onToggleAi,
}: {
  aiOpen?: boolean;
  onToggleAi?: () => void;
}) {
  return (
    <div className="window-bar">
      <Brand />
      <div className="window-bar-right">
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
        <div className="window-controls" aria-hidden="true">
          <span>−</span>
          <span>□</span>
          <span>×</span>
        </div>
      </div>
    </div>
  );
}

function AppSidebar({ width }: { width: number }) {
  return (
    <aside className="sidebar" style={{ width }}>
      <nav className="primary-nav" aria-label="主导航">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
            key={to}
            to={to}
          >
            <Icon size={19} strokeWidth={1.9} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

/* ── Resize handle ── */

function ResizeHandle({
  onResize,
}: {
  onResize: (delta: number) => void;
}) {
  const activeRef = useRef(false);
  const onResizeRef = useRef(onResize);
  onResizeRef.current = onResize;

  const onMove = (e: MouseEvent) => {
    if (!activeRef.current) return;
    onResizeRef.current(e.movementX);
  };

  const onUp = () => {
    if (!activeRef.current) return;
    activeRef.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
  };

  function onDown() {
    activeRef.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }

  useEffect(
    () => () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    },
    [],
  );

  return (
    <div
      className="resize-handle"
      onMouseDown={onDown}
      role="separator"
      aria-orientation="vertical"
      tabIndex={-1}
    >
      <GripVertical size={14} />
    </div>
  );
}

/* ── AI Chat Panel ── */

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

function AiChatPanel({
  width,
  onClose,
}: {
  width: number;
  onClose: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content:
        "你好！我是 Mentora AI 助手。关于你的学习课程，有什么我可以帮你的吗？",
    },
  ]);
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  function handleSend() {
    const text = input.trim();
    if (!text) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "这是一个示例回复。后续将接入真实的 AI 对话能力，为你提供个性化的学习建议和帮助。",
        },
      ]);
      requestAnimationFrame(() => {
        listRef.current?.scrollTo({
          top: listRef.current.scrollHeight,
          behavior: "smooth",
        });
      });
    }, 800);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div
      className="ai-chat-panel"
      style={{ width }}
      role="complementary"
      aria-label="AI 对话面板"
    >
      <header className="ai-chat-header">
        <div className="ai-chat-header-title">
          <span className="ai-chat-header-icon">
            <Sparkles size={16} />
          </span>
          <strong>AI 助手</strong>
        </div>
        <button
          className="ai-chat-close"
          type="button"
          onClick={onClose}
          aria-label="关闭 AI 面板"
        >
          <X size={18} />
        </button>
      </header>

      <div className="ai-chat-messages" ref={listRef}>
        {messages.map((msg, i) => (
          <div className={`ai-chat-message ${msg.role}`} key={i}>
            {msg.role === "assistant" && (
              <span className="ai-chat-avatar">
                <Sparkles size={13} />
              </span>
            )}
            <div className="ai-chat-bubble">{msg.content}</div>
          </div>
        ))}
      </div>

      <div className="ai-chat-input-area">
        <div className="ai-chat-input-row">
          <input
            ref={inputRef}
            className="ai-chat-input"
            placeholder="输入消息…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <button
            className="ai-chat-send"
            type="button"
            onClick={handleSend}
            disabled={!input.trim()}
            aria-label="发送"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── App Shell ── */

export function AppShell({ children }: { children: ReactNode }) {
  const [aiPanelOpen, setAiPanelOpen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(SIDEBAR_DEFAULT);
  const [panelWidth, setPanelWidth] = useState(PANEL_DEFAULT);

  function clamp(val: number, min: number, max: number) {
    return Math.min(max, Math.max(min, val));
  }

  return (
    <div className={`desktop-app${aiPanelOpen ? " ai-panel-open" : ""}`}>
      <WindowBar
        aiOpen={aiPanelOpen}
        onToggleAi={() => setAiPanelOpen((v) => !v)}
      />
      <div className="app-body">
        <AppSidebar width={sidebarWidth} />
        <ResizeHandle
          onResize={(d) =>
            setSidebarWidth((w) => clamp(w + d, MIN_SIDEBAR, MAX_SIDEBAR))
          }
        />
        <section className="page-surface">{children}</section>
        {aiPanelOpen && (
          <>
            <ResizeHandle
              onResize={(d) =>
                setPanelWidth((w) => clamp(w - d, MIN_PANEL, MAX_PANEL))
              }
            />
            <AiChatPanel
              width={panelWidth}
              onClose={() => setAiPanelOpen(false)}
            />
          </>
        )}
      </div>
    </div>
  );
}

function SetupProgress({ current }: { current: number }) {
  return (
    <ol className="setup-progress" aria-label="创建课程进度">
      {setupSteps.map((step, index) => {
        const number = index + 1;
        const completed = number < current;
        const active = number === current;
        return (
          <li className={active ? "active" : completed ? "completed" : ""} key={step}>
            <span className="step-marker">{completed ? <Check size={13} /> : number}</span>
            <span className="step-label">{step}</span>
          </li>
        );
      })}
    </ol>
  );
}

export function SetupShell({
  current,
  children,
}: {
  current: number;
  children: ReactNode;
}) {
  return (
    <div className="desktop-app setup-app">
      <WindowBar />
      <header className="setup-header">
        <Link className="back-link" to="/courses">
          <ChevronLeft size={18} />
          返回课程
        </Link>
        <SetupProgress current={current} />
        <Link className="cancel-link" to="/courses">
          取消
        </Link>
      </header>
      <main className="setup-main">{children}</main>
    </div>
  );
}
