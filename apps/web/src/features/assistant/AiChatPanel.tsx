import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  AtSign,
  Check,
  ChevronLeft,
  Copy,
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
import type { FileNode } from "../../data/files";
import { AssistantMessageBody } from "./AssistantMessageBody";
import { flattenAssistantBlocksContent, applyAssistantStreamEvent } from "./assistantBlocks";
import { getAssistantMessagePlainText } from "./assistantStorage";
import type { AssistantChatMessage, ChatMessage } from "./assistantTypes";
import { isAssistantMessage } from "./assistantTypes";
import { runAssistantChatStream } from "./runAssistantChatStream";

/* ── 类型定义 ── */

interface ChatSession {
  id: string;
  name: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

interface AiChatPersistedState {
  sessions: ChatSession[];
  openSessionIds: string[];
  activeSessionId: string;
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

interface AiChatExplanationContextItem {
  id: string;
  title: string;
  topic: string;
}

interface AiChatMistakeContextItem {
  id?: string;
  item_id?: string;
  title: string;
  topic: string;
}

export interface AiChatContext {
  files?: FileNode[];
  aiItems?: AiChatExplanationContextItem[];
  mistakeItems?: AiChatMistakeContextItem[];
  selectedFileId?: string | null;
  selectedAiId?: string | null;
  selectedMistakeId?: string | null;
}

interface MentionMenuItem extends AiChatMention {
  subtitle: string;
  current?: boolean;
}

/* ── 工具函数 ── */

function groupByDate<T extends { createdAt: number; updatedAt?: number }>(items: T[]) {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const date = new Date(item.updatedAt ?? item.createdAt);
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
const AI_CHAT_STORAGE_KEY = "mentora.aiChatPanel.v2";
const DEFAULT_SESSION_NAME = "新对话";
const DEFAULT_ASSISTANT_GREETING =
  "你好！我是 Mentora AI 助手。关于你的学习课程，有什么我可以帮你的吗？";

function normalizeSelectedText(text: string) {
  return text.replace(/\s+/g, " ").trim();
}

function truncateText(text: string, maxLength: number) {
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
}

function buildSessionTitle(text: string) {
  const normalized = normalizeSelectedText(text)
    .replace(/^请(你)?(解释|介绍|说明|讲讲|说说)/, "")
    .replace(/^什么是/, "")
    .replace(/[？?。.!！]+$/g, "")
    .trim();
  const title = normalized || DEFAULT_SESSION_NAME;
  return truncateText(title, 18);
}

function createDefaultSession(): ChatSession {
  const now = Date.now();
  return {
    id: crypto.randomUUID(),
    name: DEFAULT_SESSION_NAME,
    createdAt: now,
    updatedAt: now,
    messages: [
      {
        role: "assistant",
        blocks: [{ type: "text", content: DEFAULT_ASSISTANT_GREETING }],
      },
    ],
  };
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== "object") return false;
  const message = value as ChatMessage;
  if (message.role === "user") return typeof message.content === "string";
  if (message.role === "assistant") return Array.isArray(message.blocks);
  return false;
}

function normalizeStoredSession(value: unknown): ChatSession | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Partial<ChatSession>;
  if (typeof item.id !== "string" || !Array.isArray(item.messages)) return null;
  const createdAt = typeof item.createdAt === "number" ? item.createdAt : Date.now();
  const updatedAt = typeof item.updatedAt === "number" ? item.updatedAt : createdAt;
  const messages = item.messages.filter(isChatMessage);
  if (!messages.length) return null;
  return {
    id: item.id,
    name: typeof item.name === "string" && item.name.trim() ? item.name : DEFAULT_SESSION_NAME,
    createdAt,
    updatedAt,
    messages,
  };
}

function loadPersistedAiChatState(): AiChatPersistedState {
  const fallbackSession = createDefaultSession();
  if (typeof window === "undefined") {
    return {
      sessions: [fallbackSession],
      openSessionIds: [fallbackSession.id],
      activeSessionId: fallbackSession.id,
    };
  }

  try {
    const raw = window.localStorage.getItem(AI_CHAT_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    const storedSessions = Array.isArray(parsed?.sessions)
      ? parsed.sessions.map(normalizeStoredSession).filter(Boolean) as ChatSession[]
      : [];
    const sessions = storedSessions.length
      ? storedSessions.sort((a, b) => (b.updatedAt ?? b.createdAt) - (a.updatedAt ?? a.createdAt))
      : [fallbackSession];
    const sessionIds = new Set(sessions.map((session) => session.id));
    const storedOpenIds = Array.isArray(parsed?.openSessionIds)
      ? parsed.openSessionIds.filter((id: unknown): id is string => typeof id === "string" && sessionIds.has(id))
      : [];
    const hasStoredOpenIds = Array.isArray(parsed?.openSessionIds);
    const openSessionIds = hasStoredOpenIds
      ? Array.from(new Set(storedOpenIds))
      : [typeof parsed?.activeSessionId === "string" && sessionIds.has(parsed.activeSessionId)
        ? parsed.activeSessionId
        : sessions[0].id];
    const activeSessionId =
      typeof parsed?.activeSessionId === "string" && openSessionIds.includes(parsed.activeSessionId)
        ? parsed.activeSessionId
        : openSessionIds[0] ?? "";

    return {
      sessions,
      openSessionIds,
      activeSessionId,
    };
  } catch {
    return {
      sessions: [fallbackSession],
      openSessionIds: [fallbackSession.id],
      activeSessionId: fallbackSession.id,
    };
  }
}

function persistAiChatState(state: AiChatPersistedState) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(AI_CHAT_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // localStorage may be full or disabled; the chat still works in memory.
  }
}

function formatSessionTime(value: number) {
  return new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });
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
    id: item.id ?? item.item_id ?? item.title,
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
}: {
  width?: number;
  onClose?: () => void;
  mode?: "panel" | "page";
  context?: AiChatContext;
}) {
  /* ── 会话状态管理 ── */
  const [initialChatState] = useState(loadPersistedAiChatState);
  const [sessions, setSessions] = useState<ChatSession[]>(initialChatState.sessions);
  const [openSessionIds, setOpenSessionIds] = useState<string[]>(initialChatState.openSessionIds);
  const [activeSessionId, setActiveSessionId] = useState<string>(
    initialChatState.activeSessionId,
  );
  const [historyOpen, setHistoryOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const filteredSessions = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    const sortedSessions = [...sessions].sort((a, b) => (b.updatedAt ?? b.createdAt) - (a.updatedAt ?? a.createdAt));
    if (!q) return sortedSessions;
    return sortedSessions.filter((s) =>
      getSessionTitle(s).toLowerCase().includes(q),
    );
  }, [sessions, searchQuery]);

  const sessionMap = useMemo(
    () => new Map(sessions.map((session) => [session.id, session])),
    [sessions],
  );
  const openSessions = useMemo(
    () => openSessionIds.map((id) => sessionMap.get(id)).filter(Boolean) as ChatSession[],
    [openSessionIds, sessionMap],
  );
  const activeSession = sessions.find((s) => s.id === activeSessionId);

  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [sending, setSending] = useState(false);
  const [copiedMessageIndex, setCopiedMessageIndex] = useState<number | null>(null);
  const [selectedTextSnippets, setSelectedTextSnippets] = useState<SelectedTextSnippet[]>([]);
  const [selectionMenu, setSelectionMenu] = useState<SelectionMenuState | null>(null);
  const [mentions, setMentions] = useState<AiChatMention[]>([]);
  const [mentionMenuOpen, setMentionMenuOpen] = useState(false);
  const [mentionQuery, setMentionQuery] = useState("");
  const [mentionActiveIndex, setMentionActiveIndex] = useState(0);

  const mentionItems = buildMentionMenuItems(context, mentionQuery);

  function createSession() {
    const newSession = createDefaultSession();
    setSessions((prev) => [...prev, newSession]);
    setOpenSessionIds((prev) => [...prev.filter((id) => id !== newSession.id), newSession.id]);
    setActiveSessionId(newSession.id);
    setInput("");
  }

  function closeSession(id: string) {
    setOpenSessionIds((prev) => {
      const next = prev.filter((sessionId) => sessionId !== id);
      if (id === activeSessionId) {
        const currentIndex = prev.findIndex((sessionId) => sessionId === id);
        const nextActiveId = next[Math.min(currentIndex, next.length - 1)];
        if (nextActiveId) {
          setActiveSessionId(nextActiveId);
        } else {
          setActiveSessionId("");
        }
      }
      return next;
    });
  }

  function switchSession(id: string) {
    setOpenSessionIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
    setActiveSessionId(id);
    setInput("");
  }

  function openSessionFromHistory(id: string) {
    setOpenSessionIds((prev) => (prev.includes(id) ? prev : [...prev, id]));
    setActiveSessionId(id);
    setHistoryOpen(false);
  }

  function deleteSession(id: string) {
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      if (id === activeSessionId && next.length > 0) {
        const idx = prev.findIndex((s) => s.id === id);
        const targetIdx = Math.min(idx, next.length - 1);
        const nextActiveId = next[targetIdx].id;
        setActiveSessionId(nextActiveId);
        setOpenSessionIds((openIds) => {
          const filteredOpenIds = openIds.filter((sessionId) => sessionId !== id);
          return filteredOpenIds.includes(nextActiveId)
            ? filteredOpenIds
            : [...filteredOpenIds, nextActiveId];
        });
      } else {
        setOpenSessionIds((openIds) => openIds.filter((sessionId) => sessionId !== id));
      }
      if (next.length === 0) {
        const empty = createDefaultSession();
        setOpenSessionIds([empty.id]);
        setActiveSessionId(empty.id);
        return [empty];
      }
      return next;
    });
  }

  function deleteAllSessions() {
    const empty = createDefaultSession();
    setSessions([empty]);
    setOpenSessionIds([empty.id]);
    setActiveSessionId(empty.id);
  }

  function getSessionTitle(session: ChatSession) {
    const firstUser = session.messages.find((m) => m.role === "user");
    return session.name !== DEFAULT_SESSION_NAME ? session.name : firstUser?.content?.trim() || DEFAULT_SESSION_NAME;
  }

  function getSessionPreview(session: ChatSession) {
    const latest = [...session.messages].reverse().find((message) => {
      if (message.role === "user") return message.content.trim().length > 0;
      return flattenAssistantBlocksContent(message.blocks).trim().length > 0;
    });
    const preview = latest
      ? getAssistantMessagePlainText(latest)
      : DEFAULT_ASSISTANT_GREETING;
    return truncateText(normalizeSelectedText(preview), 72);
  }

  function updateLastAssistant(update: (message: AssistantChatMessage) => AssistantChatMessage) {
    if (!activeSession) return;
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== activeSessionId) return s;
        const msgs = [...s.messages];
        const last = msgs[msgs.length - 1];
        if (!last || !isAssistantMessage(last)) return s;
        msgs[msgs.length - 1] = update(last);
        return { ...s, messages: msgs, updatedAt: Date.now() };
      }),
    );
  }

  async function handleCopyAssistantMessage(content: string, index: number) {
    const value = content.trim();
    if (!value) return;
    await navigator.clipboard.writeText(value);
    setCopiedMessageIndex(index);
    window.setTimeout(() => {
      setCopiedMessageIndex((current) => (current === index ? null : current));
    }, 1200);
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
    const sessionIds = new Set(sessions.map((session) => session.id));
    setOpenSessionIds((prev) => {
      const filtered = prev.filter((id) => sessionIds.has(id));
      return filtered.length === prev.length ? prev : filtered;
    });

    if (activeSessionId && (!sessionIds.has(activeSessionId) || !openSessionIds.includes(activeSessionId))) {
      const nextActiveId = openSessionIds.find((id) => sessionIds.has(id)) ?? "";
      setActiveSessionId(nextActiveId);
    }
  }, [activeSessionId, openSessionIds, sessions]);

  useEffect(() => {
    const sessionIds = new Set(sessions.map((session) => session.id));
    persistAiChatState({
      sessions,
      openSessionIds: openSessionIds.filter((id) => sessionIds.has(id)),
      activeSessionId: sessionIds.has(activeSessionId) ? activeSessionId : sessions[0]?.id ?? "",
    });
  }, [activeSessionId, openSessionIds, sessions]);

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
  }, []);

  async function handleSend() {
    const text = input.trim();
    if (!text || !activeSession) return;

    const nextTitle = buildSessionTitle(text);
    const snippetsForRequest = selectedTextSnippets;
    const mentionsForRequest = mentions.filter((mention) => text.includes(`@${mention.label}`));
    const requestMessage = buildSelectedTextMessage(text, snippetsForRequest);
    const historyForRequest = activeSession.messages.map((m) => ({
      role: m.role,
      content: getAssistantMessagePlainText(m),
    }));

    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== activeSessionId) return s;
        return {
          ...s,
          name: s.name === DEFAULT_SESSION_NAME ? nextTitle : s.name,
          updatedAt: Date.now(),
          messages: [
            ...s.messages,
            { role: "user", content: text },
            { role: "assistant", blocks: [] },
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
      await runAssistantChatStream(
        {
          message: requestMessage,
          history: historyForRequest,
          mentions: mentionsForRequest,
        },
        (assistant) => {
          updateLastAssistant(() => assistant);
        },
      );
    } catch (err: unknown) {
      const errorMsg = err instanceof Error ? err.message : "连接失败";
      updateLastAssistant((last) => applyAssistantStreamEvent(last, {
        type: "error",
        message: last.blocks.length ? errorMsg : `抱歉，AI 服务出错: ${errorMsg}`,
      }));
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
        <>
        <button
          className="ai-chat-history-mask"
          type="button"
          aria-label="关闭历史会话"
          onClick={() => setHistoryOpen(false)}
        />
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
                          <span className="ai-chat-history-item-main">
                            <span className="ai-chat-history-item-head">
                              <span className="ai-chat-history-item-title">
                                {getSessionTitle(session)}
                              </span>
                              <span className="ai-chat-history-item-time">
                                {formatSessionTime(session.updatedAt ?? session.createdAt)}
                              </span>
                            </span>
                            <span className="ai-chat-history-item-preview">
                              {getSessionPreview(session)}
                            </span>
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
        </>
      ) : null}

          <nav className="ai-chat-tab-bar" aria-label="会话标签">
            {openSessions.map((session) => (
              <button
                key={session.id}
                className={`ai-chat-tab${
                  session.id === activeSessionId ? " active" : ""
                }`}
                onClick={() => switchSession(session.id)}
                title={getSessionTitle(session)}
                type="button"
              >
                <span className="ai-chat-tab-label">{getSessionTitle(session)}</span>
                <span
                  className="ai-chat-tab-close"
                  onClick={(e) => {
                    e.stopPropagation();
                    closeSession(session.id);
                  }}
                  role="button"
                  aria-label={`关闭 ${getSessionTitle(session)}`}
                >
                  <X size={12} />
                </span>
              </button>
            ))}
          </nav>

          <div
            className="ai-chat-messages"
            ref={listRef}
            onMouseUp={handleSelectionEnd}
            onScroll={closeSelectionMenu}
          >
            {!activeSession ? (
              <div className="ai-chat-empty-session">
                从历史恢复会话，或新建对话继续。
              </div>
            ) : null}
            {activeSession?.messages.map((msg, i) => (
              <div className={`ai-chat-message ${msg.role}`} data-message-index={i} key={i}>
                {isAssistantMessage(msg) ? (
                  <>
                    <div className="ai-chat-assistant-header">
                      <span className="ai-chat-avatar">
                        <Sparkles size={13} />
                      </span>
                      <strong>AI 助手</strong>
                    </div>
                    <div className="ai-chat-assistant-block">
                      <AssistantMessageBody message={msg} />
                    </div>
                    {flattenAssistantBlocksContent(msg.blocks).trim() ? (
                      <div className="ai-chat-message-toolbar">
                        <button
                          type="button"
                          onClick={() => void handleCopyAssistantMessage(
                            flattenAssistantBlocksContent(msg.blocks),
                            i,
                          )}
                          aria-label={copiedMessageIndex === i ? "已复制" : "复制回复"}
                          title={copiedMessageIndex === i ? "已复制" : "复制回复"}
                        >
                          {copiedMessageIndex === i ? <Check size={14} /> : <Copy size={14} />}
                        </button>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <div className="ai-chat-bubble">
                    <div className="ai-chat-content">{msg.content}</div>
                  </div>
                )}
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
                placeholder={activeSession ? "输入消息…" : "先新建或从历史恢复会话"}
                value={input}
                onChange={handleInputChange}
                onKeyDown={handleKeyDown}
                onClick={(event) => syncMentionMenu(input, (event.target as HTMLTextAreaElement).selectionStart)}
                disabled={!activeSession}
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
                  disabled={!activeSession || !input.trim() || sending}
                  aria-label="发送"
                >
                  <Send size={16} />
                </button>
              </div>
            </div>
          </div>
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
