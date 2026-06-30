import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  Beaker,
  Bell,
  BookOpen,
  Check,
  ChevronLeft,
  FolderClosed,
  GripVertical,
  History,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Send,
  Settings,
  Sparkles,
  Trash2,
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

interface ChatSession {
  id: string;
  name: string;
  messages: ChatMessage[];
  createdAt: number; // Date.now() 时间戳
}

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

/* 按自然日将时间戳分组 */
function groupByDate<T extends { createdAt: number }>(items: T[]) {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const date = new Date(item.createdAt);
    const key = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    const arr = groups.get(key) ?? [];
    arr.push(item);
    groups.set(key, arr);
  }
  return Array.from(groups.entries()).sort(
    ([a], [b]) => new Date(b).getTime() - new Date(a).getTime(),
  );
}

/* 将日期 key 格式化为"今天/昨天/N天前/N周前" */
function formatDateLabel(key: string) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const target = new Date(key);
  target.setHours(0, 0, 0, 0);
  const diff = Math.round(
    (today.getTime() - target.getTime()) / (1000 * 60 * 60 * 24),
  );
  if (diff <= 0) return "今天";
  if (diff === 1) return "昨天";
  if (diff < 7) return `${diff}天前`;
  const weeks = Math.floor(diff / 7);
  return `${weeks}周前`;
}

function AiChatPanel({
  width,
  onClose,
}: {
  width: number;
  onClose: () => void;
}) {
  /* ── 会话状态管理 ── */
  const [sessions, setSessions] = useState<ChatSession[]>(() => [
    {
      id: crypto.randomUUID(),
      name: "新对话",
      createdAt: Date.now(),
      messages: [
        {
          role: "assistant",
          content:
            "你好！我是 Mentora AI 助手。关于你的学习课程，有什么我可以帮你的吗？",
        },
      ],
    },
  ]);
  const [activeSessionId, setActiveSessionId] = useState<string>(
    () => sessions[0]?.id ?? "",
  );
  const [historyOpen, setHistoryOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const filteredSessions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) =>
      getSessionTitle(s).toLowerCase().includes(q),
    );
  }, [sessions, searchQuery]);

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const [sending, setSending] = useState(false);

  /* 创建新会话 */
  function createSession() {
    const newSession: ChatSession = {
      id: crypto.randomUUID(),
      name: "新对话",
      createdAt: Date.now(),
      messages: [
        {
          role: "assistant",
          content:
            "你好！我是 Mentora AI 助手。关于你的学习课程，有什么我可以帮你的吗？",
        },
      ],
    };
    setSessions((prev) => [...prev, newSession]);
    setActiveSessionId(newSession.id);
    setInput("");
  }

  /* 关闭会话 */
  function closeSession(id: string) {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      if (id === activeSessionId && next.length > 0) {
        const idx = prev.findIndex((s) => s.id === id);
        const targetIdx = Math.min(idx, next.length - 1);
        setActiveSessionId(next[targetIdx].id);
      }
      return next;
    });
  }

  /* 切换会话 */
  function switchSession(id: string) {
    setActiveSessionId(id);
    setInput("");
  }

  /* 从历史页面进入某一会话 */
  function openSessionFromHistory(id: string) {
    setActiveSessionId(id);
    setHistoryOpen(false);
  }

  /* 删除单个历史会话 */
  function deleteSession(id: string) {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      if (id === activeSessionId && next.length > 0) {
        const idx = prev.findIndex((s) => s.id === id);
        const targetIdx = Math.min(idx, next.length - 1);
        setActiveSessionId(next[targetIdx].id);
      }
      if (next.length === 0) {
        const empty: ChatSession = {
          id: crypto.randomUUID(),
          name: "新对话",
          createdAt: Date.now(),
          messages: [
            {
              role: "assistant",
              content:
                "你好！我是 Mentora AI 助手。关于你的学习课程，有什么我可以帮你的吗？",
            },
          ],
        };
        setActiveSessionId(empty.id);
        return [empty];
      }
      return next;
    });
  }

  /* 删除全部会话 */
  function deleteAllSessions() {
    const empty: ChatSession = {
      id: crypto.randomUUID(),
      name: "新对话",
      createdAt: Date.now(),
      messages: [
        {
          role: "assistant",
          content:
            "你好！我是 Mentora AI 助手。关于你的学习课程，有什么我可以帮你的吗？",
        },
      ],
    };
    setSessions([empty]);
    setActiveSessionId(empty.id);
  }

  /* 取第一条用户消息作为历史会话标题 */
  function getSessionTitle(session: ChatSession) {
    const firstUser = session.messages.find((m) => m.role === "user");
    return firstUser?.content?.trim() || "新对话";
  }

  function updateLastAssistant(update: (message: ChatMessage) => ChatMessage) {
    if (!activeSession) return;
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== activeSessionId) return s;
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (!last || last.role !== "assistant") return s;
        msgs[msgs.length - 1] = update(last);
        return { ...s, messages: msgs };
      }),
    );
  }

  async function handleSend() {
    const text = input.trim();
    if (!text || !activeSession) return;

    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== activeSessionId) return s;
        return {
          ...s,
          messages: [
            ...s.messages,
            { role: "user", content: text },
            { role: "assistant", content: "" },
          ],
        };
      }),
    );
    setInput("");
    setSending(true);

    try {
      const historyMessages =
        sessions.find((s) => s.id === activeSessionId)?.messages ?? [];
      const resp = await fetch("/api/chat/stream/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: historyMessages.map((m) => ({
            role: m.role,
            content: m.content,
          })),
        }),
      });

      if (!resp.ok) {
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
              setSessions((prev) =>
                prev.map((s) => {
                  if (s.id !== activeSessionId) return s;
                  const msgs = [...s.messages];
                  const last = msgs[msgs.length - 1];
                  msgs[msgs.length - 1] = {
                    ...last,
                    content: last.content || `错误: ${data.message}`,
                  };
                  return { ...s, messages: msgs };
                }),
              );
            }
          } catch {
            // 跳过无法解析的行
          }
        }
      }
    } catch (err: any) {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== activeSessionId) return s;
          const msgs = [...s.messages];
          const last = msgs[msgs.length - 1];
          const errorMsg = err?.message || "连接失败";
          msgs[msgs.length - 1] = {
            ...last,
            content:
              last.content || `抱歉，AI 服务出错: ${errorMsg}`,
          };
          return { ...s, messages: msgs };
        }),
      );
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
        <strong className="ai-chat-header-brand">Mentora</strong>
        <div className="ai-chat-header-actions">
          <button
            className="ai-chat-action-btn"
            type="button"
            onClick={createSession}
            title="新建会话"
            aria-label="新建会话"
          >
            <Plus size={14} />
          </button>
          <button
            className="ai-chat-action-btn"
            type="button"
            onClick={() => setHistoryOpen(true)}
            title="历史会话"
            aria-label="历史会话"
          >
            <History size={14} />
          </button>
          <button
            className="ai-chat-close"
            type="button"
            onClick={onClose}
            aria-label="关闭 AI 面板"
          >
            <X size={16} />
          </button>
        </div>
      </header>

      {historyOpen ? (
        <div className="ai-chat-history" aria-label="历史会话">
          <header className="ai-chat-history-header">
            <button
              className="ai-chat-history-back"
              type="button"
              onClick={() => setHistoryOpen(false)}
            >
              <ChevronLeft size={16} />
              <span>返回</span>
            </button>
          </header>

          <div className="ai-chat-history-toolbar">
            <h3 className="ai-chat-history-title">历史会话</h3>
            <button
              className="ai-chat-history-delete-all"
              type="button"
              onClick={deleteAllSessions}
            >
              <Trash2 size={14} />
              <span>删除全部</span>
            </button>
          </div>

          <div className="ai-chat-history-search">
            <Search size={14} />
            <input
              type="text"
              placeholder="搜索历史会话"
              aria-label="搜索历史会话"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {searchQuery.trim() && (
            <div className="ai-chat-history-count">
              找到 <span>{filteredSessions.length}</span> 条相关对话
            </div>
          )}

          <div className="ai-chat-history-list">
            {filteredSessions.length === 0 ? (
              <div className="ai-chat-history-empty">暂无历史会话</div>
            ) : (
              groupByDate(filteredSessions).map(([dateKey, dateSessions]) => (
                <section className="ai-chat-history-group" key={dateKey}>
                  <h4 className="ai-chat-history-date">
                    {formatDateLabel(dateKey)}
                  </h4>
                  <div className="ai-chat-history-items">
                    {dateSessions
                      .sort((a, b) => b.createdAt - a.createdAt)
                      .map((session) => (
                        <div
                          className={`ai-chat-history-item${
                            session.id === activeSessionId ? " current" : ""
                          }`}
                          key={session.id}
                          onClick={() => openSessionFromHistory(session.id)}
                          role="button"
                          tabIndex={0}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              openSessionFromHistory(session.id);
                            }
                          }}
                        >
                          <span className="ai-chat-history-item-icon">
                            <MessageSquare size={14} />
                          </span>
                          <span className="ai-chat-history-item-title">
                            {getSessionTitle(session)}
                          </span>
                          <button
                            className="ai-chat-history-item-delete"
                            type="button"
                            title="删除会话"
                            aria-label={`删除会话 ${getSessionTitle(session)}`}
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteSession(session.id);
                            }}
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      ))}
                  </div>
                </section>
              ))
            )}
          </div>
        </div>
      ) : (
        <>
          <nav className="ai-chat-tab-bar" aria-label="会话标签">
            {sessions.map((session) => (
              <button
                key={session.id}
                className={`ai-chat-tab${
                  session.id === activeSessionId ? " active" : ""
                }`}
                onClick={() => switchSession(session.id)}
                title={session.name}
                type="button"
              >
                <span className="ai-chat-tab-label">{session.name}</span>
                {sessions.length > 1 && (
                  <span
                    className="ai-chat-tab-close"
                    onClick={(e) => {
                      e.stopPropagation();
                      closeSession(session.id);
                    }}
                    role="button"
                    aria-label={`关闭 ${session.name}`}
                  >
                    <X size={12} />
                  </span>
                )}
              </button>
            ))}
          </nav>

          <div className="ai-chat-messages" ref={listRef}>
            {activeSession?.messages.map((msg, i) => (
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
                          className={`ai-chat-status ${
                            status.success === false ? "failed" : ""
                          }`}
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
                        <div
                          className="ai-chat-citation"
                          key={`${citation.evidence_id ?? "source"}-${index}`}
                        >
                          <Check size={12} />
                          <span>
                            {citation.source_title
                              ? `${citation.source_title}: `
                              : ""}
                            {citation.content_preview}
                            {citation.page_number
                              ? ` · p.${citation.page_number}`
                              : ""}
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
        </>
      )}
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
