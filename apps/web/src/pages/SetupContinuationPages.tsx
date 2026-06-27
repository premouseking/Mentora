import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Sparkles,
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

  const initRef = useRef(false);  // 防止 StrictMode 双调用

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

  // 首次进入 → 触发首个问题（ref 防 StrictMode 双调用）
  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    fetchNext().finally(() => setLoading(false));
  }, [fetchNext]);

  // 追问记录攒到一起
  const [inquiryLog, setInquiryLog] = useState<string[]>([]);

  async function handleAnswer(value: string) {
    if (!current) return;
    // 同步到底栏 — 追问信息汇总为一条
    const roundLabel = current.text.replace(/[？?]$/, "");
    const entry = `${roundLabel}：${value}`;
    const updated = [...inquiryLog, entry];
    setInquiryLog(updated);
    addItem({
      key: "inquiry",
      title: "补充信息",
      value: updated.join("\n"),
      source: "AI 追问",
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
            <button className="button primary" onClick={() => navigate("/courses/new/plan")} type="button">
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

          {answering && !loading && (
            <div className="question-block">
              <MentoraLoader message="AI 分析中…" size={100} />
            </div>
          )}

          {current && !loading && !error && !answering && (
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
        disabled={text.trim().length < 1 || disabled}
        onClick={() => onAnswer(text.trim())}
        type="button"
      >
        确认
      </button>
    </div>
  );
}

/* ── 步骤 5：确认方案（v5 真滚动 + scroll-snap + 箭头形阶段块）── */

const MOCK_PHASES = [
  { name: "基础入门" },
  { name: "知识梳理" },
  { name: "专项训练" },
  { name: "综合应用" },
  { name: "考前冲刺" },
];

/** 计算 block 在给定 index 的 offsetLeft（含 margin-left: -4px 累积偏移） */
function offsetOf(index: number, blockBasis: number) {
  if (index <= 0) return 0;
  return index * blockBasis - 4 * index;
}

export function ConfirmPlanPage() {
  const navigate = useNavigate();

  const courseTitle = "高中数学一轮复习";
  const phases = MOCK_PHASES;
  const N = phases.length;

  const [activeIndex, setActiveIndex] = useState(0);
  const navRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef(0); // 当前滚动的目标 phase index

  /* ── 统一滚动到 phase[index]，含「目标在第 3 可见位」规则 ── */
  const scrollToPhase = useCallback(
    (index: number) => {
      const el = navRef.current;
      if (!el) return;
      targetRef.current = index;
      setActiveIndex(index);
      const basis = el.clientWidth / 4;
      // 目标 block 落在左起第 3 位（index - 2 的 snap）；snapIndex 不能超过 N-4（保证始终 4 块可见）
      const snapIndex = Math.max(0, Math.min(index - 2, N - 4));
      el.scrollTo({ left: offsetOf(snapIndex, basis), behavior: "smooth" });
    },
    [N],
  );

  /* ── Wheel → 滚动一块并 snap ── */
  const handleWheel = useCallback(
    (e: React.WheelEvent) => {
      e.preventDefault();
      if (N <= 1) return;
      const dir = e.deltaY > 0 ? 1 : -1;
      const next = Math.max(0, Math.min(N - 1, targetRef.current + dir));
      if (next === targetRef.current) return;
      scrollToPhase(next);
    },
    [N, scrollToPhase],
  );

  /* ── Click → 滚动到目标块 ── */
  const handleClick = useCallback(
    (index: number) => {
      if (index === targetRef.current) return;
      scrollToPhase(index);
    },
    [scrollToPhase],
  );

  return (
    <SetupShell
      current={5}
      footer={
        <div className="setup-footer">
          <button className="button secondary" onClick={() => navigate("/courses/new/inquiry")} type="button">
            返回修改需求
          </button>
          <div className="footer-buttons">
            <button className="button secondary" type="button">
              调整计划
            </button>
            <button className="button primary" onClick={() => navigate("/courses")} type="button">
              开始学习
            </button>
          </div>
        </div>
      }
    >
      <div className="plan-page">
        <div className="setup-heading compact-heading">
          <h1 className="course-title-main">「{courseTitle}」学习方案确认</h1>
          <p>AI 已根据你的需求生成阶段方案，请确认并按需调整。</p>
        </div>

        <div className="phase-heading">
          <h2>学习计划 <span>（共 {phases.length} 个阶段）</span></h2>
        </div>

        {/* ── 真滚动滑轨 ── */}
        <div className="phase-track" ref={navRef} onWheel={handleWheel}>
          <div className="phase-track-window">
            {phases.map((phase, i) => (
              <div
                key={i}
                className={`phase-block${i === activeIndex ? " active" : ""}`}
                onClick={() => handleClick(i)}
              >
                <span className="phase-block-num">{i + 1}</span>
                <span className="phase-block-name">{phase.name}</span>
              </div>
            ))}
          </div>
        </div>

        {/* ── 阶段详情区（留空占位）── */}
        <div className="phase-detail-placeholder" />

      </div>
    </SetupShell>
  )
}
