import { useEffect, useState } from "react";
import { AlertTriangle, BookOpen, Check, FileText, RotateCcw, X } from "lucide-react";

import type { MistakeItem, MistakeSourceLink } from "../data/mistakes";

const OPTION_LETTERS = ["A", "B", "C", "D", "E", "F"];

function DifficultyBadge({ difficulty }: { difficulty: MistakeItem["difficulty"] }) {
  return <span className={`mistake-review-difficulty ${difficulty}`}>{difficulty}</span>;
}

function SourceLinkRow({
  link,
  available,
  onOpen,
}: {
  link: MistakeSourceLink;
  available: boolean;
  onOpen: (link: MistakeSourceLink) => void;
}) {
  const content = (
    <>
      <span className="mistake-source-icon">
        {available ? <FileText size={15} /> : <BookOpen size={15} />}
      </span>
      <span className="mistake-source-body">
        <strong>{link.title}</strong>
        <span>{link.location}</span>
        <em>{link.excerpt}</em>
      </span>
    </>
  );

  if (!available) {
    return (
      <div className="mistake-source-row unavailable">
        {content}
      </div>
    );
  }

  return (
    <button className="mistake-source-row" type="button" onClick={() => onOpen(link)}>
      {content}
    </button>
  );
}

export function MistakeReviewPanel({
  mistake,
  canOpenSource,
  onOpenSource,
}: {
  mistake: MistakeItem;
  canOpenSource: (link: MistakeSourceLink) => boolean;
  onOpenSource: (link: MistakeSourceLink) => void;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const [submitted, setSubmitted] = useState(false);

  useEffect(() => {
    setSelected(null);
    setSubmitted(false);
  }, [mistake.id]);

  const isCorrect = submitted && selected === mistake.answer;

  function handleRetry() {
    setSelected(null);
    setSubmitted(false);
  }

  return (
    <article className="mistake-review-panel">
      <header className="mistake-review-header">
        <div className="mistake-review-title-group">
          <span className="mistake-review-eyebrow">
            <AlertTriangle size={14} />
            错题复盘
          </span>
          <h2>{mistake.title}</h2>
        </div>
        <div className="mistake-review-meta">
          <DifficultyBadge difficulty={mistake.difficulty} />
          <span>错 {mistake.wrongCount} 次</span>
          <span>最近 {mistake.lastWrong}</span>
        </div>
      </header>

      <section className="mistake-review-question">
        <div className="mistake-topic-line">
          <span>{mistake.topic}</span>
          {mistake.knowledgePoints.map((point) => (
            <span key={point}>{point}</span>
          ))}
        </div>
        <p>{mistake.question}</p>
      </section>

      <div className="mistake-review-options" role="radiogroup" aria-label="错题选项">
        {mistake.options.map((option, index) => {
          let className = "mistake-review-option";
          if (selected === index) className += " selected";
          if (submitted && index === mistake.answer) className += " correct";
          if (submitted && selected === index && index !== mistake.answer) className += " wrong";

          return (
            <button
              aria-checked={selected === index}
              className={className}
              disabled={submitted}
              key={`${mistake.id}-${index}`}
              onClick={() => setSelected(index)}
              role="radio"
              type="button"
            >
              <span className="mistake-option-letter">{OPTION_LETTERS[index]}</span>
              <span className="mistake-option-text">{option}</span>
              {submitted && index === mistake.answer && <Check className="mistake-option-icon correct" size={16} />}
              {submitted && selected === index && index !== mistake.answer && <X className="mistake-option-icon wrong" size={16} />}
            </button>
          );
        })}
      </div>

      {!submitted && (
        <footer className="mistake-review-actions">
          <button
            className="button compact primary"
            disabled={selected === null}
            onClick={() => setSubmitted(true)}
            type="button"
          >
            提交答案
          </button>
        </footer>
      )}

      {submitted && (
        <section className={`mistake-review-result ${isCorrect ? "correct" : "wrong"}`}>
          <div className="mistake-result-heading">
            {isCorrect ? <Check size={16} /> : <X size={16} />}
            <strong>{isCorrect ? "这次答对了" : "这次仍需复盘"}</strong>
          </div>
          <p>
            正确答案是 {OPTION_LETTERS[mistake.answer]}。{mistake.explanation}
          </p>
          <div className="mistake-error-note">
            <AlertTriangle size={15} />
            <span>{mistake.errorReason}</span>
          </div>
          <div className="mistake-review-actions after-submit">
            <button className="button compact secondary" onClick={handleRetry} type="button">
              <RotateCcw size={14} />
              重新作答
            </button>
          </div>
        </section>
      )}

      {submitted && (
        <section className="mistake-sources">
          <div className="mistake-section-title">
            <FileText size={15} />
            <strong>涉及课程文件</strong>
          </div>
          <div className="mistake-source-list">
            {mistake.sourceLinks.map((link) => (
              <SourceLinkRow
                available={canOpenSource(link)}
                key={link.id}
                link={link}
                onOpen={onOpenSource}
              />
            ))}
          </div>
        </section>
      )}
    </article>
  );
}
