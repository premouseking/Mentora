import { useState } from "react";
import { Check, X, ArrowRight, ChevronUp } from "lucide-react";
import type { QuizQuestion } from "../data/quiz";

export function QuizPanel({
  question,
  onClose,
}: {
  question: QuizQuestion;
  onClose: () => void;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);

  function handleSelect(idx: number) {
    if (submitted) return;
    setSelected(idx);
  }

  function handleSubmit() {
    if (selected === null) return;
    setSubmitted(true);
  }

  function handleRetry() {
    setSelected(null);
    setSubmitted(false);
  }

  const isCorrect = submitted && selected === question.answer;

  return (
    <div className="quiz-panel">
      {/* Top hint bar — stop pointer events from reaching overlay swipe */}
      <div className="quiz-swipe-hint" onPointerDown={(e) => e.stopPropagation()}>
        <div className="quiz-swipe-hint-left">
          <ChevronUp size={14} />
          <span>上划收起</span>
          <span className="quiz-hint-sep">|</span>
          <kbd className="quiz-kbd">Tab</kbd>
          <span>回顾一下</span>
        </div>
        <button className="quiz-hint-close" onClick={onClose} title="关闭">
          <X size={14} />
        </button>
      </div>

      <div className="quiz-header">
        <span className="quiz-topic">{question.topic}</span>
      </div>

      <div className="quiz-body">
        <div className="quiz-progress">
          <span>第 1 题 / 共 6 题</span>
          <div className="quiz-progress-bar">
            <div className="quiz-progress-fill" style={{ width: "16%" }} />
          </div>
        </div>

        <h2 className="quiz-question">{question.question}</h2>

        <div className="quiz-options">
          {question.options.map((opt, idx) => {
            let cls = "quiz-option";
            if (selected === idx) cls += " selected";
            if (submitted) {
              if (idx === question.answer) cls += " correct";
              else if (idx === selected) cls += " wrong";
            }
            return (
              <button
                key={idx}
                className={cls}
                disabled={submitted}
                onClick={() => handleSelect(idx)}
              >
                <span className="quiz-option-letter">
                  {["A", "B", "C", "D"][idx]}
                </span>
                <span>{opt.replace(/^[A-D]\.\s*/, "")}</span>
                {submitted && idx === question.answer && (
                  <Check size={16} className="quiz-option-icon correct" />
                )}
                {submitted && idx === selected && idx !== question.answer && (
                  <X size={16} className="quiz-option-icon wrong" />
                )}
              </button>
            );
          })}
        </div>

        {submitted && (
          <div className={`quiz-feedback ${isCorrect ? "correct" : "wrong"}`}>
            {isCorrect ? (
              <p>✓ 回答正确！组号 = (主存块号) mod (Cache 组数) = 4 mod 8 = 4。但因为题目问的是 2 路组相联，每个主存块号为 129/32 = 4，Cache 组数为 16/2 = 8，所以是 4 mod 8 = 4，对应选项 C。</p>
            ) : (
              <p>✗ 回答错误。正确答案是 C。组号 = (主存块号) mod (Cache 组数)，主存块号 = 129/32 = 4（向下取整），Cache 组数 = 16/2 = 8，4 mod 8 = 4。</p>
            )}
            <div className="quiz-feedback-actions">
              {!isCorrect && (
                <button className="button compact secondary" onClick={handleRetry}>
                  重新作答
                </button>
              )}
              <button className="button compact primary">
                下一题 <ArrowRight size={14} />
              </button>
            </div>
          </div>
        )}
      </div>

      {!submitted && (
        <div className="quiz-footer">
          <button
            className="button compact primary"
            disabled={selected === null}
            onClick={handleSubmit}
          >
            提交答案
          </button>
        </div>
      )}
    </div>
  );
}
