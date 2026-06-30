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
import ReactMarkdown from "react-markdown";
import { Link, NavLink } from "react-router-dom";
import remarkGfm from "remark-gfm";

import { DesktopTitleBar } from "./DesktopTitleBar";
import { CourseInfoBar } from "./CourseInfoBar";

const navItems = [
  { to: "/courses", label: "课程", icon: BookOpen },
  { to: "/library", label: "资源库", icon: FolderClosed },
  { to: "/history", label: "学习记录", icon: History },
  { to: "/notifications", label: "通知", icon: Bell },
  { to: "/settings", label: "设置", icon: Settings },
  { to: "/lab/parsing", label: "解析实验室", icon: Beaker },
];

const setupSteps = ["建立档案", "确认方案"];

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
  statuses?: ChatStatus[];
  citations?: ChatCitation[];
}

interface ChatStatus {
  event: string;
  message: string;
  toolName?: string;
  success?: boolean;
}

interface ChatCitation {
  content_preview: string;
  page_number?: number | null;
  evidence_id?: string;
  source_title?: string;
}

type ChatStreamEvent =
  | { type: "chunk"; content: string }
  | { type: "status"; event: string; message: string; tool_name?: string; success?: boolean }
  | { type: "citations"; tool_name?: string; citations: ChatCitation[] }
  | { type: "error"; message: string }
  | { type: "done" };

function AiMarkdownMessage({ content }: { content: string }) {
  return (
    <div className="ai-chat-markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ ...props }) => (
            <a {...props} target="_blank" rel="noreferrer noopener" />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
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

  const [sending, setSending] = useState(false);

  function updateLastAssistant(update: (message: ChatMessage) => ChatMessage) {
    setMessages((prev) => {
      const updated = [...prev];
      const last = updated[updated.length - 1];
      if (!last || last.role !== "assistant") return prev;
      updated[updated.length - 1] = update(last);
      return updated;
    });
  }

  async function handleSend() {
    const text = input.trim();
    if (!text) return;
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setInput("");
    setSending(true);

    // 先添加一条空的 assistant 消息，流式填充
    setMessages((prev) => [...prev, { role: "assistant", content: "" }]);

    try {
      const resp = await fetch("/api/chat/stream/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: messages.map((m) => ({ role: m.role, content: m.content })),
        }),
      });

      if (!resp.ok) {
        // 非流式错误
        const errorText = await resp.text();
        throw new Error(errorText || `HTTP ${resp.status}`);
      }

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // 保留最后一个可能不完整的行
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const data = JSON.parse(line.slice(6)) as ChatStreamEvent;
            if (data.type === "chunk") {
              updateLastAssistant((last) => ({
                ...last,
                content: last.content + data.content,
              }));
            } else if (data.type === "status") {
              updateLastAssistant((last) => ({
                ...last,
                statuses: [
                  ...(last.statuses ?? []),
                  {
                    event: data.event,
                    message: data.message,
                    toolName: data.tool_name,
                    success: data.success,
                  },
                ],
              }));
            } else if (data.type === "citations") {
              updateLastAssistant((last) => ({
                ...last,
                citations: [...(last.citations ?? []), ...data.citations],
              }));
            } else if (data.type === "error") {
              setMessages((prev) => {
                const updated = [...prev];
                const last = updated[updated.length - 1];
                updated[updated.length - 1] = {
                  ...last,
                  content: last.content || `错误: ${data.message}`,
                };
                return updated;
              });
            }
          } catch {
            // 跳过无法解析的行
          }
        }
      }
    } catch (err: any) {
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated[updated.length - 1];
        const errorMsg = err?.message || "连接失败";
        updated[updated.length - 1] = {
          ...last,
          content: last.content || `抱歉，AI 服务出错: ${errorMsg}`,
        };
        return updated;
      });
    } finally {
      setSending(false);
    }
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
            <div className="ai-chat-bubble">
              {msg.content && (
                msg.role === "assistant" ? (
                  <AiMarkdownMessage content={msg.content} />
                ) : (
                  <div className="ai-chat-content">{msg.content}</div>
                )
              )}
              {msg.statuses?.length ? (
                <div className="ai-chat-status-list">
                  {msg.statuses.map((status, index) => (
                    <div
                      className={`ai-chat-status ${status.success === false ? "failed" : ""}`}
                      key={`${status.event}-${index}`}
                    >
                      <span className="ai-chat-status-dot" />
                      <span>{status.message}</span>
                    </div>
                  ))}
                </div>
              ) : null}
              {msg.citations?.length ? (
                <div className="ai-chat-citations" aria-label="引用来源">
                  {msg.citations.map((citation, index) => (
                    <div className="ai-chat-citation" key={`${citation.evidence_id ?? "source"}-${index}`}>
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
            </div>
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
            disabled={!input.trim() || sending}
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
  hideInfoBar = false,
  footer,
  leftAside,
  children,
}: {
  current: number;
  hideInfoBar?: boolean;
  footer?: ReactNode;
  leftAside?: ReactNode;
  children: ReactNode;
}) {
  const [infoBarExpanded, setInfoBarExpanded] = useState(false);

  return (
    <div className={`desktop-app setup-app${hideInfoBar ? " no-info-bar" : ""}`}>
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
      <main className="setup-main">
        {leftAside && <div className="setup-left-aside">{leftAside}</div>}
        <div className="setup-content-box">{children}</div>
        {footer && <div className="setup-nav-area">{footer}</div>}
      </main>
      {!hideInfoBar && (
        <CourseInfoBar
          mode={infoBarExpanded ? "expanded" : "collapsed"}
          onToggle={() => setInfoBarExpanded((v) => !v)}
        />
      )}
    </div>
  );
}
