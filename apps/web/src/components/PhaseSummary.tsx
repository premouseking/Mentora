import { Check, Pencil, Undo2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MentoraLoader } from "./MentoraLoader";

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
            { id: "p1-u1-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true, knowledge_point: "集合的概念", materials: [{ id: "m-1-1", title: "集合概念讲义.pdf" }] },
            { id: "p1-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 40, required: true, materials: [{ id: "m-1-2", title: "集合运算练习.pdf" }] },
            { id: "p1-u1-t3", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true, knowledge_point: "命题与逻辑", materials: [{ id: "m-1-3", title: "命题与逻辑讲义.pdf" }] },
            { id: "p1-u1-t4", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 40, required: true, materials: [] },
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
            { id: "p1-u2-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 50, required: true, knowledge_point: "函数的定义", materials: [{ id: "m-2-1", title: "函数定义讲义.pdf" }] },
            { id: "p1-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 50, required: true, materials: [{ id: "m-2-2", title: "定义域值域练习.pdf" }] },
            { id: "p1-u2-t3", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 50, required: true, knowledge_point: "函数的表示方法", materials: [] },
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
            { id: "p1-u3-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true, knowledge_point: "正比例函数", materials: [{ id: "m-3-1", title: "正比例函数讲义.pdf" }] },
            { id: "p1-u3-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-3-2", title: "反比例函数练习.pdf" }] },
            { id: "p1-u3-t3", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true, knowledge_point: "一次函数", materials: [{ id: "m-3-3", title: "一次函数讲义.pdf" }] },
            { id: "p1-u3-t4", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-3-4", title: "二次函数复习题.pdf" }] },
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
            { id: "p2-u1-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 60, required: true, knowledge_point: "数列的概念", materials: [{ id: "m-4-1", title: "数列概念讲义.pdf" }] },
            { id: "p2-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-4-2", title: "数列求和练习.pdf" }] },
            { id: "p2-u1-t3", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 60, required: true, knowledge_point: "极限的探究", materials: [{ id: "m-4-3", title: "极限探究项目.pdf" }] },
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
            { id: "p2-u2-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 50, required: true, knowledge_point: "三角函数的定义", materials: [{ id: "m-5-1", title: "三角函数讲义.pdf" }] },
            { id: "p2-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 50, required: true, materials: [{ id: "m-5-2", title: "三角恒等变换练习.pdf" }] },
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
            { id: "p3-u1-t1", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [{ id: "m-6-1", title: "函数题型专项训练.pdf" }] },
            { id: "p3-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [] },
            { id: "p3-u1-t3", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [{ id: "m-6-2", title: "函数易错题回顾.pdf" }] },
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
            { id: "p3-u2-t1", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [{ id: "m-7-1", title: "几何题型专项训练.pdf" }] },
            { id: "p3-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [] },
            { id: "p3-u2-t3", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 90, required: true, knowledge_point: "立体几何综合", materials: [{ id: "m-7-2", title: "立体几何综合项目.pdf" }] },
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
            { id: "p4-u1-t1", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 120, required: true, knowledge_point: "高考真题实战", materials: [{ id: "m-8-1", title: "2025高考真题集.pdf" }] },
            { id: "p4-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 120, required: true, materials: [{ id: "m-8-2", title: "真题分类训练.pdf" }] },
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
            { id: "p4-u2-t1", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 80, required: true, knowledge_point: "跨章节综合", materials: [{ id: "m-9-1", title: "跨章节综合项目.pdf" }] },
            { id: "p4-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 80, required: true, materials: [] },
            { id: "p4-u2-t3", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 80, required: true, materials: [{ id: "m-9-2", title: "综合题解题思路.pdf" }] },
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
            { id: "p5-u1-t1", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [{ id: "m-10-1", title: "考点全回顾.pdf" }] },
            { id: "p5-u1-t2", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 90, required: true, knowledge_point: "临场策略", materials: [{ id: "m-10-2", title: "临场策略讲义.pdf" }] },
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
            { id: "p5-u2-t1", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 120, required: true, knowledge_point: "限时模拟", materials: [{ id: "m-11-1", title: "限时模拟卷A.pdf" }, { id: "m-11-2", title: "限时模拟卷B.pdf" }] },
            { id: "p5-u2-t2", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-11-3", title: "模拟卷讲评.pdf" }] },
          ],
        },
      ],
    },
  ],
};

/* ── mock 学习档案（建课阶段收集的学生画像） ── */
interface ProfileItem {
  key: string;
  title: string;
  value: string;
}

const MOCK_PROFILE: ProfileItem[] = [
  { key: "goal", title: "学习目标", value: "高中数学系统复习，备战高考" },
  { key: "level", title: "当前基础", value: "中等偏上，函数部分薄弱" },
  { key: "pace", title: "推进方式", value: "按知识板块逐步推进" },
  { key: "timeBudget", title: "每日时长", value: "2~3 小时" },
  { key: "deadline", title: "目标日期", value: "2026-08-15" },
  { key: "school", title: "学校/地区", value: "华南师大附中" },
];

/* ── 初始已完成任务（mock 数据） ── */
const COMPLETED_TASKS_INIT = [
  // 第一阶段第一章「集合与逻辑」：全部完成
  "p1-u1-t1", "p1-u1-t2", "p1-u1-t3", "p1-u1-t4",
  // 第一阶段第二章「函数基础」：前两个任务完成
  "p1-u2-t1", "p1-u2-t2",
];

/* ── AI 对话阶段 ── */
type ChatStage = "input" | "options" | "ai-thinking" | "ai-result";

/* ── 时间选项 ── */
const TIME_OPTIONS = [
  "每天 1 小时以内",
  "每天 1～2 小时",
  "每天 2～3 小时",
  "每天 3～4 小时",
  "每天 4 小时以上",
  "不固定，根据进度灵活安排",
];

/* ── 任务类型标签 ── */

const TASK_TYPE_LABEL: Record<string, string> = {
  lecture: "讲解",
  exercise: "练习",
  project: "项目",
  review: "复习",
};

function formatMinutes(m: number): string {
  if (m >= 60) return `${Math.round(m / 60 * 10) / 10} 小时`;
  return `${m} 分钟`;
}

/* ── 左栏：纵向阶段导航（复用建课确认页滑轨逻辑，方向横→纵）── */

type NavPhase = { id: string; title: string };

function offsetOf(index: number, blockBasis: number) {
  if (index <= 0) return 0;
  return index * blockBasis - 14 * index;
}

function PhaseNav({
  phases,
  activeIndex,
  completedIndices,
  onSelect,
}: {
  phases: NavPhase[];
  activeIndex: number;
  completedIndices: Set<number>;
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
            className={`ps-phase-nav-block${i === activeIndex ? " active" : ""}${completedIndices.has(i) ? " completed" : ""}`}
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
      label: t.task_type === "lecture" || t.task_type === "project"
        ? (t.knowledge_point ?? `${TASK_TYPE_LABEL[t.task_type] ?? t.task_type} ${j + 1}`)
        : `${TASK_TYPE_LABEL[t.task_type] ?? t.task_type} ${j + 1}`,
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
  completedTasks,
  onSelect,
}: {
  units: typeof MOCK_PLAN.phases[0]["units"];
  selected: Selection;
  completedTasks: Set<string>;
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
          {chapters.map((ch) => {
            const chAllDone = units.find((u) => u.id === ch.id)?.tasks.every((t) => completedTasks.has(t.id)) ?? false;
            return (
            <div key={ch.id}>
              <button
                type="button"
                className={`ps-node ps-node-chapter${selected?.kind === "chapter" && selected.id === ch.id ? " selected" : ""}${chAllDone ? " completed" : ""}`}
                style={{ left: ch.x, top: ch.y, width: ch.w, height: ch.h }}
                onClick={() => onSelect({ kind: "chapter", id: ch.id })}
              >
                {ch.title}
              </button>
              {ch.tasks.map((t) => {
                const tDone = completedTasks.has(t.id);
                return (
                <button
                  key={t.id}
                  type="button"
                  className={`ps-node ps-node-task${selected?.kind === "task" && selected.id === t.id ? " selected" : ""}${tDone ? " completed" : ""}`}
                  style={{ left: t.x, top: t.y, width: t.w, height: t.h }}
                  onClick={() => onSelect({ kind: "task", id: t.id })}
                >
                  {t.label}
                </button>
                );
              })}
            </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ── 调整面板：学习计划概览画布（横向章节 + SVG 箭头）── */

const OV_CANVAS = {
  UNIT_W: 150,
  UNIT_H: 44,
  ARROW_W: 60,
  PAD_H: 20,
  PAD_V: 14,
};

type OverviewUnitNode = {
  id: string;
  title: string;
  position: number;
  x: number;
  y: number;
  w: number;
  h: number;
};

function computeOverviewLayout(units: typeof MOCK_PLAN.phases[0]["units"]) {
  const N = units.length;
  const contentW = 2 * OV_CANVAS.PAD_H + N * OV_CANVAS.UNIT_W + Math.max(0, N - 1) * OV_CANVAS.ARROW_W;
  const contentH = 2 * OV_CANVAS.PAD_V + OV_CANVAS.UNIT_H;
  const nodes: OverviewUnitNode[] = units.map((u, i) => ({
    id: u.id,
    title: u.title || `第 ${u.position + 1} 章`,
    position: u.position,
    x: OV_CANVAS.PAD_H + i * (OV_CANVAS.UNIT_W + OV_CANVAS.ARROW_W),
    y: OV_CANVAS.PAD_V,
    w: OV_CANVAS.UNIT_W,
    h: OV_CANVAS.UNIT_H,
  }));
  return { contentW, contentH, nodes };
}

function PlanOverviewCanvas({
  units,
  selectedUnitId,
  onSelectUnit,
}: {
  units: typeof MOCK_PLAN.phases[0]["units"];
  selectedUnitId: string | null;
  onSelectUnit: (unitId: string | null) => void;
}) {
  const layout = useMemo(() => computeOverviewLayout(units), [units]);
  const { contentW, contentH, nodes } = layout;

  return (
    <div className="ps-adjust-plan-canvas">
      <div
        className="ps-adjust-plan-canvas-scroll"
        style={{ minWidth: contentW, minHeight: contentH }}
      >
        <div
          className="ps-adjust-plan-canvas-content"
          style={{ width: contentW + 1, height: contentH }}
        >
          {/* SVG 箭头层 */}
          <svg
            className="ps-adjust-plan-canvas-svg"
            width={contentW}
            height={contentH}
            viewBox={`0 0 ${contentW} ${contentH}`}
          >
            <defs>
              <marker
                id="ps-overview-arrow"
                markerWidth="10"
                markerHeight="10"
                refX="9"
                refY="5"
                orient="auto"
              >
                <path
                  d="M2,2 L9,5 L2,8"
                  fill="none"
                  stroke="var(--border-strong)"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </marker>
            </defs>
            {nodes.map((n, i) => {
              if (i >= nodes.length - 1) return null;
              const next = nodes[i + 1];
              const cy = n.y + n.h / 2;
              return (
                <line
                  key={`oa-${n.id}`}
                  x1={n.x + n.w}
                  y1={cy}
                  x2={next.x}
                  y2={cy}
                  stroke="var(--border-strong)"
                  strokeWidth="1.5"
                  markerEnd="url(#ps-overview-arrow)"
                />
              );
            })}
          </svg>

          {/* 章节节点 */}
          {nodes.map((n) => (
            <button
              key={n.id}
              type="button"
              className={`ps-overview-unit${selectedUnitId === n.id ? " selected" : ""}`}
              style={{ left: n.x, top: n.y, width: n.w, height: n.h }}
              onClick={() => onSelectUnit(selectedUnitId === n.id ? null : n.id)}
            >
              <span className="ps-overview-unit-pos">{n.position + 1}</span>
              <span className="ps-overview-unit-title">{n.title}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── 右栏：详情 ── */

const DELIVERY_LABEL: Record<string, string> = {
  self_paced: "自学",
  live: "直播",
  hybrid: "混合",
};

const DEPTH_LABEL: Record<string, string> = {
  understand: "理解",
  apply: "应用",
  analyze: "分析",
};

type Material = { id: string; title: string };

type DetailInfo = {
  type: "phase" | "chapter" | "task";
  title: string;
  basics: { label: string; value: string }[];
  summary: string;
  materials: Material[];
  /** 练习任务显示「开始练习」按钮 */
  showStartButton: boolean;
  /** 非练习类任务，显示「确认完成」按钮 */
  isKnowledgeTask: boolean;
};

function PhaseDetail({
  phase,
  units,
  selected,
  completedTasks,
  confirmTaskId,
  onOpenMaterial,
  onClose,
  onRequestComplete,
  onCancelConfirm,
  onConfirmComplete,
}: {
  phase: typeof MOCK_PLAN.phases[0];
  units: typeof MOCK_PLAN.phases[0]["units"];
  selected: Selection;
  completedTasks: Set<string>;
  confirmTaskId: string | null;
  onOpenMaterial: (m: Material) => void;
  onClose: () => void;
  onRequestComplete: (taskId: string) => void;
  onCancelConfirm: () => void;
  onConfirmComplete: () => void;
}) {
  const info = useMemo<DetailInfo | null>(() => {
    if (!selected) return null;
    if (selected.kind === "phase") {
      const taskCount = units.reduce((s, u) => s + u.tasks.length, 0);
      return {
        type: "phase",
        title: phase.title,
        basics: [
          { label: "阶段序号", value: `第 ${phase.position + 1} 阶段` },
          { label: "章节数", value: `${units.length} 章` },
          { label: "任务数", value: `${taskCount} 个` },
          { label: "预估时长", value: formatMinutes(phase.estimated_minutes) },
        ],
        summary: phase.objective,
        materials: [],
        showStartButton: false,
        isKnowledgeTask: false,
      };
    }
    if (selected.kind === "chapter") {
      const u = units.find((u) => u.id === selected.id);
      if (!u) return null;
      return {
        type: "chapter",
        title: u.title || `单元 ${u.position + 1}`,
        basics: [
          { label: "章节序号", value: `第 ${u.position + 1} 章` },
          { label: "任务数", value: `${u.tasks.length} 个` },
          { label: "目标深度", value: DEPTH_LABEL[u.target_depth] ?? u.target_depth },
          { label: "预估时长", value: formatMinutes(u.estimated_minutes) },
        ],
        summary: `本章节包含 ${u.tasks.length} 个学习任务，涵盖${u.tasks.map((t) => TASK_TYPE_LABEL[t.task_type] ?? t.task_type).join("、")}等类型，预计用时 ${formatMinutes(u.estimated_minutes)}。`,
        materials: [],
        showStartButton: false,
        isKnowledgeTask: false,
      };
    }
    for (const u of units) {
      const t = u.tasks.find((t) => t.id === selected.id);
      if (t) {
        const typeLabel = TASK_TYPE_LABEL[t.task_type] ?? t.task_type;
        const isExercise = t.task_type === "exercise";
        // 讲解任务的任务类型显示为「知识点」
        const typeDisplay = t.task_type === "lecture" ? "知识点" : typeLabel;
        // 标题：讲解/项目用知识点名，练习用「练习 N」
        const taskIdx = u.tasks.indexOf(t);
        const title = (t.task_type === "lecture" || t.task_type === "project")
          ? (t.knowledge_point ?? `${typeLabel} ${taskIdx + 1}`)
          : `${typeLabel} ${taskIdx + 1}`;
        // 交付方式：讲解→自主确认，练习→完成练习，其他沿用 delivery_mode 映射
        const delivery = isExercise ? "完成练习"
          : t.task_type === "lecture" ? "自主确认"
          : (DELIVERY_LABEL[t.delivery_mode] ?? t.delivery_mode);
        return {
          type: "task",
          title,
          basics: [
            { label: "任务类型", value: typeDisplay },
            { label: "交付方式", value: delivery },
            { label: "预估时长", value: formatMinutes(t.estimated_minutes) },
            { label: "是否必修", value: t.required ? "必修" : "选修" },
          ],
          summary: isExercise
            ? `通过完成练习巩固「${u.title || "本章节"}」的知识点，预计用时 ${formatMinutes(t.estimated_minutes)}。`
            : t.task_type === "lecture"
            ? `学习知识点「${t.knowledge_point ?? title}」，理解其在「${u.title || "本章节"}」中的应用，预计用时 ${formatMinutes(t.estimated_minutes)}。`
            : `通过项目实践巩固「${t.knowledge_point ?? title}」，预计用时 ${formatMinutes(t.estimated_minutes)}。`,
          materials: t.materials ?? [],
          showStartButton: isExercise,
          isKnowledgeTask: !isExercise,
        };
      }
    }
    return null;
  }, [selected, units, phase]);

  if (!info) {
    return (
      <div className="ps-detail">
        <p className="ps-detail-empty">点击章节或任务查看详情</p>
      </div>
    );
  }

  return (
    <div className="ps-detail">
      <div className="ps-detail-badge">{info.type === "phase" ? "阶段" : info.type === "chapter" ? "章节" : "任务"}</div>
      <h3 className="ps-detail-title">{info.title}</h3>

      {/* 基础信息 */}
      <div className="ps-detail-section">
        <div className="ps-detail-section-head">基础信息</div>
        <dl className="ps-detail-basics">
          {info.basics.map((b) => (
            <div className="ps-detail-basic-row" key={b.label}>
              <dt>{b.label}</dt>
              <dd>{b.value}</dd>
            </div>
          ))}
        </dl>
      </div>

      {/* 概述 */}
      <div className="ps-detail-section">
        <div className="ps-detail-section-head">概述</div>
        <p className="ps-detail-summary">{info.summary}</p>
      </div>

      {/* 相关资料 */}
      {info.type === "task" && (
        <div className="ps-detail-section">
          <div className="ps-detail-section-head">相关资料</div>
          {info.materials.length === 0 ? (
            <p className="ps-detail-no-materials">暂无关联资料</p>
          ) : (
            <div className="ps-detail-materials">
              {info.materials.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  className="ps-detail-material-btn"
                  onClick={() => onOpenMaterial(m)}
                  title={m.title}
                >
                  {m.title}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 任务底部操作区：已完成 → ✓ 已完成；未完成 → 练习/知识点各自按钮 */}
      {info.type === "task" && selected && selected.kind === "task" && (
        <>
          {completedTasks.has(selected.id) ? (
            <div className="ps-detail-done-badge">✓ 已完成</div>
          ) : info.showStartButton ? (
            <button type="button" className="ps-detail-start-btn" onClick={onClose}>
              开始练习
            </button>
          ) : (
            <button
              type="button"
              className="ps-detail-complete-btn"
              onClick={(e) => { e.stopPropagation(); onRequestComplete(selected.id); }}
            >
              确认完成
            </button>
          )}
        </>
      )}

      {/* 二次确认弹窗 */}
      {confirmTaskId && selected && selected.kind === "task" && confirmTaskId === selected.id && (
        <div className="ps-confirm-overlay" onPointerDown={(e) => e.stopPropagation()}>
          <div className="ps-confirm-dialog">
            <p className="ps-confirm-text">确认已完成此学习任务？</p>
            <p className="ps-confirm-hint">完成后将更新学习进度</p>
            <div className="ps-confirm-actions">
              <button className="ps-confirm-cancel" type="button" onClick={(e) => { e.stopPropagation(); onCancelConfirm(); }}>
                取消
              </button>
              <button className="ps-confirm-ok" type="button" onClick={(e) => { e.stopPropagation(); onConfirmComplete(); }}>
                确认完成
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


/* ── 主体：v6 三栏布局 ── */

/** 计算 phase-track 中 block 在给定 index 的 offsetLeft（含 margin-left: -4px 累积偏移） */
function phaseTrackOffsetOf(index: number, blockBasis: number) {
  if (index <= 0) return 0;
  return index * blockBasis - 4 * index;
}

export function PhaseSummary({
  onClose,
}: {
  onClose: () => void;
}) {
  const plan = MOCK_PLAN;
  const [activePhase, setActivePhase] = useState(0);
  const [selected, setSelected] = useState<Selection>({ kind: "phase", id: plan.phases[0].id });
  const [completedTasks, setCompletedTasks] = useState<Set<string>>(
    () => new Set(COMPLETED_TASKS_INIT),
  );
  const [confirmTaskId, setConfirmTaskId] = useState<string | null>(null);
  const [adjustMode, setAdjustMode] = useState(false);
  // 调整面板状态
  const [chatStage, setChatStage] = useState<ChatStage>("input");
  const [chatInput, setChatInput] = useState("");
  const [selectedOption, setSelectedOption] = useState("");
  const [profileEditing, setProfileEditing] = useState(false);
  const [profileValues, setProfileValues] = useState<ProfileItem[]>(() =>
    MOCK_PROFILE.map((p) => ({ ...p })),
  );
  const [planEditing, setPlanEditing] = useState(false);
  // 三区变更追踪
  const [chatChanged, setChatChanged] = useState(false);
  const [profileChanged, setProfileChanged] = useState(false);
  const [planChanged, setPlanChanged] = useState(false);
  const [planGenerated, setPlanGenerated] = useState(false);
  const phase = plan.phases[activePhase];

  // 已完成的阶段索引
  const completedPhaseIndices = useMemo(() => {
    const result = new Set<number>();
    plan.phases.forEach((p, pi) => {
      if (p.units.length > 0 && p.units.every((u) => u.tasks.every((t) => completedTasks.has(t.id)))) {
        result.add(pi);
      }
    });
    return result;
  }, [plan.phases, completedTasks]);

  // 点击左栏阶段块：未选中→切换阶段并显示阶段信息；已选中→仅把右栏切回阶段信息
  const handleSelectPhase = useCallback((i: number) => {
    setActivePhase(i);
    setSelected({ kind: "phase", id: plan.phases[i].id });
  }, [plan.phases]);

  // 点击资料按钮：关闭上划栏（mock 阶段不实际跳转资料页）
  const handleOpenMaterial = useCallback(() => {
    onClose();
  }, [onClose]);

  // 完成确认相关
  const handleRequestComplete = useCallback((taskId: string) => {
    setConfirmTaskId(taskId);
  }, []);

  const handleCancelConfirm = useCallback(() => {
    setConfirmTaskId(null);
  }, []);

  const handleConfirmComplete = useCallback(() => {
    if (confirmTaskId) {
      setCompletedTasks((prev) => {
        const next = new Set(prev);
        next.add(confirmTaskId);
        return next;
      });
      setConfirmTaskId(null);
    }
  }, [confirmTaskId]);

  // ── 调整面板事件处理 ──

  const handleChatSend = useCallback(() => {
    const text = chatInput.trim();
    if (!text) return;
    setChatInput("");
    setChatChanged(true);
    setChatStage("options");
  }, [chatInput]);

  const handleOptionSelect = useCallback((option: string) => {
    setSelectedOption(option);
    setChatChanged(true);
  }, []);

  /** 清空三区 dirty 状态（星号消失） */
  const clearAllDirty = useCallback(() => {
    setChatChanged(false);
    setProfileChanged(false);
    setPlanChanged(false);
  }, []);

  const handleGeneratePlan = useCallback(() => {
    clearAllDirty();
    setPlanGenerated(true);
  }, [clearAllDirty]);

  const handleContinueAdjust = useCallback(() => {
    clearAllDirty();
    // planGenerated 不清，保持上一轮的状态
  }, [clearAllDirty]);

  const handleProfileEditToggle = useCallback(() => {
    if (profileEditing) {
      // ✓ → 标记已更改，退出编辑（不触发 AI）
      setProfileEditing(false);
      setProfileChanged(true);
    } else {
      setProfileEditing(true);
    }
  }, [profileEditing]);

  const handleProfileEditCancel = useCallback(() => {
    setProfileEditing(false);
    // 恢复到本次编辑前的状态（可能已是 dirty 状态的旧值）
    setProfileValues(MOCK_PROFILE.map((p) => ({ ...p })));
  }, []);

  /** 撤回档案更改：恢复原始值 + 清除 dirty */
  const handleProfileUndo = useCallback(() => {
    setProfileChanged(false);
    setProfileValues(MOCK_PROFILE.map((p) => ({ ...p })));
  }, []);

  const handleProfileValueChange = useCallback((key: string, value: string) => {
    setProfileValues((prev) => prev.map((p) => (p.key === key ? { ...p, value } : p)));
  }, []);

  const handlePlanEditToggle = useCallback(() => {
    if (planEditing) {
      // ✓ → 标记已更改，退出编辑（内容暂不变，待设计）
      setPlanEditing(false);
      setPlanChanged(true);
    } else {
      setPlanEditing(true);
    }
  }, [planEditing]);

  const handlePlanEditCancel = useCallback(() => {
    setPlanEditing(false);
  }, []);

  const handlePlanUndo = useCallback(() => {
    setPlanChanged(false);
  }, []);

  // ── AI 对话栏变更提示小字 ──

  const dirtyHint = useMemo(() => {
    const parts: string[] = [];
    if (chatChanged) parts.push("已说明需求");
    if (profileChanged) parts.push("已更改学习档案");
    if (planChanged) parts.push("已更改学习计划");
    return parts.length > 0 ? `${parts.join("；")}。发送给AI以确认更改。` : "";
  }, [chatChanged, profileChanged, planChanged]);

  // ── 学习计划概览：阶段导航滑轨（复刻确认页 phase-track）──

  const [trackPhaseIndex, setTrackPhaseIndex] = useState(0);
  const [overviewSelectedUnitId, setOverviewSelectedUnitId] = useState<string | null>(null);
  const trackTargetRef = useRef(0);
  const trackNavRef = useRef<HTMLDivElement>(null);
  const trackN = plan.phases.length;

  const scrollTrackTo = useCallback(
    (index: number) => {
      const el = trackNavRef.current;
      if (!el) return;
      const prevIndex = trackTargetRef.current;
      trackTargetRef.current = index;
      setTrackPhaseIndex(index);
      const basis = el.clientWidth / 4;
      const dir = index - prevIndex;
      // 右滚：选中项靠右（位置 2），锚点 = index - 2
      // 左滚：选中项靠左（位置 1），锚点 = index - 1
      const snapIndex =
        dir > 0
          ? Math.max(0, Math.min(index - 2, trackN - 4))
          : Math.max(0, index - 1);
      el.scrollTo({ left: phaseTrackOffsetOf(snapIndex, basis), behavior: "smooth" });
    },
    [trackN],
  );

  const handleTrackWheel = useCallback(
    (e: WheelEvent) => {
      // 只拦截纵向滚动（横向滚动留给 overflow-x: auto 原生行为）
      if (Math.abs(e.deltaY) <= Math.abs(e.deltaX)) {
        e.stopPropagation();
        return;
      }
      e.preventDefault();
      e.stopPropagation();
      if (trackN <= 1) return;
      const dir = e.deltaY > 0 ? 1 : -1;
      const next = Math.max(0, Math.min(trackN - 1, trackTargetRef.current + dir));
      if (next === trackTargetRef.current) return;
      scrollTrackTo(next);
    },
    [trackN, scrollTrackTo],
  );

  // 原生事件监听（passive: false 确保 preventDefault 生效）
  useEffect(() => {
    const el = trackNavRef.current;
    if (!el) return;
    el.addEventListener("wheel", handleTrackWheel, { passive: false });
    return () => el.removeEventListener("wheel", handleTrackWheel);
  }, [handleTrackWheel, adjustMode]);

  const handleTrackClick = useCallback(
    (index: number) => {
      if (index === trackTargetRef.current) {
        // 已选中当前阶段：回到阶段信息
        setOverviewSelectedUnitId(null);
        return;
      }
      setOverviewSelectedUnitId(null);
      scrollTrackTo(index);
    },
    [scrollTrackTo],
  );

  return (
    <div className="phase-summary">
      {/* 顶部栏：关闭按钮 → 返回按钮 */}
      <div className="quiz-swipe-hint" onPointerDown={(e) => e.stopPropagation()}>
        <div className="quiz-swipe-hint-left">
          <span>{adjustMode ? "调整学习方案" : "学习计划"}</span>
        </div>
        {adjustMode ? (
          <button className="quiz-hint-close" onClick={() => setAdjustMode(false)} title="返回">
            <Undo2 size={14} />
          </button>
        ) : (
          <button className="quiz-hint-close" onClick={onClose} title="关闭">
            <X size={14} />
          </button>
        )}
      </div>

      {adjustMode ? (
        <>
          <div className="ps-adjust-body">
          {/* 1. AI 对话栏目 */}
          <div className="ps-adjust-section ps-adjust-chat">
            <h2 className="ps-adjust-chat-heading">调整学习方案</h2>
            <p className="ps-adjust-chat-subtitle">与 AI 讨论你想如何调整学习方案</p>

            {chatStage === "input" && (
              <div className="ps-adjust-chat-input-area">
                <textarea
                  className="ps-adjust-chat-textarea"
                  placeholder="描述你想要的调整…"
                  value={chatInput}
                  onChange={(e) => { setChatInput(e.target.value); if (e.target.value.trim()) setChatChanged(true); }}
                  onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleChatSend(); } }}
                  rows={4}
                />
                <div className="ps-adjust-chat-send-row">
                  {dirtyHint && <span className="ps-adjust-chat-hint">{dirtyHint}</span>}
                  <button
                    className={`ps-adjust-chat-send${chatInput.trim() ? "" : " empty"}`}
                    type="button"
                    onClick={handleChatSend}
                  >
                    发送
                  </button>
                </div>
              </div>
            )}

            {chatStage === "options" && (
              <div className="ps-adjust-options-area">
                <h3 className="ps-adjust-options-subtitle">新的学习时长安排</h3>
                <div className="ps-adjust-options-list">
                  {TIME_OPTIONS.map((opt) => (
                    <button
                      key={opt}
                      className={`ps-adjust-option-btn${selectedOption === opt ? " selected" : ""}`}
                      type="button"
                      onClick={() => handleOptionSelect(opt)}
                    >
                      {opt}
                    </button>
                  ))}
                </div>
                {dirtyHint && <p className="ps-adjust-chat-hint ps-adjust-chat-hint-block">{dirtyHint}</p>}
                <div className="ps-adjust-options-actions">
                  <button className="ps-btn ps-btn-primary" type="button" disabled={!selectedOption} onClick={handleGeneratePlan}>
                    确认并生成学习方案
                  </button>
                  <button className="ps-btn ps-btn-secondary" type="button" disabled={!selectedOption} onClick={handleContinueAdjust}>
                    确认并继续调整
                  </button>
                </div>
              </div>
            )}

            {chatStage === "ai-thinking" && (
              <div className="ps-adjust-thinking">
                <MentoraLoader message="AI 正在分析你的档案调整…" size={120} />
              </div>
            )}

            {chatStage === "ai-result" && (
              <div className="ps-adjust-result-area">
                <div className="ps-adjust-result-box">
                  我已经查看了你修改后的学习档案，你现在的基础和目标与之前相比有一些变化。是否需要继续为你调整方案，还是直接生成学习方案？
                </div>
                {dirtyHint && <p className="ps-adjust-chat-hint ps-adjust-chat-hint-block">{dirtyHint}</p>}
                <div className="ps-adjust-options-actions">
                  <button className="ps-btn ps-btn-primary" type="button" disabled={!selectedOption} onClick={handleGeneratePlan}>
                    确认并生成学习方案
                  </button>
                  <button className="ps-btn ps-btn-secondary" type="button" disabled={!selectedOption} onClick={handleContinueAdjust}>
                    确认并继续调整
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* 2. 学习档案表格 */}
          <div className="ps-adjust-section ps-adjust-profile">
            <div className="ps-adjust-profile-header">
              <div className="ps-adjust-section-title">
                学习档案{profileChanged && <span className="ps-adjust-dirty-star">*</span>}
              </div>
              <div className="ps-adjust-edit-actions">
                {profileEditing ? (
                  <button
                    className="ps-adjust-edit-btn ps-adjust-edit-cancel"
                    type="button"
                    onClick={handleProfileEditCancel}
                    title="取消编辑"
                  >
                    <X size={16} />
                  </button>
                ) : profileChanged ? (
                  <button
                    className="ps-adjust-edit-btn ps-adjust-edit-undo"
                    type="button"
                    onClick={handleProfileUndo}
                    title="撤回更改"
                  >
                    <Undo2 size={14} />
                  </button>
                ) : null}
                <button
                  className="ps-adjust-edit-btn"
                  type="button"
                  onClick={handleProfileEditToggle}
                  title={profileEditing ? "完成编辑" : "编辑档案"}
                >
                  {profileEditing ? <Check size={16} /> : <Pencil size={14} />}
                </button>
              </div>
            </div>
            <table className="ps-adjust-profile-table">
              <thead>
                <tr>
                  <th>项目</th>
                  <th>内容</th>
                </tr>
              </thead>
              <tbody>
                {profileValues.map((item) => (
                  <tr key={item.key}>
                    <td>{item.title}</td>
                    <td>
                      {profileEditing ? (
                        <input
                          className="ps-adjust-profile-input"
                          value={item.value}
                          onChange={(e) => handleProfileValueChange(item.key, e.target.value)}
                        />
                      ) : (
                        item.value
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 3. 学习计划概览（阶段导航滑轨 + 详情占位） */}
          <div className="ps-adjust-section ps-adjust-plan">
            <div className="ps-adjust-profile-header">
              <div className="ps-adjust-section-title">
                学习计划概览{planChanged && <span className="ps-adjust-dirty-star">*</span>}
              </div>
              <div className="ps-adjust-edit-actions">
                {planEditing ? (
                  <button
                    className="ps-adjust-edit-btn ps-adjust-edit-cancel"
                    type="button"
                    onClick={handlePlanEditCancel}
                    title="取消编辑"
                  >
                    <X size={16} />
                  </button>
                ) : planChanged ? (
                  <button
                    className="ps-adjust-edit-btn ps-adjust-edit-undo"
                    type="button"
                    onClick={handlePlanUndo}
                    title="撤回更改"
                  >
                    <Undo2 size={14} />
                  </button>
                ) : null}
                <button
                  className="ps-adjust-edit-btn"
                  type="button"
                  onClick={handlePlanEditToggle}
                  title={planEditing ? "完成编辑" : "编辑计划"}
                >
                  {planEditing ? <Check size={16} /> : <Pencil size={14} />}
                </button>
              </div>
            </div>
            <div className="phase-track" ref={trackNavRef}>
              <div className="phase-track-window">
                {plan.phases.map((p, i) => (
                  <div
                    key={p.id}
                    className={`phase-block${i === trackPhaseIndex ? " active" : ""}`}
                    onClick={() => handleTrackClick(i)}
                  >
                    <span className="phase-block-num">{i + 1}</span>
                    <span className="phase-block-name">{p.title}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* 横向画布：章节 + SVG 箭头 */}
            <PlanOverviewCanvas
              units={plan.phases[trackPhaseIndex].units}
              selectedUnitId={overviewSelectedUnitId}
              onSelectUnit={(id) => setOverviewSelectedUnitId(id)}
            />

            {/* 详情栏 */}
            <div className="ps-adjust-plan-detail">
              {(() => {
                const tp = plan.phases[trackPhaseIndex];
                const selUnit = overviewSelectedUnitId
                  ? tp.units.find((u) => u.id === overviewSelectedUnitId) ?? null
                  : null;

                if (selUnit) {
                  // ── 章节详情 ──
                  const taskCount = selUnit.tasks.length;
                  const allMaterials: { id: string; title: string }[] = [];
                  for (const t of selUnit.tasks) {
                    if (t.materials) allMaterials.push(...t.materials);
                  }
                  const typeSet = new Set(selUnit.tasks.map((t) => TASK_TYPE_LABEL[t.task_type] ?? t.task_type));
                  const summary = `本章节包含 ${taskCount} 个学习任务，涵盖${[...typeSet].join("、")}等类型，预计用时 ${formatMinutes(selUnit.estimated_minutes)}。`;

                  return (
                    <>
                      <div className="ps-adjust-plan-detail-head">
                        <span className="ps-adjust-plan-detail-badge">第 {selUnit.position + 1} 章</span>
                        <span className="ps-adjust-plan-detail-title">{selUnit.title || `第 ${selUnit.position + 1} 章`}</span>
                      </div>

                      {/* 基础信息 */}
                      <div className="ps-detail-section">
                        <div className="ps-detail-section-head">基础信息</div>
                        <dl className="ps-detail-basics">
                          <div className="ps-detail-basic-row">
                            <dt>章节序号</dt>
                            <dd>第 {selUnit.position + 1} 章</dd>
                          </div>
                          <div className="ps-detail-basic-row">
                            <dt>任务数</dt>
                            <dd>{taskCount} 个</dd>
                          </div>
                          <div className="ps-detail-basic-row">
                            <dt>目标深度</dt>
                            <dd>{DEPTH_LABEL[selUnit.target_depth] ?? selUnit.target_depth}</dd>
                          </div>
                          <div className="ps-detail-basic-row">
                            <dt>预估时长</dt>
                            <dd>{formatMinutes(selUnit.estimated_minutes)}</dd>
                          </div>
                        </dl>
                      </div>

                      {/* 概述 */}
                      <div className="ps-detail-section">
                        <div className="ps-detail-section-head">概述</div>
                        <p className="ps-detail-summary">{summary}</p>
                      </div>

                      {/* 相关资料 */}
                      {allMaterials.length > 0 && (
                        <div className="ps-detail-section">
                          <div className="ps-detail-section-head">相关资料</div>
                          <ul className="ps-detail-materials">
                            {allMaterials.map((m) => (
                              <li key={m.id} className="ps-detail-material-item">
                                <span className="ps-detail-material-name">{m.title}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </>
                  );
                }

                // ── 阶段详情 ──
                const taskCount = tp.units.reduce((s, u) => s + u.tasks.length, 0);
                return (
                  <>
                    <div className="ps-adjust-plan-detail-head">
                      <span className="ps-adjust-plan-detail-badge">第 {tp.position + 1} 阶段</span>
                      <span className="ps-adjust-plan-detail-title">{tp.title}</span>
                    </div>

                    {/* 基础信息 */}
                    <div className="ps-detail-section">
                      <div className="ps-detail-section-head">基础信息</div>
                      <dl className="ps-detail-basics">
                        <div className="ps-detail-basic-row">
                          <dt>阶段序号</dt>
                          <dd>第 {tp.position + 1} 阶段</dd>
                        </div>
                        <div className="ps-detail-basic-row">
                          <dt>章节数</dt>
                          <dd>{tp.units.length} 章</dd>
                        </div>
                        <div className="ps-detail-basic-row">
                          <dt>任务数</dt>
                          <dd>{taskCount} 个</dd>
                        </div>
                        <div className="ps-detail-basic-row">
                          <dt>预估时长</dt>
                          <dd>{formatMinutes(tp.estimated_minutes)}</dd>
                        </div>
                      </dl>
                    </div>

                    {/* 概述 */}
                    <div className="ps-detail-section">
                      <div className="ps-detail-section-head">概述</div>
                      <p className="ps-detail-summary">{tp.objective}</p>
                    </div>
                  </>
                );
              })()}
            </div>
          </div>
        </div>
        <div className="ps-adjust-footer">
          <button
            className={`ps-btn ps-adjust-confirm-btn${planGenerated && !profileChanged && !planChanged ? " active" : ""}`}
            type="button"
            disabled={!(planGenerated && !profileChanged && !planChanged)}
            onClick={() => setAdjustMode(false)}
          >
            确认方案
          </button>
        </div>
        </>
      ) : (
        <>
          {/* 三栏主体 */}
          <div className="ps-layout">
            {/* 左栏：纵向阶段导航 */}
            <PhaseNav phases={plan.phases} activeIndex={activePhase} completedIndices={completedPhaseIndices} onSelect={handleSelectPhase} />
            {/* 中栏：主干 + 分支画板 */}
            <PhaseCanvas units={phase.units} selected={selected} completedTasks={completedTasks} onSelect={setSelected} />
            {/* 右栏：详情 */}
            <PhaseDetail
              phase={phase}
              units={phase.units}
              selected={selected}
              completedTasks={completedTasks}
              confirmTaskId={confirmTaskId}
              onOpenMaterial={handleOpenMaterial}
              onClose={onClose}
              onRequestComplete={handleRequestComplete}
              onCancelConfirm={handleCancelConfirm}
              onConfirmComplete={handleConfirmComplete}
            />
          </div>

          {/* 底部按钮 */}
          <div className="ps-layout-actions">
            <button className="ps-btn ps-btn-secondary" type="button" onClick={() => setAdjustMode(true)}>
              调整方案
            </button>
          </div>
        </>
      )}
    </div>
  );
}
