import { useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  ChevronLeft,
  History,
  MessageSquare,
  Plus,
  Search,
  Send,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/* ── 类型定义 ── */

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
  createdAt: number;
}

/* ── 工具函数 ── */

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

/* ── AiChatPanel 组件 ──
   约定：
   - mode="panel"：侧边面板模式，需 width / onClose，显示关闭按钮
   - mode="page"：嵌入页面模式，撑满父容器，不显示关闭按钮
*/

export function AiChatPanel({
  width,
  onClose,
  mode = "panel",
}: {
  width?: number;
  onClose?: () => void;
  mode?: "panel" | "page";
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

  function switchSession(id: string) {
    setActiveSessionId(id);
    setInput("");
  }

  function openSessionFromHistory(id: string) {
    setActiveSessionId(id);
    setHistoryOpen(false);
  }

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

  const isPage = mode === "page";

  return (
    <div
      className={`ai-chat-panel${isPage ? " ai-chat-panel--page" : ""}`}
      style={!isPage ? { width } : undefined}
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
          {!isPage && (
            <button
              className="ai-chat-close"
              type="button"
              onClick={onClose}
              aria-label="关闭 AI 面板"
            >
              <X size={16} />
            </button>
          )}
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
