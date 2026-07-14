import { useEffect, useMemo, useRef, useState } from "react";
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
  findReusableQuizSession,
  generateQuizSession,
  isQuizGenerationJob,
  pollQuizGenerationJob,
  submitQuizAnswer,
  TASK_QUIZ_DEFAULT_COUNT,
  type QuizItem,
  type QuizSession,
} from "../services/assessmentApi";

const DEFAULT_COUNT = TASK_QUIZ_DEFAULT_COUNT;
const OPTION_LABELS = ["A", "B", "C", "D"];

export interface TaskQuizConfig {
  taskId: string;
  taskTitle?: string;
  sourceEvidenceIds: string[];
  sourceVersionIds: string[];
  courseSessionId?: string;
  onCompleted?: () => void;
}

function flattenFiles(files: FileNode[]): FileNode[] {
  return files.flatMap((file) => [file, ...(file.children ? flattenFiles(file.children) : [])]);
}

export function QuizPracticeView({
  files,
  defaultSourceId,
  onBack,
  onOpenSource,
  taskMode,
}: {
  files: FileNode[];
  defaultSourceId: string | null;
  onBack: () => void;
  onOpenSource: (id: string) => void;
  taskMode?: TaskQuizConfig;
}) {
  const isTaskMode = Boolean(taskMode);
  const sourceFiles = useMemo(() => flattenFiles(files), [files]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(
    () => new Set(
      taskMode?.sourceVersionIds.length
        ? taskMode.sourceVersionIds
        : defaultSourceId
          ? [defaultSourceId]
          : [],
    ),
  );
  const [count, setCount] = useState(DEFAULT_COUNT);
  const [difficulty, setDifficulty] = useState("综合");
  const [session, setSession] = useState<QuizSession | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submittingItems, setSubmittingItems] = useState<Set<string>>(new Set());
  const [generating, setGenerating] = useState(false);
  const [generationStage, setGenerationStage] = useState("准备生成");
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState("");
  const [confirmSubmitOpen, setConfirmSubmitOpen] = useState(false);
  const autoStartedRef = useRef(false);

  const currentItem = session?.items[currentIndex] ?? null;
  const isLastQuestion = session ? currentIndex === session.items.length - 1 : false;
  const answeredCount = session
    ? session.items.filter((item) => answers[item.item_id] || item.user_answer).length
    : 0;
  const unansweredCount = session ? session.items.length - answeredCount : 0;
  const submitted = session?.status === "completed";

  function toggleSource(id: string) {
    setSelectedSourceIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function applySession(nextSession: QuizSession) {
    setSession(nextSession);
    setCurrentIndex(0);
    setAnswers(
      Object.fromEntries(
        nextSession.items
          .filter((item) => item.user_answer)
          .map((item) => [item.item_id, item.user_answer]),
      ),
    );
  }

  async function handleGenerate(forceRegenerate = false) {
    const sourceVersionIds = isTaskMode
      ? (taskMode?.sourceVersionIds ?? [])
      : Array.from(selectedSourceIds);
    const sourceEvidenceIds = taskMode?.sourceEvidenceIds ?? [];
    if (!isTaskMode && sourceVersionIds.length === 0) return;
    if (isTaskMode && sourceEvidenceIds.length === 0 && sourceVersionIds.length === 0) return;

    setGenerating(true);
    setError("");
    setGenerationStage(forceRegenerate ? "重新生成题目" : "正在读取参考资料");
    try {
      const useAsync = count >= 10;
      setGenerationStage(useAsync ? "已提交后台生成任务" : "正在调用模型生成");
      const result = await generateQuizSession({
        sourceVersionIds,
        sourceEvidenceIds: sourceEvidenceIds.length > 0 ? sourceEvidenceIds : undefined,
        taskId: taskMode?.taskId,
        count,
        difficulty,
        courseSessionId: taskMode?.courseSessionId,
        forceRegenerate,
        async: useAsync,
      });
      if (isQuizGenerationJob(result)) {
        setGenerationStage(result.progress || "后台生成中");
        const nextSession = await pollQuizGenerationJob(result.job_id, {
          intervalMs: 2_000,
        });
        applySession(nextSession);
        return;
      }
      applySession(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成题目失败");
    } finally {
      setGenerating(false);
      setGenerationStage("准备生成");
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

  async function finishQuiz() {
    if (!session || finishing || submitted) return;
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
      taskMode?.onCompleted?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交试卷失败");
    } finally {
      setFinishing(false);
    }
  }

  async function handleComplete() {
    if (!session || finishing || submitted) return;
    if (unansweredCount > 0) {
      setConfirmSubmitOpen(true);
      return;
    }
    await finishQuiz();
  }

  useEffect(() => {
    if (!taskMode || autoStartedRef.current || session) return;
    autoStartedRef.current = true;

    async function bootstrapTaskQuiz() {
      if (taskMode?.courseSessionId) {
        setGenerating(true);
        setGenerationStage("正在查找已有题目");
        try {
          const reused = await findReusableQuizSession({
            courseSessionId: taskMode.courseSessionId,
            taskId: taskMode.taskId,
            sourceVersionIds: taskMode.sourceVersionIds,
            sourceEvidenceIds: taskMode.sourceEvidenceIds,
            count,
            difficulty,
          });
          if (reused) {
            applySession(reused);
            return;
          }
        } catch {
          // 复用失败时继续走新生成
        } finally {
          setGenerating(false);
          setGenerationStage("准备生成");
        }
      }
      await handleGenerate(false);
    }

    void bootstrapTaskQuiz();
  }, [taskMode, session]);

  if (!session) {
    if (isTaskMode && generating) {
      return (
        <div className="quiz-practice-view">
          <header className="quiz-practice-topbar">
            <button className="quiz-topbar-action" onClick={onBack} type="button">
              <ArrowLeft size={16} />
              返回
            </button>
            <div className="quiz-topbar-title">
              <ListChecks size={16} />
              <span>{taskMode?.taskTitle ?? "任务练习"}</span>
            </div>
          </header>
          <main className="quiz-setup">
            <div className="quiz-empty-note">
              <Loader2 size={18} className="spin" />
              {generationStage}…（fast 路径通常 30–90 秒，请勿关闭页面）
            </div>
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
            <span>刷题模式</span>
          </div>
        </header>

        <main className="quiz-setup">
          {isTaskMode && (
            <section className="quiz-setup-main">
              <div className="quiz-setup-heading">
                <span className="quiz-setup-kicker">任务练习</span>
                <h2>{taskMode?.taskTitle ?? "基于任务证据生成题目"}</h2>
              </div>
              <p className="quiz-task-scope-note">
                将仅使用本任务关联的 {taskMode?.sourceEvidenceIds.length ?? 0} 条证据出题。
              </p>
            </section>
          )}
          {!isTaskMode && (
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
          )}
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
              disabled={(isTaskMode ? (taskMode?.sourceEvidenceIds.length ?? 0) === 0 : selectedSourceIds.size === 0) || generating}
              onClick={() => void handleGenerate(false)}
              type="button"
            >
              {generating ? <Loader2 size={16} className="spin" /> : <ListChecks size={16} />}
              {generating ? `${generationStage}…` : "生成题目"}
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
            {submitted
              ? `已完成 · 得分 ${session.score_pct}%`
              : `第 ${currentIndex + 1} 题 / 共 ${session.items.length} 题`}
          </span>
        </div>
        {!submitted && (
          <button
            className="quiz-submit-paper"
            disabled={finishing || generating}
            onClick={() => void handleGenerate(true)}
            type="button"
          >
            重新生成
          </button>
        )}
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
                    submitted && !item.is_correct ? "wrong" : "",
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
          disabled={submitted ? isLastQuestion : finishing}
          onClick={() => {
            if (!submitted && isLastQuestion) {
              void handleComplete();
              return;
            }
            setCurrentIndex((index) => Math.min(session.items.length - 1, index + 1));
          }}
          type="button"
        >
          {finishing && isLastQuestion && !submitted ? (
            <Loader2 size={18} className="spin" />
          ) : null}
          {!submitted && isLastQuestion ? (
            <>
              <Check size={18} />
              提交
            </>
          ) : (
            <>
              下一题
              <ChevronRight size={18} />
            </>
          )}
        </button>
      </footer>

      {confirmSubmitOpen && (
        <div className="quiz-confirm-backdrop" role="presentation">
          <section className="quiz-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="quiz-confirm-title">
            <div className="quiz-confirm-icon">
              <AlertTriangle size={18} />
            </div>
            <div>
              <h3 id="quiz-confirm-title">题目未做完</h3>
              <p>还有 {unansweredCount} 道题未作答，确认交卷吗？未作答题目将按错误处理。</p>
              <div className="quiz-confirm-actions">
                <button
                  className="quiz-confirm-secondary"
                  onClick={() => setConfirmSubmitOpen(false)}
                >
                  继续作答
                </button>
                <button
                  className="quiz-confirm-primary"
                  onClick={() => {
                    setConfirmSubmitOpen(false);
                    void finishQuiz();
                  }}
                >
                  确认交卷
                </button>
              </div>
            </div>
          </section>
        </div>
      )}

      {error && (
        <div className="quiz-floating-error">
          <AlertTriangle size={14} />
          {error}
        </div>
      )}
    </div>
  );
}
