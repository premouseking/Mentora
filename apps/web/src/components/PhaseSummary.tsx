import { X } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";

/* ── Mock 数据（v6：全部 mock，不连后端）── */

const MOCK_PLAN = {
  plan_id: "mock-plan",
  revision_id: "mock-rev-1",
  status: "active",
  feasibility_status: "feasible",
  profile_revision_id: "mock-profile-1",
  phases: [
    {
      id: "p1",
      position: 0,
      title: "基础入门",
      objective: "掌握集合、函数等核心概念与基本方法",
      estimated_minutes: 480,
      units: [
        {
          id: "p1-u1",
          title: "集合与逻辑",
          position: 0,
          topic_id: null,
          target_depth: "understand",
          estimated_minutes: 160,
          prerequisite_unit_ids: [],
          priority: 1,
          tasks: [
            { id: "p1-u1-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true },
            { id: "p1-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 40, required: true },
            { id: "p1-u1-t3", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true },
            { id: "p1-u1-t4", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 40, required: true },
          ],
        },
        {
          id: "p1-u2",
          title: "函数基础",
          position: 1,
          topic_id: null,
          target_depth: "understand",
          estimated_minutes: 150,
          prerequisite_unit_ids: ["p1-u1"],
          priority: 1,
          tasks: [
            { id: "p1-u2-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 50, required: true },
            { id: "p1-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 50, required: true },
            { id: "p1-u2-t3", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 50, required: true },
          ],
        },
        {
          id: "p1-u3",
          title: "基本初等函数",
          position: 2,
          topic_id: null,
          target_depth: "understand",
          estimated_minutes: 170,
          prerequisite_unit_ids: ["p1-u2"],
          priority: 1,
          tasks: [
            { id: "p1-u3-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true },
            { id: "p1-u3-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 45, required: true },
            { id: "p1-u3-t3", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true },
            { id: "p1-u3-t4", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 45, required: true },
          ],
        },
      ],
    },
    {
      id: "p2",
      position: 1,
      title: "知识梳理",
      objective: "系统学习教材，按章节深入梳理知识体系",
      estimated_minutes: 600,
      units: [
        {
          id: "p2-u1",
          title: "数列与极限",
          position: 0,
          topic_id: null,
          target_depth: "apply",
          estimated_minutes: 300,
          prerequisite_unit_ids: [],
          priority: 1,
          tasks: [
            { id: "p2-u1-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 60, required: true },
            { id: "p2-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true },
            { id: "p2-u1-t3", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 60, required: true },
          ],
        },
        {
          id: "p2-u2",
          title: "三角函数",
          position: 1,
          topic_id: null,
          target_depth: "apply",
          estimated_minutes: 300,
          prerequisite_unit_ids: ["p2-u1"],
          priority: 1,
          tasks: [
            { id: "p2-u2-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 50, required: true },
            { id: "p2-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 50, required: true },
          ],
        },
      ],
    },
    {
      id: "p3",
      position: 2,
      title: "专项训练",
      objective: "突破薄弱点，题型分类训练",
      estimated_minutes: 540,
      units: [
        {
          id: "p3-u1",
          title: "函数题型专项",
          position: 0,
          topic_id: null,
          target_depth: "apply",
          estimated_minutes: 270,
          prerequisite_unit_ids: [],
          priority: 1,
          tasks: [
            { id: "p3-u1-t1", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true },
            { id: "p3-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true },
            { id: "p3-u1-t3", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 90, required: true },
          ],
        },
        {
          id: "p3-u2",
          title: "几何题型专项",
          position: 1,
          topic_id: null,
          target_depth: "apply",
          estimated_minutes: 270,
          prerequisite_unit_ids: ["p3-u1"],
          priority: 1,
          tasks: [
            { id: "p3-u2-t1", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true },
            { id: "p3-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true },
            { id: "p3-u2-t3", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 90, required: true },
          ],
        },
      ],
    },
    {
      id: "p4",
      position: 3,
      title: "综合应用",
      objective: "跨知识点实战，真题与综合项目",
      estimated_minutes: 480,
      units: [
        {
          id: "p4-u1",
          title: "综合真题训练",
          position: 0,
          topic_id: null,
          target_depth: "analyze",
          estimated_minutes: 240,
          prerequisite_unit_ids: [],
          priority: 1,
          tasks: [
            { id: "p4-u1-t1", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 120, required: true },
            { id: "p4-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 120, required: true },
          ],
        },
        {
          id: "p4-u2",
          title: "跨章节综合",
          position: 1,
          topic_id: null,
          target_depth: "analyze",
          estimated_minutes: 240,
          prerequisite_unit_ids: ["p4-u1"],
          priority: 1,
          tasks: [
            { id: "p4-u2-t1", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 80, required: true },
            { id: "p4-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 80, required: true },
            { id: "p4-u2-t3", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 80, required: true },
          ],
        },
      ],
    },
    {
      id: "p5",
      position: 4,
      title: "考前冲刺",
      objective: "考点回顾，临场策略与限时模拟",
      estimated_minutes: 360,
      units: [
        {
          id: "p5-u1",
          title: "考点回顾",
          position: 0,
          topic_id: null,
          target_depth: "analyze",
          estimated_minutes: 180,
          prerequisite_unit_ids: [],
          priority: 1,
          tasks: [
            { id: "p5-u1-t1", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 90, required: true },
            { id: "p5-u1-t2", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 90, required: true },
          ],
        },
        {
          id: "p5-u2",
          title: "限时模拟",
          position: 1,
          topic_id: null,
          target_depth: "analyze",
          estimated_minutes: 180,
          prerequisite_unit_ids: ["p5-u1"],
          priority: 1,
          tasks: [
            { id: "p5-u2-t1", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 120, required: true },
            { id: "p5-u2-t2", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 60, required: true },
          ],
        },
      ],
    },
  ],
};

/* ── 任务类型标签 ── */

const TASK_TYPE_LABEL: Record<string, string> = {
  lecture: "讲解",
  exercise: "练习",
  project: "项目",
  review: "复习",
};

/* ── 左栏：纵向阶段导航（复用建课确认页滑轨逻辑，方向横→纵）── */

type NavPhase = { id: string; title: string };

function offsetOf(index: number, blockBasis: number) {
  if (index <= 0) return 0;
  return index * blockBasis - 14 * index;
}

function PhaseNav({
  phases,
  activeIndex,
  onSelect,
}: {
  phases: NavPhase[];
  activeIndex: number;
  /** 点击阶段块：无论是否已选中都触发，由父组件决定行为 */
  onSelect: (i: number) => void;
}) {
  const N = phases.length;
  const navRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef(activeIndex);

  const snapTopOf = useCallback((snapIndex: number) => {
    const el = navRef.current;
    if (!el) return 0;
    const blocks = el.querySelectorAll<HTMLElement>(".ps-phase-nav-block");
    const block = blocks[snapIndex];
    return block ? block.offsetTop : offsetOf(snapIndex, el.clientHeight / 4);
  }, []);

  const scrollToPhase = useCallback(
    (index: number) => {
      const el = navRef.current;
      if (!el) return;
      const prev = targetRef.current;
      const down = index > prev;
      targetRef.current = index;
      onSelect(index);
      const maxStart = Math.max(0, N - 4);
      const anchor = down ? index - 2 : index - 1;
      const snapIndex = Math.max(0, Math.min(anchor, maxStart));
      el.scrollTo({ top: snapTopOf(snapIndex), behavior: "smooth" });
    },
    [N, snapTopOf, onSelect],
  );

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

  const handleClick = useCallback(
    (index: number) => {
      // 已选中：直接回调让父组件把右栏切回阶段信息
      // 未选中：先滚动定位，再回调切换阶段
      if (index !== targetRef.current) {
        scrollToPhase(index);
      }
      onSelect(index);
    },
    [scrollToPhase, onSelect],
  );

  return (
    <div className="ps-phase-nav" ref={navRef} onWheel={handleWheel} onPointerDown={(e) => e.stopPropagation()}>
      <div className="ps-phase-nav-window">
        {phases.map((phase, i) => (
          <div
            key={phase.id}
            className={`ps-phase-nav-block${i === activeIndex ? " active" : ""}`}
            onClick={() => handleClick(i)}
          >
            <span className="ps-phase-nav-num">{i + 1}</span>
            <span className="ps-phase-nav-name">{phase.title}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── 中栏：主干 + 分支画板 ── */

/** 画板尺寸常量 */
const CANVAS = {
  W: 600,
  chW: 150,
  chH: 42,
  tkW: 116,
  tkH: 34,
  tkGap: 10,
  chGap: 48,
  branch: 104, // 章节中心到任务群竖线的水平距离
  pad: 28,
};

type TaskNode = {
  id: string;
  label: string;
  taskType: string;
  minutes: number;
  x: number;
  y: number;
  w: number;
  h: number;
};

type ChapterNode = {
  id: string;
  title: string;
  x: number;
  y: number;
  w: number;
  h: number;
  centerY: number;
  side: 1 | -1;
  stemX: number;
  tasks: TaskNode[];
};

type Layout = {
  width: number;
  height: number;
  chapters: ChapterNode[];
};

/** 计算当前阶段所有章节与任务的绝对坐标 */
function computeLayout(units: typeof MOCK_PLAN.phases[0]["units"]): Layout {
  const cx = CANVAS.W / 2;
  let y = CANVAS.pad;
  const chapters: ChapterNode[] = units.map((unit, i) => {
    const tasks = unit.tasks;
    const tasksH = tasks.length * CANVAS.tkH + Math.max(0, tasks.length - 1) * CANVAS.tkGap;
    const blockH = Math.max(CANVAS.chH, tasksH);
    const chTop = y + (blockH - CANVAS.chH) / 2;
    const chCenterY = chTop + CANVAS.chH / 2;
    const side: 1 | -1 = i % 2 === 0 ? 1 : -1; // 偶数章节右、奇数章节左
    const stemX = cx + side * CANVAS.branch;
    const taskStartY = y + (blockH - tasksH) / 2;
    const taskNodes: TaskNode[] = tasks.map((t, j) => ({
      id: t.id,
      label: `${TASK_TYPE_LABEL[t.task_type] ?? t.task_type} ${j + 1}`,
      taskType: t.task_type,
      minutes: t.estimated_minutes,
      x: side === 1 ? stemX + 14 : stemX - 14 - CANVAS.tkW,
      y: taskStartY + j * (CANVAS.tkH + CANVAS.tkGap),
      w: CANVAS.tkW,
      h: CANVAS.tkH,
    }));
    const chapter: ChapterNode = {
      id: unit.id,
      title: unit.title || `单元 ${unit.position + 1}`,
      x: cx - CANVAS.chW / 2,
      y: chTop,
      w: CANVAS.chW,
      h: CANVAS.chH,
      centerY: chCenterY,
      side,
      stemX,
      tasks: taskNodes,
    };
    y += blockH + CANVAS.chGap;
    return chapter;
  });
  const height = Math.max(y - CANVAS.chGap + CANVAS.pad, 1);
  return { width: CANVAS.W, height, chapters };
}

type Selection =
  | { kind: "phase"; id: string }
  | { kind: "chapter"; id: string }
  | { kind: "task"; id: string }
  | null;

function PhaseCanvas({
  units,
  selected,
  onSelect,
}: {
  units: typeof MOCK_PLAN.phases[0]["units"];
  selected: Selection;
  onSelect: (s: Selection) => void;
}) {
  const layout = useMemo(() => computeLayout(units), [units]);
  const { width, height, chapters } = layout;
  const cx = width / 2;

  return (
    <div className="ps-canvas" onPointerDown={(e) => e.stopPropagation()}>
      <div className="ps-canvas-scroll" style={{ minWidth: width, minHeight: height }}>
        <div className="ps-canvas-content" style={{ width, height }}>
          {/* SVG 连线层 */}
          <svg
            className="ps-canvas-svg"
            width={width}
            height={height}
            viewBox={`0 0 ${width} ${height}`}
          >
            <defs>
              <marker
                id="ps-arrow-down"
                markerWidth="10"
                markerHeight="10"
                refX="5"
                refY="8"
                orient="auto"
              >
                <path d="M1.5,2 L5,8 L8.5,2" fill="none" stroke="var(--border-strong)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </marker>
            </defs>

            {/* 主干箭头：章节 i 底部 → 章节 i+1 顶部 */}
            {chapters.map((ch, i) =>
              i < chapters.length - 1 ? (
                <line
                  key={`trunk-${ch.id}`}
                  x1={cx}
                  y1={ch.y + ch.h}
                  x2={cx}
                  y2={chapters[i + 1].y}
                  stroke="var(--border-strong)"
                  strokeWidth="1.5"
                  markerEnd="url(#ps-arrow-down)"
                />
              ) : null,
            )}

            {/* 分支：每个章节的丰字形连线 */}
            {chapters.map((ch) => {
              if (ch.tasks.length === 0) return null;
              const firstCY = ch.tasks[0].y + ch.tasks[0].h / 2;
              const lastCY = ch.tasks[ch.tasks.length - 1].y + ch.tasks[ch.tasks.length - 1].h / 2;
              return (
                <g key={`branch-${ch.id}`}>
                  {/* 章节中心 → 任务群竖线的横线 */}
                  <line
                    x1={cx}
                    y1={ch.centerY}
                    x2={ch.stemX}
                    y2={ch.centerY}
                    stroke="var(--border)"
                    strokeWidth="1.2"
                  />
                  {/* 任务群竖线 */}
                  {ch.tasks.length > 1 && (
                    <line
                      x1={ch.stemX}
                      y1={firstCY}
                      x2={ch.stemX}
                      y2={lastCY}
                      stroke="var(--border)"
                      strokeWidth="1.2"
                    />
                  )}
                  {/* 每个任务的水平连线 */}
                  {ch.tasks.map((t) => {
                    const tCY = t.y + t.h / 2;
                    const edgeX = ch.side === 1 ? t.x : t.x + t.w;
                    return (
                      <line
                        key={`tl-${t.id}`}
                        x1={ch.stemX}
                        y1={tCY}
                        x2={edgeX}
                        y2={tCY}
                        stroke="var(--border)"
                        strokeWidth="1.2"
                      />
                    );
                  })}
                </g>
              );
            })}
          </svg>

          {/* DOM 节点层 */}
          {chapters.map((ch) => (
            <div key={ch.id}>
              <button
                type="button"
                className={`ps-node ps-node-chapter${selected?.kind === "chapter" && selected.id === ch.id ? " selected" : ""}`}
                style={{ left: ch.x, top: ch.y, width: ch.w, height: ch.h }}
                onClick={() => onSelect({ kind: "chapter", id: ch.id })}
              >
                {ch.title}
              </button>
              {ch.tasks.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`ps-node ps-node-task${selected?.kind === "task" && selected.id === t.id ? " selected" : ""}`}
                  style={{ left: t.x, top: t.y, width: t.w, height: t.h }}
                  onClick={() => onSelect({ kind: "task", id: t.id })}
                >
                  {t.label}
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── 右栏：详情（占位，响应选中）── */

function PhaseDetail({
  phase,
  units,
  selected,
}: {
  phase: typeof MOCK_PLAN.phases[0];
  units: typeof MOCK_PLAN.phases[0]["units"];
  selected: Selection;
}) {
  // 查找选中节点
  const node = useMemo(() => {
    if (!selected) return null;
    if (selected.kind === "phase") {
      const taskCount = units.reduce((s, u) => s + u.tasks.length, 0);
      return { type: "phase", title: phase.title, meta: `${units.length} 章节 · ${taskCount} 任务 · ${phase.estimated_minutes} 分钟`, objective: phase.objective };
    }
    if (selected.kind === "chapter") {
      const u = units.find((u) => u.id === selected.id);
      return u ? { type: "chapter", title: u.title || `单元 ${u.position + 1}`, meta: `${u.tasks.length} 个任务 · ${u.estimated_minutes} 分钟` } : null;
    }
    for (const u of units) {
      const t = u.tasks.find((t) => t.id === selected.id);
      if (t) {
        return { type: "task", title: `${TASK_TYPE_LABEL[t.task_type] ?? t.task_type}`, meta: `${t.estimated_minutes} 分钟`, parent: u.title };
      }
    }
    return null;
  }, [selected, units, phase]);

  if (!node) {
    return (
      <div className="ps-detail">
        <p className="ps-detail-empty">点击章节或任务查看详情</p>
      </div>
    );
  }

  return (
    <div className="ps-detail">
      <div className="ps-detail-badge">{node.type === "phase" ? "阶段" : node.type === "chapter" ? "章节" : "任务"}</div>
      <h3 className="ps-detail-title">{node.title}</h3>
      <p className="ps-detail-meta">{node.meta}</p>
      {"objective" in node && node.objective && (
        <p className="ps-detail-objective">{node.objective}</p>
      )}
      {"parent" in node && node.parent && (
        <p className="ps-detail-parent">所属章节：{node.parent}</p>
      )}
    </div>
  );
}

/* ── 主体：v6 三栏布局 ── */

export function PhaseSummary({
  onClose,
}: {
  onClose: () => void;
}) {
  const plan = MOCK_PLAN;
  const [activePhase, setActivePhase] = useState(0);
  const [selected, setSelected] = useState<Selection>({ kind: "phase", id: plan.phases[0].id });
  const phase = plan.phases[activePhase];

  // 切换阶段时清空选中
  const handleSelectPhase = useCallback((i: number) => {
    setActivePhase(i);
    setSelected(null);
  }, []);

  return (
    <div className="phase-summary">
      {/* 顶部栏（静态文案 + X 关闭；下拉手势已移除） */}
      <div className="quiz-swipe-hint" onPointerDown={(e) => e.stopPropagation()}>
        <div className="quiz-swipe-hint-left">
          <span>学习方案概览</span>
        </div>
        <button className="quiz-hint-close" onClick={onClose} title="关闭">
          <X size={14} />
        </button>
      </div>

      {/* 三栏主体 */}
      <div className="ps-layout">
        {/* 左栏：纵向阶段导航 */}
        <PhaseNav phases={plan.phases} activeIndex={activePhase} onSelect={handleSelectPhase} />
        {/* 中栏：主干 + 分支画板 */}
        <PhaseCanvas units={phase.units} selected={selected} onSelect={setSelected} />
        {/* 右栏：详情 */}
        <PhaseDetail phase={phase} units={phase.units} selected={selected} />
      </div>

      {/* 底部按钮 */}
      <div className="ps-layout-actions">
        <button className="ps-btn ps-btn-secondary" type="button">
          调整计划
        </button>
      </div>
    </div>
  );
}
