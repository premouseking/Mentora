import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  ChevronLeft,
  ChevronRight,
  FileText,
  Loader2,
  ListChecks,
  X,
} from "lucide-react";
import type { FileNode } from "../data/files";
import {
  completeQuizSession,
  generateQuizSession,
  submitQuizAnswer,
  type QuizItem,
  type QuizSession,
} from "../services/assessmentApi";

const DEFAULT_COUNT = 10;
const OPTION_LABELS = ["A", "B", "C", "D"];

function flattenFiles(files: FileNode[]): FileNode[] {
  return files.flatMap((file) => [file, ...(file.children ? flattenFiles(file.children) : [])]);
}

export function QuizPracticeView({
  files,
  defaultSourceId,
  onBack,
  onOpenSource,
}: {
  files: FileNode[];
  defaultSourceId: string | null;
  onBack: () => void;
  onOpenSource: (id: string) => void;
}) {
  const sourceFiles = useMemo(() => flattenFiles(files), [files]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(
    () => new Set(defaultSourceId ? [defaultSourceId] : []),
  );
  const [count, setCount] = useState(DEFAULT_COUNT);
  const [difficulty, setDifficulty] = useState("综合");
  const [session, setSession] = useState<QuizSession | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submittingItems, setSubmittingItems] = useState<Set<string>>(new Set());
  const [generating, setGenerating] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState("");

  const currentItem = session?.items[currentIndex] ?? null;
  const answeredCount = session
    ? session.items.filter((item) => answers[item.item_id] || item.user_answer).length
    : 0;
  const submitted = session?.status === "completed";

  function toggleSource(id: string) {
    setSelectedSourceIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleGenerate() {
    if (selectedSourceIds.size === 0) return;
    setGenerating(true);
    setError("");
    try {
      const nextSession = await generateQuizSession({
        sourceVersionIds: Array.from(selectedSourceIds),
        count,
        difficulty,
      });
      setSession(nextSession);
      setCurrentIndex(0);
      setAnswers(
        Object.fromEntries(
          nextSession.items
            .filter((item) => item.user_answer)
            .map((item) => [item.item_id, item.user_answer]),
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成题目失败");
    } finally {
      setGenerating(false);
    }
  }

  async function handleSelectAnswer(item: QuizItem, answer: string) {
    if (submitted || submittingItems.has(item.item_id)) return;
    setAnswers((prev) => ({ ...prev, [item.item_id]: answer }));
    setSubmittingItems((prev) => new Set(prev).add(item.item_id));
    try {
      await submitQuizAnswer({
        sessionId: session!.session_id,
        itemId: item.item_id,
        userAnswer: answer,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交答案失败");
    } finally {
      setSubmittingItems((prev) => {
        const next = new Set(prev);
        next.delete(item.item_id);
        return next;
      });
    }
  }

  async function handleComplete() {
    if (!session || answeredCount < session.items.length) return;
    setFinishing(true);
    setError("");
    try {
      const completed = await completeQuizSession(session.session_id);
      setSession(completed);
      setAnswers(
        Object.fromEntries(
          completed.items
            .filter((item) => item.user_answer)
            .map((item) => [item.item_id, item.user_answer]),
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交试卷失败");
    } finally {
      setFinishing(false);
    }
  }

  if (!session) {
    return (
      <div className="quiz-practice-view">
        <header className="quiz-practice-topbar">
          <button className="quiz-topbar-action" onClick={onBack}>
            <ArrowLeft size={16} />
            返回
          </button>
          <div className="quiz-topbar-title">
            <ListChecks size={16} />
            <span>刷题模式</span>
          </div>
        </header>

        <main className="quiz-setup">
          <section className="quiz-setup-main">
            <div className="quiz-setup-heading">
              <span className="quiz-setup-kicker">选择出题资料</span>
              <h2>大模型将基于勾选文件生成练习题</h2>
            </div>

            <div className="quiz-source-list">
              {sourceFiles.length === 0 ? (
                <div className="quiz-empty-note">当前没有可用于出题的课程文件。</div>
              ) : (
                sourceFiles.map((file) => (
                  <label className="quiz-source-row" key={file.id}>
                    <input
                      type="checkbox"
                      checked={selectedSourceIds.has(file.id)}
                      onChange={() => toggleSource(file.id)}
                    />
                    <FileText size={16} />
                    <span>{file.name}</span>
                    {file.id === defaultSourceId && <em>当前打开</em>}
                  </label>
                ))
              )}
            </div>
          </section>

          <aside className="quiz-setup-side">
            <label className="quiz-field">
              <span>题目数量</span>
              <input
                min={1}
                max={20}
                type="number"
                value={count}
                onChange={(event) => setCount(Number(event.target.value) || DEFAULT_COUNT)}
              />
            </label>
            <label className="quiz-field">
              <span>难度</span>
              <select value={difficulty} onChange={(event) => setDifficulty(event.target.value)}>
                <option value="综合">综合</option>
                <option value="基础">基础</option>
                <option value="提高">提高</option>
                <option value="冲刺">冲刺</option>
              </select>
            </label>
            {error && (
              <div className="quiz-error">
                <AlertTriangle size={14} />
                {error}
              </div>
            )}
            <button
              className="quiz-generate-button"
              disabled={selectedSourceIds.size === 0 || generating}
              onClick={handleGenerate}
            >
              {generating ? <Loader2 size={16} className="spin" /> : <ListChecks size={16} />}
              生成题目
            </button>
          </aside>
        </main>
      </div>
    );
  }

  return (
    <div className="quiz-practice-view">
      <header className="quiz-practice-topbar">
        <button className="quiz-topbar-action" onClick={onBack}>
          <ArrowLeft size={16} />
          返回
        </button>
        <div className="quiz-topbar-title">
          <ListChecks size={16} />
          <span>
            第 {currentIndex + 1} 题 / 共 {session.items.length} 题
          </span>
        </div>
        <button
          className="quiz-submit-paper"
          disabled={answeredCount < session.items.length || finishing || submitted}
          onClick={handleComplete}
        >
          {finishing ? <Loader2 size={16} className="spin" /> : <Check size={16} />}
          {submitted ? `得分 ${session.score_pct}` : "提交试卷"}
        </button>
      </header>

      <main className="quiz-practice-layout">
        <section className="quiz-question-board">
          {currentItem && (
            <>
              <div className="quiz-question-meta">
                <span>单选题</span>
                <span>难度 {currentItem.difficulty}</span>
                <span>{answers[currentItem.item_id] || currentItem.user_answer ? "已作答" : "未作答"}</span>
              </div>
              <h2>{currentItem.question_text}</h2>

              <div className="quiz-answer-options">
                {currentItem.options.map((option, index) => {
                  const answer = answers[currentItem.item_id] || currentItem.user_answer;
                  const isPicked = answer === option.label;
                  const isCorrect = submitted && currentItem.correct_answer === option.label;
                  const isWrong = submitted && isPicked && !isCorrect;
                  return (
                    <button
                      key={option.label || index}
                      className={[
                        "quiz-answer-option",
                        isPicked ? "selected" : "",
                        isCorrect ? "correct" : "",
                        isWrong ? "wrong" : "",
                      ].filter(Boolean).join(" ")}
                      disabled={submitted}
                      onClick={() => handleSelectAnswer(currentItem, option.label || OPTION_LABELS[index])}
                    >
                      <span>{option.label || OPTION_LABELS[index]}</span>
                      <strong>{option.text}</strong>
                      {isCorrect && <Check size={16} />}
                      {isWrong && <X size={16} />}
                    </button>
                  );
                })}
              </div>

              {submitted && (
                <div className="quiz-analysis">
                  <div className={currentItem.is_correct ? "quiz-result correct" : "quiz-result wrong"}>
                    {currentItem.is_correct ? <Check size={16} /> : <X size={16} />}
                    {currentItem.is_correct ? "回答正确" : `正确答案是 ${currentItem.correct_answer}`}
                  </div>
                  <p>{currentItem.explanation || "暂无解析。"}</p>
                  {currentItem.source_links.length > 0 && (
                    <div className="quiz-source-evidence">
                      <h3>涉及课程文件</h3>
                      {currentItem.source_links.map((link) => (
                        <button
                          key={link.evidence_id}
                          onClick={() => onOpenSource(link.source_version_id)}
                        >
                          <FileText size={15} />
                          <span>
                            <strong>{link.title}</strong>
                            <small>第 {link.page_number} 页 · {link.snippet}</small>
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </section>

        <aside className="quiz-answer-sheet">
          <div className="quiz-answer-sheet-title">答题卡</div>
          <div className="quiz-answer-sheet-list">
            {session.items.map((item, index) => {
              const answered = !!(answers[item.item_id] || item.user_answer);
              return (
                <button
                  key={item.item_id}
                  className={[
                    "quiz-sheet-number",
                    index === currentIndex ? "current" : "",
                    answered ? "answered" : "",
                    submitted && item.is_correct ? "correct" : "",
                    submitted && answered && !item.is_correct ? "wrong" : "",
                  ].filter(Boolean).join(" ")}
                  onClick={() => setCurrentIndex(index)}
                >
                  {index + 1}
                </button>
              );
            })}
          </div>
        </aside>
      </main>

      <footer className="quiz-practice-footer">
        <button
          className="quiz-nav-button"
          disabled={currentIndex === 0}
          onClick={() => setCurrentIndex((index) => Math.max(0, index - 1))}
        >
          <ChevronLeft size={18} />
          上一题
        </button>
        <button
          className="quiz-nav-button primary"
          disabled={currentIndex === session.items.length - 1}
          onClick={() => setCurrentIndex((index) => Math.min(session.items.length - 1, index + 1))}
        >
          下一题
          <ChevronRight size={18} />
        </button>
      </footer>

      {error && (
        <div className="quiz-floating-error">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}
    </div>
  );
}
