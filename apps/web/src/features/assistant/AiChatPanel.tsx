import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  AtSign,
  ChevronLeft,
  File,
  FolderClosed,
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
import type { AiExplanation } from "../../data/aiExplanations";
import type { FileNode } from "../../data/files";
import type { MistakeItem } from "../../data/mistakes";
import {
  getCourseAgentSession,
  listCourseAgentSessions,
  streamCourseAgentMessage,
  type CourseAgentStreamEvent,
} from "../../services/courseAgentApi";
import { postJsonStream } from "../../services/streamClient";
import { consumeAssistantStream } from "./assistantStream";
import { ChatCitationList } from "./ChatCitationList";

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
  content?: string;
  content_preview: string;
  page_number?: number | null;
  source_title?: string;
}

type ChatStreamEvent =
  | { type: "chunk"; content: string }
  | { type: "status"; event: string; message: string; tool_name?: string; success?: boolean }
  | { type: "citations"; tool_name?: string; citations: ChatCitation[] }
  | { type: "session_created"; session_id: string; title?: string; course_id?: string }
  | { type: "error"; message: string }
  | { type: "done" };

interface ChatSession {
  id: string;
  name: string;
  messages: ChatMessage[];
  createdAt: number;
  agentSessionId?: string | null;
}

interface SelectedTextSnippet {
  id: string;
  text: string;
  sourceMessageIndex: number;
}

interface SelectionMenuState {
  text: string;
  sourceMessageIndex: number;
  top: number;
  left: number;
}

type AiChatMentionType = "course_file" | "course_folder" | "ai_explanation" | "mistake";

interface AiChatMention {
  id: string;
  type: AiChatMentionType;
  label: string;
  source: string;
}

export interface AiChatContext {
  files?: FileNode[];
  aiItems?: AiExplanation[];
  mistakeItems?: MistakeItem[];
  selectedFileId?: string | null;
  selectedAiId?: string | null;
  selectedMistakeId?: string | null;
}

export interface CourseAgentBinding {
  courseId: string;
  courseSessionId: string;
  courseTitle?: string;
  courseGoal?: string;
  currentTaskId?: string | null;
  currentSourceVersionId?: string | null;
}

function buildWelcomeMessage(courseBinding?: CourseAgentBinding) {
  if (courseBinding) {
    const title = courseBinding.courseTitle || courseBinding.courseGoal || "当前课程";
    return `你好！我是「${title}」的 AI 助教。我可以结合课程资料、学习方案和当前任务为你答疑。`;
  }
  return "你好！我是 Mentora AI 助手。关于你的学习课程，有什么我可以帮你的吗？";
}

function createEmptySession(courseBinding?: CourseAgentBinding): ChatSession {
  return {
    id: crypto.randomUUID(),
    name: "新对话",
    createdAt: Date.now(),
    agentSessionId: null,
    messages: [{ role: "assistant", content: buildWelcomeMessage(courseBinding) }],
  };
}

interface MentionMenuItem extends AiChatMention {
  subtitle: string;
  current?: boolean;
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

const MAX_SELECTED_TEXT_SNIPPETS = 8;
const MAX_SELECTED_TEXT_LENGTH = 1000;
const SELECTED_TEXT_PREVIEW_LENGTH = 80;
const MAX_MENTION_MENU_ITEMS = 12;
const AI_CHAT_INPUT_MIN_HEIGHT = 28;
const AI_CHAT_INPUT_MAX_HEIGHT = 140;

function normalizeSelectedText(text: string) {
  return text.replace(/\s+/g, " ").trim();
}

function truncateText(text: string, maxLength: number) {
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
}

function buildSelectedTextMessage(text: string, snippets: SelectedTextSnippet[]) {
  if (!snippets.length) return text;

  const context = snippets
    .map((snippet, index) => `${index + 1}. ${snippet.text}`)
    .join("\n");

  return [
    "以下是用户从上一轮 AI 回复中选中的重点上下文，请优先围绕它回答：",
    context,
    "",
    `用户问题：${text}`,
  ].join("\n");
}

function flattenMentionFiles(nodes: FileNode[], parentNames: string[] = []): MentionMenuItem[] {
  return nodes.flatMap((node) => {
    const path = [...parentNames, node.name];
    const item: MentionMenuItem = {
      id: node.id,
      type: node.type === "folder" ? "course_folder" : "course_file",
      label: node.name,
      source: path.join(" / "),
      subtitle: node.type === "folder" ? "课程文件夹" : "课程文件",
    };
    return [item, ...(node.children ? flattenMentionFiles(node.children, path) : [])];
  });
}

function buildMentionMenuItems(context?: AiChatContext, query = "") {
  const files = flattenMentionFiles(context?.files ?? []);
  const aiItems: MentionMenuItem[] = (context?.aiItems ?? []).map((item) => ({
    id: item.id,
    type: "ai_explanation",
    label: item.title,
    source: item.topic,
    subtitle: "AI 讲解",
  }));
  const mistakes: MentionMenuItem[] = (context?.mistakeItems ?? []).map((item) => ({
    id: item.id,
    type: "mistake",
    label: item.title,
    source: item.topic,
    subtitle: "错题集",
  }));

  const allItems = [...files, ...aiItems, ...mistakes].map((item) => ({
    ...item,
    current:
      item.id === context?.selectedFileId ||
      item.id === context?.selectedAiId ||
      item.id === context?.selectedMistakeId,
  }));
  const normalizedQuery = query.trim().toLocaleLowerCase();
  const filtered = normalizedQuery
    ? allItems.filter((item) =>
        `${item.label} ${item.source} ${item.subtitle}`.toLocaleLowerCase().includes(normalizedQuery),
      )
    : allItems;

  return filtered
    .sort((a, b) => Number(b.current) - Number(a.current))
    .slice(0, MAX_MENTION_MENU_ITEMS);
}

function getMentionTrigger(input: string, caret: number) {
  const beforeCaret = input.slice(0, caret);
  const atIndex = beforeCaret.lastIndexOf("@");
  if (atIndex < 0) return null;
  const charBeforeAt = atIndex > 0 ? beforeCaret[atIndex - 1] : "";
  if (charBeforeAt && !/\s/.test(charBeforeAt)) return null;
  const query = beforeCaret.slice(atIndex + 1);
  if (/\s/.test(query)) return null;
  return { atIndex, query };
}

function getMentionIcon(type: AiChatMentionType) {
  return type === "course_folder" ? <FolderClosed size={14} /> : <File size={14} />;
}

function AiChatMentionMenu({
  items,
  activeIndex,
  onSelect,
}: {
  items: MentionMenuItem[];
  activeIndex: number;
  onSelect: (item: MentionMenuItem) => void;
}) {
  return (
    <div className="ai-mention-menu" role="listbox" aria-label="引用课程上下文">
      {items.length ? (
        items.map((item, index) => (
          <button
            className={`ai-mention-item${index === activeIndex ? " active" : ""}`}
            key={`${item.type}:${item.id}`}
            type="button"
            role="option"
            aria-selected={index === activeIndex}
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => onSelect(item)}
          >
            <span className="ai-mention-icon">
              {item.type === "course_folder" ? <FolderClosed size={14} /> : <File size={14} />}
            </span>
            <span className="ai-mention-main">
              <strong>{item.label}</strong>
              <small>{item.current ? "当前 · " : ""}{item.subtitle}{item.source ? ` · ${item.source}` : ""}</small>
            </span>
          </button>
        ))
      ) : (
        <div className="ai-mention-empty">没有可引用的课程内容</div>
      )}
    </div>
  );
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
  context,
  courseBinding,
}: {
  width?: number;
  onClose?: () => void;
  mode?: "panel" | "page";
  context?: AiChatContext;
  courseBinding?: CourseAgentBinding;
}) {
  /* ── 会话状态管理 ── */
  const [sessions, setSessions] = useState<ChatSession[]>(() => [createEmptySession(courseBinding)]);
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
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [sending, setSending] = useState(false);
  const [selectedTextSnippets, setSelectedTextSnippets] = useState<SelectedTextSnippet[]>([]);
  const [selectionMenu, setSelectionMenu] = useState<SelectionMenuState | null>(null);
  const [mentions, setMentions] = useState<AiChatMention[]>([]);
  const [mentionMenuOpen, setMentionMenuOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionActiveIndex, setMentionActiveIndex] = useState(0);
  const [courseSessionsLoaded, setCourseSessionsLoaded] = useState(false);

  const mentionItems = buildMentionMenuItems(context, mentionQuery);

  useEffect(() => {
    if (!courseBinding?.courseId || courseSessionsLoaded) return;

    let cancelled = false;
    (async () => {
      try {
        const items = await listCourseAgentSessions(courseBinding.courseId);
        if (cancelled || items.length === 0) {
          if (!cancelled) setCourseSessionsLoaded(true);
          return;
        }

        const detail = await getCourseAgentSession(courseBinding.courseId, items[0].id);
        if (cancelled) return;

        const restored: ChatSession = {
          id: crypto.randomUUID(),
          agentSessionId: detail.id,
          name: detail.title || "新对话",
          createdAt: detail.updated_at ? Date.parse(detail.updated_at) : Date.now(),
          messages: detail.messages.length > 0
            ? detail.messages.map((message) => ({
                role: message.role,
                content: message.content,
                citations: message.citations,
              }))
            : [{ role: "assistant", content: buildWelcomeMessage(courseBinding) }],
        };

        const others: ChatSession[] = items.slice(1).map((item) => ({
          id: crypto.randomUUID(),
          agentSessionId: item.id,
          name: item.title || "新对话",
          createdAt: item.updated_at ? Date.parse(item.updated_at) : Date.now(),
          messages: [{ role: "assistant", content: buildWelcomeMessage(courseBinding) }],
        }));

        setSessions([restored, ...others]);
        setActiveSessionId(restored.id);
      } catch {
        // 恢复失败时保留本地空会话
      } finally {
        if (!cancelled) setCourseSessionsLoaded(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [courseBinding, courseSessionsLoaded]);

  function createSession() {
    const newSession = createEmptySession(courseBinding);
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
    void hydrateCourseSession(id);
  }

  function openSessionFromHistory(id: string) {
    setActiveSessionId(id);
    setHistoryOpen(false);
    void hydrateCourseSession(id);
  }

  async function hydrateCourseSession(localSessionId: string) {
    if (!courseBinding?.courseId) return;
    const target = sessions.find((session) => session.id === localSessionId);
    if (!target?.agentSessionId) return;
    const hasUserMessage = target.messages.some((message) => message.role === "user");
    if (hasUserMessage) return;

    try {
      const detail = await getCourseAgentSession(courseBinding.courseId, target.agentSessionId);
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== localSessionId) return session;
          return {
            ...session,
            name: detail.title || session.name,
            messages: detail.messages.length > 0
              ? detail.messages.map((message) => ({
                  role: message.role,
                  content: message.content,
                  citations: message.citations,
                }))
              : session.messages,
          };
        }),
      );
    } catch {
      // 历史加载失败时保留当前占位消息
    }
  }

  function applyStreamEvent(data: ChatStreamEvent | CourseAgentStreamEvent) {
    if (data.type === "session_created") {
      setSessions((prev) =>
        prev.map((session) =>
          session.id === activeSessionId
            ? {
                ...session,
                agentSessionId: data.session_id,
                name: data.title || session.name,
              }
            : session,
        ),
      );
      return;
    }

    if (data.type === "chunk") {
      updateLastAssistant((last) => ({
        ...last,
        content: last.content + data.content,
      }));
      return;
    }

    if (data.type === "status") {
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
      return;
    }

    if (data.type === "citations") {
      updateLastAssistant((last) => ({
        ...last,
        citations: [...(last.citations ?? []), ...data.citations],
      }));
      return;
    }

    if (data.type === "error") {
      setSessions((prev) =>
        prev.map((session) => {
          if (session.id !== activeSessionId) return session;
          const msgs = [...session.messages];
          const last = msgs[msgs.length - 1];
          msgs[msgs.length - 1] = {
            ...last,
            content: last.content || `错误: ${data.message}`,
          };
          return { ...session, messages: msgs };
        }),
      );
    }
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
        const empty = createEmptySession(courseBinding);
        setActiveSessionId(empty.id);
        return [empty];
      }
      return next;
    });
  }

  function deleteAllSessions() {
    const empty = createEmptySession(courseBinding);
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

  function closeSelectionMenu() {
    setSelectionMenu(null);
  }

  function inspectAssistantSelection() {
    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
      closeSelectionMenu();
      return;
    }

    const range = selection.getRangeAt(0);
    const ancestor = range.commonAncestorContainer;
    const element =
      ancestor.nodeType === Node.ELEMENT_NODE
        ? (ancestor as Element)
        : ancestor.parentElement;
    const assistantMessage = element?.closest(".ai-chat-message.assistant") as HTMLElement | null;

    if (!assistantMessage || !panelRef.current?.contains(assistantMessage)) {
      closeSelectionMenu();
      return;
    }

    const text = normalizeSelectedText(selection.toString()).slice(0, MAX_SELECTED_TEXT_LENGTH);
    if (!text) {
      closeSelectionMenu();
      return;
    }

    const rect = range.getBoundingClientRect();
    const fallbackRect = range.getClientRects()[0];
    const targetRect = rect.width || rect.height ? rect : fallbackRect;
    if (!targetRect) {
      closeSelectionMenu();
      return;
    }

    const sourceMessageIndex = Number(assistantMessage.dataset.messageIndex ?? "-1");
    const left = Math.min(window.innerWidth - 16, Math.max(16, targetRect.left + targetRect.width / 2));
    const top = Math.max(12, targetRect.top - 12);

    setSelectionMenu({ text, sourceMessageIndex, left, top });
  }

  function handleSelectionEnd() {
    window.setTimeout(inspectAssistantSelection, 0);
  }

  function handleAddSelectionToChat() {
    if (!selectionMenu) return;
    const snippet: SelectedTextSnippet = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      text: selectionMenu.text,
      sourceMessageIndex: selectionMenu.sourceMessageIndex,
    };

    setSelectedTextSnippets((prev) => {
      if (prev.some((item) => item.text === snippet.text)) return prev;
      return [...prev, snippet].slice(-MAX_SELECTED_TEXT_SNIPPETS);
    });

    window.getSelection()?.removeAllRanges();
    closeSelectionMenu();
    inputRef.current?.focus();
  }

  function syncInputHeight() {
    const el = inputRef.current;
    if (!el) return;
    if (!el.value) {
      el.style.height = `${AI_CHAT_INPUT_MIN_HEIGHT}px`;
      el.style.overflowY = "hidden";
      return;
    }
    el.style.height = "auto";
    const nextHeight = Math.max(
      AI_CHAT_INPUT_MIN_HEIGHT,
      Math.min(el.scrollHeight, AI_CHAT_INPUT_MAX_HEIGHT),
    );
    el.style.height = `${nextHeight}px`;
    el.style.overflowY = el.scrollHeight > AI_CHAT_INPUT_MAX_HEIGHT ? "auto" : "hidden";
  }

  function syncMentionMenu(nextInput: string, caret: number | null) {
    if (caret == null) {
      setMentionMenuOpen(false);
      return;
    }
    const trigger = getMentionTrigger(nextInput, caret);
    if (!trigger) {
      setMentionMenuOpen(false);
      return;
    }
    setMentionQuery(trigger.query);
    setMentionActiveIndex(0);
    setMentionMenuOpen(true);
  }

  function handleInputChange(event: React.ChangeEvent<HTMLTextAreaElement>) {
    const nextInput = event.target.value;
    setInput(nextInput);
    syncMentionMenu(nextInput, event.target.selectionStart ?? null);
    window.setTimeout(syncInputHeight, 0);
  }

  function openMentionMenuFromButton() {
    inputRef.current?.focus();
    const caret = inputRef.current?.selectionStart ?? input.length;
    const needsSpace = input.length > 0 && caret > 0 && !/\s/.test(input[caret - 1] ?? "");
    const prefix = needsSpace ? " @" : "@";
    const nextInput = `${input.slice(0, caret)}${prefix}${input.slice(caret)}`;
    const nextCaret = caret + prefix.length;
    setInput(nextInput);
    setMentionQuery("");
    setMentionActiveIndex(0);
    setMentionMenuOpen(true);
    window.setTimeout(() => {
      inputRef.current?.setSelectionRange(nextCaret, nextCaret);
      syncInputHeight();
    }, 0);
  }

  function handleMentionSelect(item: MentionMenuItem) {
    const caret = inputRef.current?.selectionStart ?? input.length;
    const trigger = getMentionTrigger(input, caret);
    if (!trigger) return;

    const inserted = `@${item.label} `;
    const nextInput = `${input.slice(0, trigger.atIndex)}${inserted}${input.slice(caret)}`;
    const nextCaret = trigger.atIndex + inserted.length;
    setInput(nextInput);
    setMentions((prev) => {
      if (prev.some((mention) => mention.id === item.id && mention.type === item.type)) return prev;
      return [...prev, {
        id: item.id,
        type: item.type,
        label: item.label,
        source: item.source,
      }];
    });
    setMentionMenuOpen(false);
    window.setTimeout(() => {
      inputRef.current?.focus();
      inputRef.current?.setSelectionRange(nextCaret, nextCaret);
      syncInputHeight();
    }, 0);
  }

  function handleRemoveMention(mention: AiChatMention) {
    setMentions((prev) => prev.filter((item) => !(item.id === mention.id && item.type === mention.type)));
    setInput((prev) => prev.replace(`@${mention.label} `, "").replace(`@${mention.label}`, "").trimStart());
    window.setTimeout(syncInputHeight, 0);
  }

  useLayoutEffect(() => {
    syncInputHeight();
  }, [input]);

  useEffect(() => {
    function handleDocumentMouseDown(event: MouseEvent) {
      const target = event.target as Node | null;
      if (target && panelRef.current?.contains(target)) {
        if (!(target as Element).closest(".ai-chat-input-area")) {
          setMentionMenuOpen(false);
        }
        return;
      }
      closeSelectionMenu();
      setMentionMenuOpen(false);
    }

    function handleDocumentKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") closeSelectionMenu();
    }

    function handleDocumentKeyUp() {
      handleSelectionEnd();
    }

    document.addEventListener("mousedown", handleDocumentMouseDown);
    document.addEventListener("keydown", handleDocumentKeyDown);
    document.addEventListener("keyup", handleDocumentKeyUp);
    return () => {
      document.removeEventListener("mousedown", handleDocumentMouseDown);
      document.removeEventListener("keydown", handleDocumentKeyDown);
      document.removeEventListener("keyup", handleDocumentKeyUp);
    };
  });

  async function handleSend() {
    const text = input.trim();
    if (!text || !activeSession) return;

    const snippetsForRequest = selectedTextSnippets;
    const mentionsForRequest = mentions.filter((mention) => text.includes(`@${mention.label}`));
    const requestMessage = buildSelectedTextMessage(text, snippetsForRequest);

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
    setSelectedTextSnippets([]);
    setMentions([]);
    setMentionMenuOpen(false);
    closeSelectionMenu();
    setSending(true);
    window.setTimeout(syncInputHeight, 0);

    try {
      if (courseBinding) {
        await streamCourseAgentMessage({
          courseId: courseBinding.courseId,
          message: requestMessage,
          agentSessionId: activeSession.agentSessionId,
          currentTaskId: courseBinding.currentTaskId,
          currentSourceVersionId: courseBinding.currentSourceVersionId ?? context?.selectedFileId,
          mentions: mentionsForRequest,
          onEvent: applyStreamEvent,
        });
      } else {
        const historyMessages =
          sessions.find((s) => s.id === activeSessionId)?.messages ?? [];
        const body = await postJsonStream(
          "/api/chat/stream/",
          {
            message: requestMessage,
            history: historyMessages.map((m) => ({
              role: m.role,
              content: m.content,
            })),
            mentions: mentionsForRequest,
          },
        );
        await consumeAssistantStream(body, (event) => applyStreamEvent(event as ChatStreamEvent));
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
    if (mentionMenuOpen) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMentionActiveIndex((index) => Math.min(index + 1, Math.max(mentionItems.length - 1, 0)));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setMentionActiveIndex((index) => Math.max(index - 1, 0));
        return;
      }
      if (e.key === "Enter") {
        const item = mentionItems[mentionActiveIndex];
        if (item) {
          e.preventDefault();
          handleMentionSelect(item);
          return;
        }
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setMentionMenuOpen(false);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const isPage = mode === "page";

  return (
    <div
      ref={panelRef}
      className={`ai-chat-panel${isPage ? " ai-chat-panel--page" : ""}`}
      style={!isPage ? { width } : undefined}
      role="complementary"
      aria-label="AI 对话面板"
    >
      <header className="ai-chat-header">
        <div className="ai-chat-header-main">
          <strong className="ai-chat-header-brand">Mentora</strong>
          {courseBinding && (
            <div className="ai-chat-course-tags">
              <span className="ai-chat-course-tag">
                {courseBinding.courseTitle || courseBinding.courseGoal || "当前课程"}
              </span>
              {activeSession?.agentSessionId ? (
                <span className="ai-chat-course-tag bound">已绑定课程</span>
              ) : null}
            </div>
          )}
        </div>
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

          <div
            className="ai-chat-messages"
            ref={listRef}
            onMouseUp={handleSelectionEnd}
            onScroll={closeSelectionMenu}
          >
            {activeSession?.messages.map((msg, i) => (
              <div className={`ai-chat-message ${msg.role}`} data-message-index={i} key={i}>
                {msg.role === "assistant" && (
                  <span className="ai-chat-avatar">
                    <Sparkles size={13} />
                  </span>
                )}
                <div className="ai-chat-bubble">
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
                  {msg.content && (
                    msg.role === "assistant" ? (
                      <AiMarkdownMessage content={msg.content} />
                    ) : (
                      <div className="ai-chat-content">{msg.content}</div>
                    )
                  )}
                  {msg.citations?.length ? (
                    <ChatCitationList citations={msg.citations} />
                  ) : null}
                </div>
              </div>
            ))}
          </div>

          <div className="ai-chat-input-area">
            {selectedTextSnippets.length > 0 && (
              <div className="ai-selected-text-wrap">
                <button
                  className="ai-selected-text-pill"
                  type="button"
                  aria-label={`已选择 ${selectedTextSnippets.length} 个文本片段`}
                >
                  <MessageSquare size={14} />
                  <strong>{selectedTextSnippets.length}</strong>
                  <span>个已选文本片段</span>
                </button>
                <div className="ai-selected-text-preview" role="tooltip">
                  {selectedTextSnippets.map((snippet) => (
                    <div className="ai-selected-text-preview-item" key={snippet.id}>
                      "{truncateText(snippet.text, SELECTED_TEXT_PREVIEW_LENGTH)}"
                    </div>
                  ))}
                </div>
                <button
                  className="ai-selected-text-clear"
                  type="button"
                  onClick={() => setSelectedTextSnippets([])}
                  aria-label="清除已选文本片段"
                >
                  <X size={14} />
                </button>
              </div>
            )}
            {mentions.length > 0 && (
              <div className="ai-mentioned-context-list" aria-label="已引用课程内容">
                {mentions.map((mention) => (
                  <div className="ai-mentioned-context-pill" key={`${mention.type}:${mention.id}`}>
                    <span className="ai-mentioned-context-icon">
                      {getMentionIcon(mention.type)}
                    </span>
                    <span className="ai-mentioned-context-label">{mention.label}</span>
                    <button
                      type="button"
                      onClick={() => handleRemoveMention(mention)}
                      aria-label={`移除 ${mention.label}`}
                    >
                      <X size={13} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="ai-chat-input-row">
              {mentionMenuOpen && (
                <AiChatMentionMenu
                  items={mentionItems}
                  activeIndex={mentionActiveIndex}
                  onSelect={handleMentionSelect}
                />
              )}
              <textarea
                ref={inputRef}
                className="ai-chat-input"
                placeholder="输入消息…"
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                onClick={(event) => syncMentionMenu(input, (event.target as HTMLTextAreaElement).selectionStart)}
                rows={1}
              />
              <div className="ai-chat-input-actions">
                <button
                  className="ai-chat-mention-button"
                  type="button"
                  onClick={openMentionMenuFromButton}
                  aria-label="引用课程内容"
                >
                  <AtSign size={16} />
                </button>
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
        </>
      )}
      {selectionMenu && (
        <div
          className="ai-selection-menu"
          style={{ top: selectionMenu.top, left: selectionMenu.left }}
        >
          <button type="button" onMouseDown={(event) => event.preventDefault()} onClick={handleAddSelectionToChat}>
            <MessageSquare size={15} />
            添加到对话
          </button>
        </div>
      )}
    </div>
  );
}
