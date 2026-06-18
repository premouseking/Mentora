import { useMemo, useState } from "react";
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

/* ── 步骤 3：信息追问 ── */

const mockQuestions = [
  {
    id: "q1",
    question: "你需要重点学习哪些具体主题？",
    guidance: "根据你之前的描述，AI 已经了解到你想学习计算机组成原理。请选择你希望重点掌握的主题，可以多选。",
    type: "multi_choice" as const,
    options: ["存储系统", "指令系统", "CPU 组成", "总线与 I/O", "运算方法与 ALU"],
  },
  {
    id: "q2",
    question: "你的考试范围是否包含实验或设计题目？",
    guidance: "了解是否有实践环节可以帮助 AI 规划更合适的学习路径和练习内容。",
    type: "single_choice" as const,
    options: ["仅理论笔试", "包含实验部分", "包含课程设计", "不确定"],
  },
  {
    id: "q3",
    question: "你对哪个方面最有信心？哪个最需要加强？",
    guidance: "这些信息有助于 AI 调整各阶段的重点分配和练习量。",
    type: "free_text" as const,
  },
];

export function AiInquiryPage() {
  const navigate = useNavigate();
  const { addItem } = useCourseCreation();
  const [qIndex, setQIndex] = useState(0);
  const current = mockQuestions[qIndex];
  const isLast = qIndex >= mockQuestions.length - 1;

  function handleAnswer(value: string) {
    addItem({
      key: `inquiry_${current.id}`,
      title: current.question.replace(/[？?]$/, ""),
      value,
      source: "你的回答",
    });
    if (isLast) return;
    setQIndex((i) => i + 1);
  }

  return (
    <SetupShell
      current={4}
      leftAside={
        <AiMessageBubble visible={!!current}>
          {current.guidance}
        </AiMessageBubble>
      }
      footer={
        <div className="setup-footer">
          <button className="button secondary" onClick={() => navigate("/courses/new/materials")} type="button">
            <ArrowLeft size={15} /> 上一步
          </button>
          <div className="footer-buttons">
            {!isLast && (
              <button className="button secondary" onClick={() => navigate("/courses/new/plan")} type="button">
                停止追问
              </button>
            )}
            <button className="button primary" onClick={() => navigate("/courses/new/plan")} type="button">
              <Sparkles size={16} /> 生成学习方案
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
              <span className="inquiry-progress">
                问题 {qIndex + 1} / {mockQuestions.length}
              </span>
            </p>
          </div>

          <section className="question-block">
            <p className="question-index">当前问题</p>
            <h2>{current.question}</h2>

            {current.type === "multi_choice" && (
              <MultiChoiceQ options={current.options} onAnswer={handleAnswer} />
            )}
            {current.type === "single_choice" && (
              <SingleChoiceQ options={current.options} onAnswer={handleAnswer} />
            )}
            {current.type === "free_text" && (
              <FreeTextQ onAnswer={handleAnswer} />
            )}
          </section>
        </div>
      </div>
    </SetupShell>
  );
}

function MultiChoiceQ({
  options,
  onAnswer,
}: {
  options: string[];
  onAnswer: (v: string) => void;
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
        disabled={selected.length === 0}
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
}: {
  options: string[];
  onAnswer: (v: string) => void;
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

function FreeTextQ({ onAnswer }: { onAnswer: (v: string) => void }) {
  const [text, setText] = useState("");
  return (
    <div className="free-text-block">
      <textarea
        autoFocus
        className="free-text-input"
        maxLength={500}
        onChange={(e) => setText(e.target.value)}
        placeholder="请简要描述你的想法…"
        value={text}
      />
      <button
        className="button secondary"
        disabled={text.trim().length < 2}
        onClick={() => onAnswer(text.trim())}
        type="button"
      >
        确认
      </button>
    </div>
  );
}

/* ── 步骤 4：确认方案 ── */

type Phase = {
  id: string;
  name: string;
  goal: string;
  share: number;
  tasks: string[];
};

const initialPhases: Phase[] = [
  {
    id: "foundation",
    name: "基础梳理",
    goal: "建立完整知识框架，理解核心概念与基本原理。",
    share: 25,
    tasks: ["理解计算机系统的层次结构", "掌握数据的表示与运算", "理解指令系统与寻址方式", "理解存储系统的基本组成"],
  },
  {
    id: "focus",
    name: "重点突破",
    goal: "集中突破考试高频主题和当前薄弱环节。",
    share: 35,
    tasks: ["Cache 映射与替换策略", "CPU 数据通路", "指令流水线与相关冲突"],
  },
  {
    id: "application",
    name: "综合应用",
    goal: "通过综合问题建立跨主题联系。",
    share: 25,
    tasks: ["综合计算题", "跨章节概念辨析", "典型题型迁移练习"],
  },
  {
    id: "review",
    name: "检验巩固",
    goal: "检查掌握情况并安排针对性回顾。",
    share: 15,
    tasks: ["阶段检查", "错题回顾", "考前快速复盘"],
  },
];

export function ConfirmPlanPage() {
  const navigate = useNavigate();
  const { items } = useCourseCreation();
  const [phases, setPhases] = useState(initialPhases);
  const [activePhaseId, setActivePhaseId] = useState(initialPhases[0].id);
  const [planExpanded, setPlanExpanded] = useState(false);
  const activePhase = useMemo(
    () => phases.find((phase) => phase.id === activePhaseId) ?? phases[0],
    [activePhaseId, phases],
  );

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
          <button className="button primary" onClick={startCourse} type="button">开始学习</button>
        </div>
      }
    >
      <div className="plan-page">
        <div className="setup-heading compact-heading">
          <h1>确认学习方案</h1>
          <p>AI 已根据你的需求生成阶段方案，请确认并按需调整。</p>
        </div>

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
            <p>{activePhase.goal}</p>
          </div>
          <div className="phase-detail-row">
            <span><ListTree size={18} /> 相对学习量</span>
            <div className="share-display">
              <strong>约占全部内容的 {activePhase.share}%</strong>
              <div>
                {[10, 20, 30, 40, 50, 60].map((threshold) => (
                  <i className={activePhase.share >= threshold ? "filled" : ""} key={threshold} />
                ))}
              </div>
            </div>
          </div>
          <div className="phase-detail-row task-detail">
            <span><FileText size={18} /> 代表性任务</span>
            <ul>
              {activePhase.tasks.slice(0, 5).map((task) => <li key={task}>{task}</li>)}
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
      </div>
    </SetupShell>
  );
}
