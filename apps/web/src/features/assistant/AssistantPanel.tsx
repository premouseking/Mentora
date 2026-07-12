import { useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  Copy,
  FileText,
  History,
  Image,
  Paperclip,
  Plus,
  Send,
  Sparkles,
  Square,
  X,
} from "lucide-react";

import { AssistantMarkdown } from "./AssistantMarkdown";
import { ChatCitationList } from "./ChatCitationList";
import type { AiChatContext, CourseAgentBinding } from "./AiChatPanel";
import {
  getCourseAgentSession,
  listCourseAgentSessions,
  streamCourseAgentMessage,
  type CourseAgentStreamEvent,
} from "../../services/courseAgentApi";
import {
  loadStoredConversations,
  saveStoredConversations,
  type AssistantAttachment,
  type ChatMessage,
  type ConversationSnapshot,
} from "./assistantStorage";
import {
  applyStreamEventToConversation,
  isWelcomeOnlyConversation,
  updateConversationById,
  updateLastAssistantInConversation,
} from "./assistantPanelStream";
import { consumeAssistantStream, type ChatStreamEvent } from "./assistantStream";
import { postJsonStream } from "../../services/streamClient";

interface AssistantPanelProps {
  width: number;
  onClose: () => void;
  courseBinding?: CourseAgentBinding;
  context?: AiChatContext;
}

const CONVERSATION_STORAGE_KEY = "mentora-assistant-conversations-v1";

function buildWelcomeMessage(courseBinding?: CourseAgentBinding): ChatMessage {
  if (courseBinding) {
    const title = courseBinding.courseTitle || courseBinding.courseGoal || "当前课程";
    return {
      role: "assistant",
      content: `你好！我是「${title}」的 AI 助教。我可以结合课程资料、学习方案和当前任务为你答疑。`,
    };
  }
  return {
    role: "assistant",
    content: "你好！我是 Mentora AI 助手。关于你的学习课程，有什么我可以帮你的吗？",
  };
}

function conversationStorageKey(courseBinding?: CourseAgentBinding) {
  if (courseBinding?.courseId) {
    return `mentora-assistant-conversations-course-${courseBinding.courseId}-v1`;
  }
  return CONVERSATION_STORAGE_KEY;
}

const MODEL_OPTIONS = [
  { id: "auto", label: "Auto", hint: "根据任务自动路由" },
  { id: "balanced", label: "Balanced", hint: "默认导师模型" },
  { id: "fast", label: "Fast", hint: "快速答疑" },
];

const INITIAL_MESSAGE: ChatMessage = buildWelcomeMessage();

function createId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createConversation(courseBinding?: CourseAgentBinding): ConversationSnapshot {
  return {
    id: createId("conv"),
    title: "新对话",
    updatedAt: Date.now(),
    agentSessionId: null,
    messages: [buildWelcomeMessage(courseBinding)],
  };
}

function loadConversations(storageKey: string): ConversationSnapshot[] {
  return loadStoredConversations(localStorage, storageKey);
}

function saveConversations(storageKey: string, conversations: ConversationSnapshot[]) {
  saveStoredConversations(localStorage, storageKey, conversations);
}

function buildConversationTitle(messages: ChatMessage[]) {
  const firstUser = messages.find((message) => message.role === "user" && message.content.trim());
  if (!firstUser) return "新对话";
  const normalized = firstUser.content.replace(/\s+/g, " ").trim();
  return normalized.length > 26 ? `${normalized.slice(0, 26)}...` : normalized;
}

function formatTime(timestamp: number) {
  const date = new Date(timestamp);
  return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours().toString().padStart(2, "0")}:${date
    .getMinutes()
    .toString()
    .padStart(2, "0")}`;
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (typeof reader.result === "string") resolve(reader.result);
      else reject(new Error("文件读取失败"));
    };
    reader.onerror = () => reject(reader.error ?? new Error("文件读取失败"));
    reader.readAsDataURL(file);
  });
}

export function AssistantPanel({
  width,
  onClose,
  courseBinding,
  context,
}: AssistantPanelProps) {
  const storageKey = conversationStorageKey(courseBinding);
  const [conversations, setConversations] = useState<ConversationSnapshot[]>(() => {
    const loaded = loadConversations(storageKey);
    return loaded.length ? loaded : [createConversation(courseBinding)];
  });
  const [activeConversationId, setActiveConversationId] = useState(() => conversations[0]?.id ?? "");
  const [activeTab, setActiveTab] = useState<"chat" | "history">("chat");
  const [selectedModel, setSelectedModel] = useState(MODEL_OPTIONS[0].id);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<AssistantAttachment[]>([]);
  const [sending, setSending] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<number | null>(null);
  const [courseSessionsLoaded, setCourseSessionsLoaded] = useState(false);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const streamingConversationIdRef = useRef<string | null>(null);
  const sendingRef = useRef(false);
  const activeConversationIdRef = useRef(activeConversationId);

  useEffect(() => {
    sendingRef.current = sending;
  }, [sending]);

  useEffect(() => {
    activeConversationIdRef.current = activeConversationId;
  }, [activeConversationId]);

  const activeConversation = useMemo(() => {
    return conversations.find((conversation) => conversation.id === activeConversationId) ?? conversations[0];
  }, [activeConversationId, conversations]);

  const messages = activeConversation?.messages ?? [buildWelcomeMessage(courseBinding)];
  const selectedModelInfo = MODEL_OPTIONS.find((model) => model.id === selectedModel) ?? MODEL_OPTIONS[0];
  const courseSessionsReady = !courseBinding || courseSessionsLoaded;
  const canSend = Boolean(input.trim() || attachments.length) && !sending && courseSessionsReady;

  useEffect(() => {
    setCourseSessionsLoaded(false);
    const loaded = loadConversations(storageKey);
    setConversations(loaded.length ? loaded : [createConversation(courseBinding)]);
    setActiveConversationId(loaded[0]?.id ?? "");
    setActiveTab("chat");
    setInput("");
    setAttachments([]);
  }, [storageKey, courseBinding?.courseId]);

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
        if (sendingRef.current || streamingConversationIdRef.current) {
          setCourseSessionsLoaded(true);
          return;
        }

        const restored: ConversationSnapshot = {
          id: createId("conv"),
          agentSessionId: detail.id,
          title: detail.title || "新对话",
          updatedAt: detail.updated_at ? Date.parse(detail.updated_at) : Date.now(),
          messages: detail.messages.length > 0
            ? detail.messages.map((message) => ({
                role: message.role,
                content: message.content,
                citations: message.citations,
              }))
            : [buildWelcomeMessage(courseBinding)],
        };

        const others: ConversationSnapshot[] = items.slice(1).map((item) => ({
          id: createId("conv"),
          agentSessionId: item.id,
          title: item.title || "新对话",
          updatedAt: item.updated_at ? Date.parse(item.updated_at) : Date.now(),
          messages: [buildWelcomeMessage(courseBinding)],
        }));

        let shouldActivateRestored = false;
        setConversations((prev) => {
          const active = prev.find((conversation) => conversation.id === activeConversationIdRef.current);
          if (!isWelcomeOnlyConversation(active)) {
            const merged = [restored, ...others];
            const serverAgentIds = new Set(
              merged.map((conversation) => conversation.agentSessionId).filter(Boolean),
            );
            const localOnly = prev.filter(
              (conversation) => !conversation.agentSessionId || !serverAgentIds.has(conversation.agentSessionId),
            );
            return [...merged, ...localOnly].sort((left, right) => right.updatedAt - left.updatedAt);
          }
          shouldActivateRestored = true;
          return [restored, ...others];
        });

        if (shouldActivateRestored) {
          setActiveConversationId(restored.id);
        }
      } catch {
        // 恢复失败时保留本地空会话
      } finally {
        if (!cancelled) setCourseSessionsLoaded(true);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [courseBinding?.courseId, courseSessionsLoaded]);

  useEffect(() => {
    saveConversations(storageKey, conversations);
  }, [conversations, storageKey]);

  useEffect(() => {
    messageListRef.current?.scrollTo({
      top: messageListRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages.length, messages[messages.length - 1]?.content]);

  useEffect(() => {
    return () => abortControllerRef.current?.abort();
  }, []);

  function updateActiveConversation(updater: (conversation: ConversationSnapshot) => ConversationSnapshot) {
    setConversations((prev) => {
      const current = prev.find((conversation) => conversation.id === activeConversationId);
      if (!current) return prev;
      return updateConversationById(prev, current.id, updater);
    });
  }

  function updateStreamingConversation(updater: (conversation: ConversationSnapshot) => ConversationSnapshot) {
    const targetId = streamingConversationIdRef.current;
    if (!targetId) return;
    setConversations((prev) => updateConversationById(prev, targetId, updater));
  }

  function updateLastAssistant(update: (message: ChatMessage) => ChatMessage) {
    updateStreamingConversation((conversation) => updateLastAssistantInConversation(conversation, update));
  }

  async function addFiles(files: FileList | File[] | null, preferredKind?: "image" | "file") {
    if (!files) return;
    const next = await Promise.all(
      Array.from(files).map(async (file) => {
        const kind = preferredKind ?? (file.type.startsWith("image/") ? "image" : "file");
        return {
          id: createId("att"),
          name: file.name,
          kind,
          mimeType: file.type || "application/octet-stream",
          size: file.size,
          dataUrl: kind === "image" ? await readFileAsDataUrl(file) : undefined,
        } satisfies AssistantAttachment;
      }),
    );
    setAttachments((prev) => [...prev, ...next]);
  }

  function removeAttachment(id: string) {
    setAttachments((prev) => prev.filter((attachment) => attachment.id !== id));
  }

  function handleNewConversation() {
    const conversation = createConversation(courseBinding);
    setConversations((prev) => [conversation, ...prev]);
    setActiveConversationId(conversation.id);
    setActiveTab("chat");
    setInput("");
    setAttachments([]);
  }

  async function hydrateCourseConversation(conversationId: string) {
    if (!courseBinding?.courseId) return;
    const target = conversations.find((conversation) => conversation.id === conversationId);
    if (!target?.agentSessionId) return;
    const hasUserMessage = target.messages.some((message) => message.role === "user");
    if (hasUserMessage) return;

    try {
      const detail = await getCourseAgentSession(courseBinding.courseId, target.agentSessionId);
      setConversations((prev) =>
        prev.map((conversation) => {
          if (conversation.id !== conversationId) return conversation;
          return {
            ...conversation,
            title: detail.title || conversation.title,
            messages: detail.messages.length > 0
              ? detail.messages.map((message) => ({
                  role: message.role,
                  content: message.content,
                  citations: message.citations,
                }))
              : conversation.messages,
          };
        }),
      );
    } catch {
      // 历史加载失败时保留当前占位消息
    }
  }

  async function handleCopyMessage(content: string, index: number) {
    await navigator.clipboard.writeText(content);
    setCopiedMessageId(index);
    window.setTimeout(() => setCopiedMessageId(null), 1200);
  }

  function handleStopGeneration() {
    abortControllerRef.current?.abort();
  }

  function applyStreamEvent(data: ChatStreamEvent | CourseAgentStreamEvent) {
    const targetId = streamingConversationIdRef.current;
    if (!targetId) return;

    setConversations((prev) =>
      updateConversationById(prev, targetId, (conversation) => applyStreamEventToConversation(conversation, data)),
    );
  }

  async function handleSend() {
    const text = input.trim();
    if ((!text && !attachments.length) || sending || !courseSessionsReady) return;
    const requestText = text || "请根据我上传的附件进行分析。";
    const outgoingAttachments = attachments;
    const userMessage: ChatMessage = {
      role: "user",
      content: requestText,
      attachments: outgoingAttachments,
    };
    const assistantPlaceholder: ChatMessage = { role: "assistant", content: "" };
    const conversationId = activeConversationId;
    const agentSessionIdAtSend = activeConversation?.agentSessionId;

    streamingConversationIdRef.current = conversationId;
    updateActiveConversation((conversation) => {
      const nextMessages = [...conversation.messages, userMessage, assistantPlaceholder];
      return {
        ...conversation,
        title: buildConversationTitle(nextMessages),
        updatedAt: Date.now(),
        messages: nextMessages,
      };
    });
    setInput("");
    setAttachments([]);
    setSending(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      if (courseBinding) {
        await streamCourseAgentMessage({
          courseId: courseBinding.courseId,
          message: requestText,
          agentSessionId: agentSessionIdAtSend,
          currentTaskId: courseBinding.currentTaskId,
          currentSourceVersionId: courseBinding.currentSourceVersionId ?? context?.selectedFileId,
          signal: controller.signal,
          onEvent: applyStreamEvent,
        });
      } else {
        const body = await postJsonStream(
          "/api/chat/stream/",
          {
            message: requestText,
            model_id: selectedModel,
            attachments: outgoingAttachments.map((attachment) => ({
              name: attachment.name,
              kind: attachment.kind,
              mime_type: attachment.mimeType,
              size: attachment.size,
              data_url: attachment.dataUrl,
            })),
            history: messages.map((message) => ({
              role: message.role,
              content: message.content,
            })),
          },
          { signal: controller.signal },
        );
        await consumeAssistantStream(body, applyStreamEvent);
      }
    } catch (error) {
      if (error instanceof Error && error.name === "AbortError") {
        updateLastAssistant((last) => ({
          ...last,
          content: last.content || "已停止生成。",
        }));
        return;
      }
      const message = error instanceof Error ? error.message : "连接失败";
      updateLastAssistant((last) => ({
        ...last,
        content: last.content || `抱歉，AI 服务出错：${message}`,
      }));
    } finally {
      streamingConversationIdRef.current = null;
      abortControllerRef.current = null;
      setSending(false);
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  }

  return (
    <div className="ai-chat-panel" style={{ width }} role="complementary" aria-label="AI 对话面板">
      <header className="ai-chat-header">
        <div className="ai-chat-header-title">
          <span className="ai-chat-header-icon">
            <Sparkles size={16} />
          </span>
          <div className="ai-chat-header-main">
            <strong>AI 助手</strong>
            {courseBinding ? (
              <div className="ai-chat-course-tags">
                <span className="ai-chat-course-tag">
                  {courseBinding.courseTitle || courseBinding.courseGoal || "当前课程"}
                </span>
                {activeConversation?.agentSessionId ? (
                  <span className="ai-chat-course-tag bound">已绑定课程</span>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
        <div className="ai-chat-header-actions">
          <button
            className={activeTab === "chat" ? "active" : ""}
            type="button"
            onClick={() => setActiveTab("chat")}
          >
            对话
          </button>
          <button
            className={activeTab === "history" ? "active" : ""}
            type="button"
            onClick={() => setActiveTab("history")}
          >
            <History size={14} />
            历史
          </button>
          <button className="ai-chat-icon-button" type="button" onClick={handleNewConversation} aria-label="新建对话">
            <Plus size={16} />
          </button>
          <button className="ai-chat-close" type="button" onClick={onClose} aria-label="关闭 AI 面板">
            <X size={18} />
          </button>
        </div>
      </header>

      {activeTab === "history" ? (
        <div className="ai-chat-history-list">
          {conversations.map((conversation) => (
            <button
              key={conversation.id}
              className={`ai-chat-history-item${conversation.id === activeConversationId ? " active" : ""}`}
              type="button"
              onClick={() => {
                setActiveConversationId(conversation.id);
                setActiveTab("chat");
                void hydrateCourseConversation(conversation.id);
              }}
            >
              <strong>{conversation.title}</strong>
              <span>{formatTime(conversation.updatedAt)}</span>
              <p>{conversation.messages.find((message) => message.role === "assistant" && message.content)?.content}</p>
            </button>
          ))}
        </div>
      ) : (
        <>
          <div className="ai-chat-messages" ref={messageListRef}>
            {messages.map((message, index) => (
              <div className={`ai-chat-message ${message.role}`} key={`${message.role}-${index}`}>
                {message.role === "assistant" ? (
                  <>
                    <div className="ai-chat-assistant-header">
                      <span className="ai-chat-avatar">
                        <Sparkles size={13} />
                      </span>
                      <strong>AI 助手</strong>
                    </div>
                    <div className="ai-chat-assistant-block">
                      {message.statuses?.length ? (
                        <div className="ai-chat-status-list">
                          {message.statuses.map((status, statusIndex) => (
                            <div
                              className={`ai-chat-status ${status.success === false ? "failed" : ""}`}
                              key={`${status.event}-${statusIndex}`}
                            >
                              <span className="ai-chat-status-dot" />
                              <span>{status.message}</span>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      {message.content ? (
                        <AssistantMarkdown content={message.content} />
                      ) : (
                        <div className="ai-chat-loading">正在生成...</div>
                      )}
                      {message.citations?.length ? (
                        <ChatCitationList citations={message.citations} />
                      ) : null}
                    </div>
                    {message.content ? (
                      <div className="ai-chat-message-toolbar">
                        <button
                          type="button"
                          onClick={() => void handleCopyMessage(message.content, index)}
                          aria-label={copiedMessageId === index ? "已复制" : "复制回复"}
                          title={copiedMessageId === index ? "已复制" : "复制回复"}
                        >
                          {copiedMessageId === index ? <Check size={14} /> : <Copy size={14} />}
                        </button>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <div className="ai-chat-bubble">
                  {message.content ? (
                    <div className="ai-chat-content">{message.content}</div>
                  ) : (
                    <div className="ai-chat-loading">正在生成...</div>
                  )}
                  {message.attachments?.length ? (
                    <div className="ai-chat-message-attachments">
                      {message.attachments.map((attachment) => (
                        <span key={attachment.id}>
                          {attachment.kind === "image" ? <Image size={12} /> : <FileText size={12} />}
                          {attachment.name}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  </div>
                )}
              </div>
            ))}
          </div>

          <div className="ai-chat-input-area">
            {attachments.length ? (
              <div className="ai-chat-attachment-strip">
                {attachments.map((attachment) => (
                  <span key={attachment.id}>
                    {attachment.kind === "image" ? <Image size={13} /> : <FileText size={13} />}
                    {attachment.name}
                    <button type="button" onClick={() => removeAttachment(attachment.id)} aria-label="移除附件">
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            ) : null}
            <div className="ai-chat-input-row">
              <textarea
                className="ai-chat-input"
                placeholder={courseSessionsReady ? "输入消息..." : "正在恢复会话…"}
                value={input}
                rows={2}
                disabled={!courseSessionsReady}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleKeyDown}
              />
              <div className="ai-chat-composer-footer">
              <div className="ai-chat-input-tools">
                <button type="button" onClick={() => imageInputRef.current?.click()} aria-label="添加图片">
                  <Image size={16} />
                </button>
                <button type="button" onClick={() => fileInputRef.current?.click()} aria-label="添加附件">
                  <Paperclip size={16} />
                </button>
                <select
                  aria-label="选择模型"
                  value={selectedModel}
                  onChange={(event) => setSelectedModel(event.target.value)}
                  title={selectedModelInfo.hint}
                >
                  {MODEL_OPTIONS.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.label}
                    </option>
                  ))}
                </select>
              </div>
              <button
                className={`ai-chat-send${sending ? " stop" : ""}`}
                type="button"
                onClick={sending ? handleStopGeneration : () => void handleSend()}
                disabled={!canSend && !sending}
                aria-label={sending ? "停止生成" : "发送"}
              >
                {sending ? <Square size={14} /> : <Send size={16} />}
              </button>
              </div>
            </div>
            <input
              ref={imageInputRef}
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={(event) => {
                void addFiles(event.target.files, "image");
                event.target.value = "";
              }}
            />
            <input
              ref={fileInputRef}
              type="file"
              multiple
              hidden
              onChange={(event) => {
                void addFiles(event.target.files, "file");
                event.target.value = "";
              }}
            />
          </div>
        </>
      )}
    </div>
  );
}
