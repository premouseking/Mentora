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
import {
  loadStoredConversations,
  saveStoredConversations,
  type AssistantAttachment,
  type ChatMessage,
  type ConversationSnapshot,
} from "./assistantStorage";
import { parseAssistantStreamChunk, type ChatStreamEvent } from "./assistantStream";

interface AssistantPanelProps {
  width: number;
  onClose: () => void;
}

const CONVERSATION_STORAGE_KEY = "mentora-assistant-conversations-v1";

const MODEL_OPTIONS = [
  { id: "auto", label: "Auto", hint: "根据任务自动路由" },
  { id: "balanced", label: "Balanced", hint: "默认导师模型" },
  { id: "fast", label: "Fast", hint: "快速答疑" },
];

const INITIAL_MESSAGE: ChatMessage = {
  role: "assistant",
  content: "你好！我是 Mentora AI 助手。关于你的学习课程，有什么我可以帮你的吗？",
};

function createId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createConversation(): ConversationSnapshot {
  return {
    id: createId("conv"),
    title: "新对话",
    updatedAt: Date.now(),
    messages: [INITIAL_MESSAGE],
  };
}

function loadConversations(): ConversationSnapshot[] {
  return loadStoredConversations(localStorage, CONVERSATION_STORAGE_KEY);
}

function saveConversations(conversations: ConversationSnapshot[]) {
  saveStoredConversations(localStorage, CONVERSATION_STORAGE_KEY, conversations);
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

export function AssistantPanel({ width, onClose }: AssistantPanelProps) {
  const [conversations, setConversations] = useState<ConversationSnapshot[]>(() => {
    const loaded = loadConversations();
    return loaded.length ? loaded : [createConversation()];
  });
  const [activeConversationId, setActiveConversationId] = useState(() => conversations[0]?.id ?? "");
  const [activeTab, setActiveTab] = useState<"chat" | "history">("chat");
  const [selectedModel, setSelectedModel] = useState(MODEL_OPTIONS[0].id);
  const [input, setInput] = useState("");
  const [attachments, setAttachments] = useState<AssistantAttachment[]>([]);
  const [sending, setSending] = useState(false);
  const [copiedMessageId, setCopiedMessageId] = useState<number | null>(null);
  const imageInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const messageListRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const activeConversation = useMemo(() => {
    return conversations.find((conversation) => conversation.id === activeConversationId) ?? conversations[0];
  }, [activeConversationId, conversations]);

  const messages = activeConversation?.messages ?? [INITIAL_MESSAGE];
  const selectedModelInfo = MODEL_OPTIONS.find((model) => model.id === selectedModel) ?? MODEL_OPTIONS[0];
  const canSend = Boolean(input.trim() || attachments.length) && !sending;

  useEffect(() => {
    saveConversations(conversations);
  }, [conversations]);

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
      const current = prev.find((conversation) => conversation.id === activeConversationId) ?? prev[0] ?? createConversation();
      const nextConversation = updater(current);
      const exists = prev.some((conversation) => conversation.id === nextConversation.id);
      const next = exists
        ? prev.map((conversation) => (conversation.id === nextConversation.id ? nextConversation : conversation))
        : [nextConversation, ...prev];
      return next.sort((a, b) => b.updatedAt - a.updatedAt);
    });
  }

  function updateLastAssistant(update: (message: ChatMessage) => ChatMessage) {
    updateActiveConversation((conversation) => {
      const nextMessages = [...conversation.messages];
      const last = nextMessages[nextMessages.length - 1];
      if (!last || last.role !== "assistant") return conversation;
      nextMessages[nextMessages.length - 1] = update(last);
      return {
        ...conversation,
        updatedAt: Date.now(),
        messages: nextMessages,
      };
    });
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
    const conversation = createConversation();
    setConversations((prev) => [conversation, ...prev]);
    setActiveConversationId(conversation.id);
    setActiveTab("chat");
    setInput("");
    setAttachments([]);
  }

  async function handleCopyMessage(content: string, index: number) {
    await navigator.clipboard.writeText(content);
    setCopiedMessageId(index);
    window.setTimeout(() => setCopiedMessageId(null), 1200);
  }

  function handleStopGeneration() {
    abortControllerRef.current?.abort();
  }

  function applyStreamEvent(data: ChatStreamEvent) {
    if (data.type === "chunk") {
      updateLastAssistant((last) => ({ ...last, content: last.content + data.content }));
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
      updateLastAssistant((last) => ({
        ...last,
        content: last.content || `错误：${data.message}`,
      }));
    }
  }

  async function handleSend() {
    const text = input.trim();
    if ((!text && !attachments.length) || sending) return;
    const requestText = text || "请根据我上传的附件进行分析。";
    const outgoingAttachments = attachments;
    const userMessage: ChatMessage = {
      role: "user",
      content: requestText,
      attachments: outgoingAttachments,
    };
    const assistantPlaceholder: ChatMessage = { role: "assistant", content: "" };

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
      const resp = await fetch("/api/chat/stream/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: controller.signal,
        body: JSON.stringify({
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
        }),
      });

      if (!resp.ok) {
        const errorText = await resp.text();
        throw new Error(errorText || `HTTP ${resp.status}`);
      }
      if (!resp.body) throw new Error("响应流为空");

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const parsed = parseAssistantStreamChunk(decoder.decode(value, { stream: true }), buffer);
        buffer = parsed.buffer;
        parsed.events.forEach(applyStreamEvent);
      }
      parseAssistantStreamChunk("\n", buffer).events.forEach(applyStreamEvent);
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
          <strong>AI 助手</strong>
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
                      {message.content ? (
                        <AssistantMarkdown content={message.content} />
                      ) : (
                        <div className="ai-chat-loading">正在生成...</div>
                      )}
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
                      {message.citations?.length ? (
                        <div className="ai-chat-citations" aria-label="引用来源">
                          {message.citations.map((citation, citationIndex) => (
                            <div className="ai-chat-citation" key={`${citation.evidence_id ?? "source"}-${citationIndex}`}>
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
                placeholder="输入消息..."
                value={input}
                rows={2}
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
