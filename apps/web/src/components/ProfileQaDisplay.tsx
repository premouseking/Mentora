import { Loader, MessageCircleQuestion, Sparkles } from "lucide-react";
import type { ReactNode } from "react";

import type { CourseInfoItem } from "./CourseCreationContext";

export interface QaDisplayItem {
  key: string;
  title: string;
  value: string;
  source?: string;
  editable?: boolean;
}

interface QaPairCardProps {
  question: string;
  answer?: string;
  source?: string;
  variant?: "completed" | "active" | "summary";
  children?: ReactNode;
}

/** Single Q→A card — completed pairs or the active question shell. */
export function QaPairCard({
  question,
  answer,
  source,
  variant = "completed",
  children,
}: QaPairCardProps) {
  const isActive = variant === "active";
  const isSummary = variant === "summary";

  return (
    <article className={`qa-pair-card${isActive ? " qa-pair-card--active" : ""}${isSummary ? " qa-pair-card--summary" : ""}`}>
      <div className="qa-pair-question">
        <span className="qa-pair-badge" aria-hidden="true">
          {isActive ? <Sparkles size={12} /> : <MessageCircleQuestion size={12} />}
        </span>
        <p className="qa-pair-q-text">{question}</p>
      </div>
      {answer && (
        <div className="qa-pair-answer">
          <span className="qa-pair-a-label">答</span>
          <p className="qa-pair-a-text">{answer}</p>
          {source && <span className="qa-pair-source">{source}</span>}
        </div>
      )}
      {children}
    </article>
  );
}

interface ProfileQaListProps {
  items: QaDisplayItem[];
  compact?: boolean;
  editing?: boolean;
  onValueChange?: (key: string, value: string) => void;
}

/** Renders profile / info items as stacked Q→A cards. */
export function ProfileQaList({
  items,
  compact = false,
  editing = false,
  onValueChange,
}: ProfileQaListProps) {
  const visible = items.filter((item) => item.value.trim() || (editing && item.editable !== false));
  if (visible.length === 0) return null;

  return (
    <div className={`profile-qa-list${compact ? " profile-qa-list--compact" : ""}`}>
      {visible.map((item) => (
        <QaPairCard
          key={item.key}
          question={item.title}
          answer={
            editing && item.editable !== false && onValueChange ? undefined : item.value
          }
          source={item.source}
          variant="completed"
        >
          {editing && item.editable !== false && onValueChange && (
            <div className="qa-pair-answer qa-pair-answer--edit">
              <span className="qa-pair-a-label">答</span>
              <input
                className="qa-pair-edit-input"
                value={item.value}
                onChange={(e) => onValueChange(item.key, e.target.value)}
              />
            </div>
          )}
        </QaPairCard>
      ))}
    </div>
  );
}

export function courseInfoToQaItems(items: CourseInfoItem[]): QaDisplayItem[] {
  return items.map((item) => ({
    key: item.key,
    title: item.title,
    value: item.value,
    source: item.source,
  }));
}

interface InquiryStageProps {
  history: Array<{ question: string; answer: string }>;
  currentQuestion: {
    text: string;
    type: "single_choice" | "multi_choice" | "free_text";
    options: string[];
    guidance: string;
  } | null;
  loading: boolean;
  summary: string | null;
  answer: string;
  onAnswerChange: (value: string) => void;
  onSubmit: (answer?: string) => void;
  onSkip: () => void;
  onConfirm: () => void;
}

/** Full inquiry step — distinct Q&A thread with active question. */
export function InquiryStage({
  history,
  currentQuestion,
  loading,
  summary,
  answer,
  onAnswerChange,
  onSubmit,
  onSkip,
  onConfirm,
}: InquiryStageProps) {
  return (
    <div className="inquiry-stage">
      <header className="inquiry-stage-header">
        <div className="inquiry-stage-title">
          <span className="inquiry-stage-icon" aria-hidden="true">
            <Sparkles size={18} />
          </span>
          <div>
            <h2>AI 追问</h2>
            <p>通过几个简短问题，帮你建立更精准的学习档案</p>
          </div>
        </div>
        {!loading && !summary && (
          <button className="inquiry-stage-skip" onClick={onSkip} type="button">
            跳过追问
          </button>
        )}
      </header>

      <div className="inquiry-stage-body">
        <div className="inquiry-thread">
          {history.map((entry, i) => (
            <QaPairCard
              key={`${entry.question}-${i}`}
              question={entry.question}
              answer={entry.answer}
              source="你的回答"
              variant="completed"
            />
          ))}

          {loading && (
            <div className="inquiry-stage-loading">
              <Loader size={24} className="spin" />
              <span>{history.length === 0 ? "AI 正在分析你的学习目标…" : "AI 正在整理下一个问题…"}</span>
            </div>
          )}

          {summary && (
            <div className="inquiry-stage-complete">
              <QaPairCard question="信息收集完成" answer={summary} variant="summary" />
              <button className="button primary inquiry-stage-confirm" onClick={onConfirm} type="button">
                确认并进入试生成
              </button>
            </div>
          )}

          {currentQuestion && !summary && !loading && (
            <QaPairCard question={currentQuestion.text} variant="active">
              {currentQuestion.type === "free_text" ? (
                <div className="inquiry-active-input">
                  <textarea
                    className="inquiry-active-textarea"
                    onChange={(e) => onAnswerChange(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        onSubmit();
                      }
                    }}
                    placeholder="输入你的回答…"
                    rows={3}
                    value={answer}
                  />
                  <button
                    className="button primary"
                    disabled={!answer.trim()}
                    onClick={() => onSubmit()}
                    type="button"
                  >
                    提交回答
                  </button>
                </div>
              ) : (
                <div className="inquiry-active-options">
                  {currentQuestion.options.map((opt) => (
                    <button
                      className="inquiry-active-option"
                      key={opt}
                      onClick={() => onSubmit(opt)}
                      type="button"
                    >
                      {opt}
                    </button>
                  ))}
                </div>
              )}
              {currentQuestion.guidance && (
                <p className="inquiry-active-guidance">{currentQuestion.guidance}</p>
              )}
            </QaPairCard>
          )}
        </div>
      </div>
    </div>
  );
}
