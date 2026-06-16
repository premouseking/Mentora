import { type ReactNode, useEffect, useRef, useState } from "react";
import {
  Beaker,
  Bell,
  BookOpen,
  Check,
  ChevronLeft,
  FolderClosed,
  GripVertical,
  History,
  PanelLeftClose,
  PanelLeftOpen,
  Send,
  Settings,
  Sparkles,
  X,
} from "lucide-react";
import { Link, NavLink } from "react-router-dom";

import { DesktopTitleBar } from "./DesktopTitleBar";

const navItems = [
  { to: "/courses", label: "课程", icon: BookOpen },
  { to: "/library", label: "资源库", icon: FolderClosed },
  { to: "/history", label: "学习记录", icon: History },
  { to: "/notifications", label: "通知", icon: Bell },
  { to: "/settings", label: "设置", icon: Settings },
  { to: "/lab/parsing", label: "解析实验室", icon: Beaker },
];

const setupSteps = ["描述目标", "补充信息", "添加资料", "确认需求", "确认方案"];

const MIN_SIDEBAR = 160;
const MAX_SIDEBAR = 320;
const MIN_PANEL = 260;
const MAX_PANEL = 600;
const SIDEBAR_DEFAULT = 196;
const COLLAPSED_SIDEBAR = 68;
const PANEL_DEFAULT = 360;
const SIDEBAR_COLLAPSED_KEY = "mentora-sidebar-collapsed";
const SIDEBAR_WIDTH_KEY = "mentora-sidebar-width";

function clampSidebarWidth(value: number) {
  return Math.min(MAX_SIDEBAR, Math.max(MIN_SIDEBAR, value));
}

function readStoredSidebarWidth() {
  const raw = localStorage.getItem(SIDEBAR_WIDTH_KEY);
  if (!raw) return SIDEBAR_DEFAULT;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? clampSidebarWidth(parsed) : SIDEBAR_DEFAULT;
}

function readStoredCollapsed() {
  return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
}

function AppSidebar({
  width,
  collapsed,
  labelsVisible,
  animating,
  resizing,
  onToggleCollapsed,
  onTransitionEnd,
}: {
  width: number;
  collapsed: boolean;
  labelsVisible: boolean;
  animating: boolean;
  resizing: boolean;
  onToggleCollapsed: () => void;
  onTransitionEnd: (event: React.TransitionEvent<HTMLElement>) => void;
}) {
  const showLabels = labelsVisible && !collapsed;

  return (
    <aside
      className={[
        "sidebar",
        collapsed && "collapsed",
        showLabels && "sidebar-labels-visible",
        animating && "sidebar-animating",
        resizing && "sidebar-resizing",
      ]
        .filter(Boolean)
        .join(" ")}
      onTransitionEnd={onTransitionEnd}
      style={{ width: collapsed ? COLLAPSED_SIDEBAR : width }}
    >
      <button
        aria-expanded={!collapsed}
        aria-label={collapsed ? "展开侧边栏" : "折叠侧边栏"}
        className="sidebar-toggle"
        onClick={onToggleCollapsed}
        title={collapsed ? "展开侧边栏" : "折叠侧边栏"}
        type="button"
      >
        {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
      </button>
      <nav className="primary-nav" aria-label="主导航">
        {navItems.map(({ to, label, icon: Icon }) => (
          <NavLink
            className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
            key={to}
            title={!showLabels ? label : undefined}
            to={to}
          >
            <Icon size={19} strokeWidth={1.9} />
            <span className="nav-item-label">{label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}

/* ── Resize handle ── */

function ResizeHandle({
  onResize,
  onResizeStart,
  onResizeEnd,
}: {
  onResize: (delta: number) => void;
  onResizeStart?: () => void;
  onResizeEnd?: () => void;
}) {
  const activeRef = useRef(false);
  const lastXRef = useRef(0);
  const onResizeRef = useRef(onResize);
  const onResizeEndRef = useRef(onResizeEnd);
  onResizeRef.current = onResize;
  onResizeEndRef.current = onResizeEnd;

  const onMove = (e: MouseEvent) => {
    if (!activeRef.current) return;
    const delta = e.clientX - lastXRef.current;
    lastXRef.current = e.clientX;
    if (delta !== 0) onResizeRef.current(delta);
  };

  const onUp = () => {
    if (!activeRef.current) return;
    activeRef.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
    onResizeEndRef.current?.();
  };

  function onDown(e: React.MouseEvent) {
    activeRef.current = true;
    lastXRef.current = e.clientX;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    onResizeStart?.();
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
  const [sidebarCollapsed, setSidebarCollapsed] = useState(readStoredCollapsed);
  const [sidebarLabelsVisible, setSidebarLabelsVisible] = useState(
    () => !readStoredCollapsed(),
  );
  const [sidebarAnimating, setSidebarAnimating] = useState(false);
  const [sidebarResizing, setSidebarResizing] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(readStoredSidebarWidth);
  const [panelWidth, setPanelWidth] = useState(PANEL_DEFAULT);
  const sidebarWidthRef = useRef(sidebarWidth);
  const sidebarCollapsedRef = useRef(sidebarCollapsed);
  sidebarWidthRef.current = sidebarWidth;
  sidebarCollapsedRef.current = sidebarCollapsed;

  function clamp(val: number, min: number, max: number) {
    return Math.min(max, Math.max(min, val));
  }

  function toggleSidebarCollapsed() {
    setSidebarAnimating(true);
    setSidebarCollapsed((prev) => {
      const next = !prev;
      setSidebarLabelsVisible(!next);
      localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      return next;
    });
  }

  function handleSidebarTransitionEnd(event: React.TransitionEvent<HTMLElement>) {
    if (event.target !== event.currentTarget || event.propertyName !== "width") return;
    setSidebarAnimating(false);
    if (!sidebarCollapsedRef.current) {
      setSidebarLabelsVisible(true);
    }
  }

  function handleSidebarResize(delta: number) {
    setSidebarWidth((w) => clampSidebarWidth(w + delta));
  }

  function handleSidebarResizeEnd() {
    setSidebarResizing(false);
    localStorage.setItem(SIDEBAR_WIDTH_KEY, String(sidebarWidthRef.current));
  }

  return (
    <div className={`desktop-app${aiPanelOpen ? " ai-panel-open" : ""}`}>
      <DesktopTitleBar
        aiOpen={aiPanelOpen}
        onToggleAi={() => setAiPanelOpen((v) => !v)}
      />
      <div className="app-body">
        <AppSidebar
          animating={sidebarAnimating}
          collapsed={sidebarCollapsed}
          labelsVisible={sidebarLabelsVisible}
          onToggleCollapsed={toggleSidebarCollapsed}
          onTransitionEnd={handleSidebarTransitionEnd}
          resizing={sidebarResizing}
          width={sidebarWidth}
        />
        {!sidebarCollapsed && (
          <ResizeHandle
            onResize={handleSidebarResize}
            onResizeEnd={handleSidebarResizeEnd}
            onResizeStart={() => setSidebarResizing(true)}
          />
        )}
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
      <DesktopTitleBar />
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
