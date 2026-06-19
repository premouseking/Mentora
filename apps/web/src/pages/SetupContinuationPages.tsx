import { useMemo, useState, useEffect, useCallback } from "react";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  FileText,
  ListTree,
  LockKeyhole,
  Sparkles,
  Target,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { SetupShell } from "../components/AppShell";
import { useCourseCreation } from "../components/CourseCreationContext";
import { AiMessageBubble } from "../components/AiMessageBubble";
import { MentoraLoader } from "../components/MentoraLoader";
import { inquiryNext, type InquiryQuestion } from "../services/courseApi";

/* ── 步骤 4：信息追问 ── */

export function AiInquiryPage() {
  const navigate = useNavigate();
  const { addItem, sessionId } = useCourseCreation();
  const [loading, setLoading] = useState(true);        // 首个问题加载
  const [answering, setAnswering] = useState(false);   // 回答提交中
  const [ready, setReady] = useState(false);
  const [current, setCurrent] = useState<InquiryQuestion | null>(null);
  const [round, setRound] = useState(0);
  const [error, setError] = useState("");

  // 获取下一个问题
  const fetchNext = useCallback(async (answer?: string) => {
    if (!sessionId) {
      setError("会话未创建，请返回第一步重新开始。");
      return;
    }
    try {
      const resp = await inquiryNext(sessionId, answer);
      if (resp.ready) {
        setReady(true);
        setCurrent(null);
      } else if (resp.questions && resp.questions.length > 0) {
        setCurrent(resp.questions[0]);
        setRound((r) => r + 1);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "追问请求失败");
    }
  }, [sessionId]);

  // 首次进入 → 触发首个问题
  useEffect(() => {
    fetchNext().finally(() => setLoading(false));
  }, [fetchNext]);

  async function handleAnswer(value: string) {
    if (!current) return;
    // 同步到底栏
    addItem({
      key: `inquiry_r${round}`,
      title: current.text.replace(/[？?]$/, ""),
      value,
      source: "你的回答",
    });

    const prevQuestion = current;
    setCurrent(null);
    setAnswering(true);

    try {
      const resp = await inquiryNext(sessionId!, value);
      if (resp.ready) {
        setReady(true);
      } else if (resp.questions && resp.questions.length > 0) {
        setCurrent(resp.questions[0]);
        setRound((r) => r + 1);
      }
    } catch (err: unknown) {
      // 回答失败时恢复当前问题供重试
      setCurrent(prevQuestion);
      setError(err instanceof Error ? err.message : "回答提交失败");
    } finally {
      setAnswering(false);
    }
  }

  return (
    <SetupShell
      current={4}
      leftAside={
        <AiMessageBubble visible={!!current?.guidance || !!error}>
          {error || current?.guidance || ""}
        </AiMessageBubble>
      }
      footer={
        <div className="setup-footer">
          <button className="button secondary" onClick={() => navigate("/courses/new/materials")} type="button">
            <ArrowLeft size={15} /> 上一步
          </button>
          <div className="footer-buttons">
            <button className="button primary" onClick={() => navigate("/courses/new/plan")} type="button"
              disabled={answering}>
              <Sparkles size={16} /> {ready ? "生成学习方案" : "停止追问 → 生成方案"}
            </button>
          </div>
        </div>
      }
    >
      <div className="inquiry-page">
        <div className="inquiry-main">
          <div className="setup-heading compact-heading">
            <h1>信息追问</h1>
            <p>
              AI 正在根据你的目标进一步确认需求。
              {round > 0 && (
                <span className="inquiry-progress">已收集 {round} 轮信息</span>
              )}
            </p>
          </div>

          {loading && (
            <div className="question-block">
              <MentoraLoader message="AI 正在分析你的需求…" size={140} />
            </div>
          )}

          {error && !loading && (
            <div className="question-block">
              <p className="error-text">{error}</p>
              <button className="button secondary" onClick={() => { setError(""); fetchNext(); }} type="button">
                重试
              </button>
            </div>
          )}

          {ready && !loading && (
            <div className="question-block">
              <h2>信息已足够！</h2>
              <p>AI 已收集到足够的信息，可以为你生成个性化的学习方案。</p>
            </div>
          )}

          {current && !loading && !error && (
            <section className="question-block">
              <p className="question-index">当前问题</p>
              <h2>{current.text}</h2>

              {current.type === "multi_choice" && (
                <MultiChoiceQ options={current.options} onAnswer={handleAnswer} disabled={answering} />
              )}
              {current.type === "single_choice" && (
                <SingleChoiceQ options={current.options} onAnswer={handleAnswer} disabled={answering} />
              )}
              {current.type === "free_text" && (
                <FreeTextQ onAnswer={handleAnswer} disabled={answering} />
              )}

              {answering && (
                <MentoraLoader message="AI 分析中…" size={100} />              )}
            </section>
          )}
        </div>
      </div>
    </SetupShell>
  );
}

function MultiChoiceQ({
  options,
  onAnswer,
  disabled = false,
}: {
  options: string[];
  onAnswer: (v: string) => void;
  disabled?: boolean;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  return (
    <div>
      <div className="choice-grid">
        {options.map((opt) => (
          <button
            key={opt}
            aria-pressed={selected.includes(opt)}
            className={selected.includes(opt) ? "choice selected" : "choice"}
            disabled={disabled}
            onClick={() =>
              setSelected((prev) =>
                prev.includes(opt) ? prev.filter((o) => o !== opt) : [...prev, opt],
              )
            }
            type="button"
          >
            {opt}
          </button>
        ))}
      </div>
      <button
        className="button secondary"
        disabled={selected.length === 0 || disabled}
        onClick={() => onAnswer(selected.join("、"))}
        style={{ marginTop: 16 }}
        type="button"
      >
        确认
      </button>
    </div>
  );
}

function SingleChoiceQ({
  options,
  onAnswer,
  disabled = false,
}: {
  options: string[];
  onAnswer: (v: string) => void;
  disabled?: boolean;
}) {
  const [picked, setPicked] = useState("");
  return (
    <div>
      <div className="choice-grid">
        {options.map((opt) => (
          <button
            key={opt}
            aria-pressed={picked === opt}
            className={picked === opt ? "choice selected" : "choice"}
            disabled={disabled}
            onClick={() => {
              setPicked(opt);
              onAnswer(opt);
            }}
            type="button"
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}

function FreeTextQ({ onAnswer, disabled = false }: { onAnswer: (v: string) => void; disabled?: boolean }) {
  const [text, setText] = useState("");
  return (
    <div className="free-text-block">
      <textarea
        autoFocus
        className="free-text-input"
        disabled={disabled}
        maxLength={500}
        onChange={(e) => setText(e.target.value)}
        placeholder="请简要描述你的想法…"
        value={text}
      />
      <button
        className="button secondary"
        disabled={text.trim().length < 2 || disabled}
        onClick={() => onAnswer(text.trim())}
        type="button"
      >
        确认
      </button>
    </div>
  );
}

/* ── 步骤 5：确认方案 ── */

type Phase = {
  id: string;
  name: string;
  goal: string;
  share: number;
  tasks: string[];
};

export function ConfirmPlanPage() {
  const navigate = useNavigate();
  const { items, sessionId } = useCourseCreation();
  const [phases, setPhases] = useState<Phase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activePhaseId, setActivePhaseId] = useState("");
  const [planExpanded, setPlanExpanded] = useState(false);

  const activePhase = useMemo(
    () => phases.find((phase) => phase.id === activePhaseId) ?? phases[0],
    [activePhaseId, phases],
  );

  // 页面加载 → 调用 plan API
  useEffect(() => {
    if (!sessionId) {
      setError("未找到建课会话，请返回第一步重新开始。");
      setLoading(false);
      return;
    }

    import("../services/courseApi").then(async ({ generatePlan }) => {
      try {
        const resp = await generatePlan(sessionId);
        const mapped: Phase[] = resp.phases.map((p, i) => ({
          id: `phase_${i}`,
          name: p.name,
          goal: p.goal,
          share: p.share,
          tasks: p.tasks,
        }));
        setPhases(mapped);
        if (mapped.length > 0) {
          setActivePhaseId(mapped[0].id);
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "方案生成失败");
      } finally {
        setLoading(false);
      }
    });
  }, [sessionId]);

  // 页面加载后触发底栏展开动画
  function triggerExpand() {
    setPlanExpanded(true);
  }

  function startCourse() {
    sessionStorage.setItem("mentora-course-started", "true");
    navigate("/courses");
  }

  function adjustActivePhase(direction: "simplify" | "deepen") {
    setPhases((current) =>
      current.map((phase) => {
        if (phase.id !== activePhaseId) return phase;
        if (direction === "simplify") {
          return {
            ...phase,
            share: Math.max(10, phase.share - 5),
            tasks: phase.tasks.length > 2 ? phase.tasks.slice(0, -1) : phase.tasks,
          };
        }
        return {
          ...phase,
          share: Math.min(50, phase.share + 5),
          tasks: phase.tasks.includes("补充迁移练习") ? phase.tasks : [...phase.tasks, "补充迁移练习"],
        };
      }),
    );
  }

  return (
    <SetupShell
      current={5}
      hideInfoBar
      footer={
        <div className="setup-footer">
          <button className="button secondary" onClick={() => navigate("/courses/new/inquiry")} type="button">
            返回修改需求
          </button>
          <button className="button primary" disabled={loading} onClick={startCourse} type="button">开始学习</button>
        </div>
      }
    >
      <div className="plan-page">
        <div className="setup-heading compact-heading">
          <h1>确认学习方案</h1>
          <p>{loading ? "AI 正在生成方案…" : error ? "方案生成遇到问题" : "AI 已根据你的需求生成阶段方案，请确认并按需调整。"}</p>
        </div>

        {loading && (
          <div className="question-block">
            <MentoraLoader
              message="AI 正在根据你的信息生成个性化学习方案…"
              size={160}
            >
              <p style={{ margin: 0, fontSize: 13, color: "var(--quiet)", maxWidth: 320, textAlign: "center", lineHeight: 1.7 }}>
                这将需要一点时间，请稍候。
              </p>
            </MentoraLoader>
          </div>
        )}

        {error && (
          <div className="question-block">
            <p className="error-text">{error}</p>
            <button className="button secondary" onClick={() => window.location.reload()} type="button">
              重试
            </button>
          </div>
        )}

        {!loading && !error && phases.length > 0 && (
          <>
          <div className={`plan-info-section${planExpanded ? " plan-expanded" : ""}`}>
            <h3 className="plan-info-heading">
              <Sparkles size={16} /> 学习方案概览
            </h3>
            <dl className="info-bar-list plan-info-list">
              {items.map((item) => (
                <div className="info-bar-row" key={item.key}>
                  <dt>{item.title}</dt>
                  <dd>{item.value}</dd>
                </div>
              ))}
            </dl>
            {!planExpanded && (
              <button className="plan-expand-btn" onClick={triggerExpand} type="button">
                查看完整方案
              </button>
            )}
          </div>

        <div className="phase-heading">
          <h2>学习阶段 <span>（共 {phases.length} 个阶段）</span></h2>
          <small>阶段是主要结构，完成节奏可根据实际情况调整。</small>
        </div>

        <div className="phase-path">
          {phases.map((phase, index) => (
            <div className="phase-path-item" key={phase.id}>
              <button
                aria-pressed={phase.id === activePhaseId}
                className={phase.id === activePhaseId ? "active" : ""}
                onClick={() => setActivePhaseId(phase.id)}
                type="button"
              >
                <span>{index + 1}</span>
                {phase.name}
              </button>
              {index < phases.length - 1 ? <ArrowRight size={18} /> : null}
            </div>
          ))}
        </div>

        <section className="phase-detail">
          <div className="phase-detail-row">
            <span><Target size={18} /> 阶段目标</span>
            <p>{activePhase?.goal || "请在左侧选择一个阶段"}</p>
          </div>
          <div className="phase-detail-row">
            <span><ListTree size={18} /> 相对学习量</span>
            <div className="share-display">
              <strong>约占全部内容的 {activePhase?.share ?? 0}%</strong>
              <div>
                {[10, 20, 30, 40, 50, 60].map((threshold) => (
                  <i className={(activePhase?.share ?? 0) >= threshold ? "filled" : ""} key={threshold} />
                ))}
              </div>
            </div>
          </div>
          <div className="phase-detail-row task-detail">
            <span><FileText size={18} /> 代表性任务</span>
            <ul>
              {(activePhase?.tasks ?? []).slice(0, 5).map((task) => <li key={task}>{task}</li>)}
            </ul>
          </div>
          <div className="phase-operations">
            <span>本阶段操作</span>
            <button onClick={() => adjustActivePhase("simplify")} type="button">
              <ArrowDown size={16} /> 简化阶段
            </button>
            <button onClick={() => adjustActivePhase("deepen")} type="button">
              <ArrowUp size={16} /> 加强阶段
            </button>
            <button type="button">
              <ListTree size={16} /> 查看全部任务
            </button>
          </div>
        </section>
        <p className="privacy-note"><LockKeyhole size={13} /> 开始后仍可调整阶段顺序、内容重点和学习节奏。</p>
        </>
        )}
      </div>
    </SetupShell>
  );
}
