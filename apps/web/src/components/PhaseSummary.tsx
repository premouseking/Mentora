import { Check, GripVertical, Pencil, Plus, Undo2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MentoraLoader } from "./MentoraLoader";
import type { ActivePlan, PlanPhase, PlanUnit } from "../services/courseApi";
import type { CoursePhasesResponse } from "../services/documentApi";
import { completeLearningTask } from "../services/learningApi";
import { COURSE_SESSION_ID_KEY } from "../lib/courseCreationStorage";
import {
  buildTaskDetailSummary,
  getTaskCardLabelForUnit,
  getTaskDeliveryLabel,
  getTaskDetailTitle,
  getTaskTypeDetailLabel,
  resolveTaskStartPath,
  summarizeUnitTasks,
} from "../pages/courseFlowHelpers";

/* ── Mock 数据（v6：全部 mock，不连后端）── */

interface PoolPhase {
  id: string;
  title: string;
  objective: string;
}

const MOCK_PHASE_POOL: PoolPhase[] = [
  { id: "pool-k1", title: "知识衔接", objective: "补齐前置知识缺口" },
  { id: "pool-k2", title: "习题强化", objective: "大量针对性练习，巩固薄弱环节" },
  { id: "pool-k3", title: "阶段测评", objective: "定期检测学习效果，调整方向" },
  { id: "pool-k4", title: "拓展阅读", objective: "拓展学科视野，了解实际应用" },
  { id: "pool-k5", title: "思维训练", objective: "培养逻辑思维与解题策略" },
  { id: "pool-k6", title: "实战模拟", objective: "全真模拟考试，训练应试能力" },
];

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

/* ── 任务类型标签（详情区沿用统一 helper）── */

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
  tkW: 88,
  tkH: 32,
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
function computeLayout(units: PlanUnit[]): Layout {
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
      label: getTaskCardLabelForUnit(tasks, t, j),
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
  units: PlanUnit[];
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

function computeOverviewLayout(units: PlanUnit[]) {
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
  units: PlanUnit[];
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
  onRequestComplete,
  onCancelConfirm,
  onConfirmComplete,
  completingTaskId,
  completionError,
  courseId,
}: {
  phase: PlanPhase;
  units: PlanUnit[];
  selected: Selection;
  completedTasks: Set<string>;
  confirmTaskId: string | null;
  onOpenMaterial: (m: Material) => void;
  onRequestComplete: (taskId: string) => void;
  onCancelConfirm: () => void;
  onConfirmComplete: () => void;
  completingTaskId: string | null;
  completionError: string | null;
  courseId: string;
}) {
  const navigate = useNavigate();
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
        summary: summarizeUnitTasks(u.tasks, u.estimated_minutes),
        materials: [],
        showStartButton: false,
        isKnowledgeTask: false,
      };
    }
    for (const u of units) {
      const t = u.tasks.find((t) => t.id === selected.id);
      if (t) {
        const taskIdx = u.tasks.indexOf(t);
        const title = getTaskDetailTitle(t, taskIdx);
        const isExercise = t.task_type === "exercise";
        const typeDisplay = getTaskTypeDetailLabel(t.task_type);
        const delivery = getTaskDeliveryLabel(t.task_type, t.delivery_mode);
        return {
          type: "task",
          title,
          basics: [
            { label: "任务类型", value: typeDisplay },
            { label: "交付方式", value: delivery },
            { label: "预估时长", value: formatMinutes(t.estimated_minutes) },
            { label: "是否必修", value: t.required ? "必修" : "选修" },
          ],
          summary: buildTaskDetailSummary(
            t,
            u.title || `单元 ${u.position + 1}`,
            taskIdx,
            t.estimated_minutes,
          ),
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
          ) : (
            <button
              type="button"
              className="ps-detail-start-btn"
              onClick={() => navigate(resolveTaskStartPath(courseId, selected.id))}
            >
              开始学习
            </button>
          )}
          <button
            type="button"
            className="ps-detail-complete-btn"
            onClick={(e) => { e.stopPropagation(); onRequestComplete(selected.id); }}
            style={{ marginTop: 8 }}
          >
            确认完成
          </button>
        </>
      )}

      {/* 二次确认弹窗 */}
      {confirmTaskId && selected && selected.kind === "task" && confirmTaskId === selected.id && (
        <div className="ps-confirm-overlay" onPointerDown={(e) => e.stopPropagation()}>
          <div className="ps-confirm-dialog">
            <p className="ps-confirm-text">确认已完成此学习任务？</p>
            <p className="ps-confirm-hint">
              {completionError ?? "完成后将更新学习进度"}
            </p>
            <div className="ps-confirm-actions">
              <button className="ps-confirm-cancel" type="button" onClick={(e) => { e.stopPropagation(); onCancelConfirm(); }}>
                取消
              </button>
              <button className="ps-confirm-ok" type="button" disabled={completingTaskId === confirmTaskId} onClick={(e) => { e.stopPropagation(); onConfirmComplete(); }}>
                {completingTaskId === confirmTaskId ? "提交中…" : "确认完成"}
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
  activePlan,
  phases,
  courseId,
  sessionId,
}: {
  onClose: () => void;
  activePlan: ActivePlan | null;
  phases: CoursePhasesResponse | null;
  courseId: string;
  sessionId: string;
}) {
  const navigate = useNavigate();
  const plan = activePlan?.phases?.length ? activePlan : { phases: [] };
  const firstPhaseId = plan.phases[0]?.id ?? "";
  const [activePhase, setActivePhase] = useState(0);
  const [selected, setSelected] = useState<Selection>({ kind: "phase", id: firstPhaseId });
  const [completedTasks, setCompletedTasks] = useState<Set<string>>(new Set());
  const [confirmTaskId, setConfirmTaskId] = useState<string | null>(null);
  const [completingTaskId, setCompletingTaskId] = useState<string | null>(null);
  const [completionError, setCompletionError] = useState<string | null>(null);
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
  // 阶段编辑表格状态
  const [editPhases, setEditPhases] = useState<{ id: string; title: string; objective: string }[]>([]);
  const [showAddPhase, setShowAddPhase] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  const phase = plan.phases[activePhase] ?? null;

  // 已完成的阶段索引
  const completedPhaseIndices = useMemo(() => {
    const result = new Set<number>();
    plan.phases.forEach((p, pi) => {
      const persistedState = phases?.phases.find((item) => item.id === p.id)?.state;
      if (
        persistedState === "completed"
        || (p.units.length > 0 && p.units.every((u) => u.tasks.every((t) => completedTasks.has(t.id))))
      ) {
        result.add(pi);
      }
    });
    return result;
  }, [plan.phases, phases, completedTasks]);

  // 点击左栏阶段块：未选中→切换阶段并显示阶段信息；已选中→仅把右栏切回阶段信息
  const handleSelectPhase = useCallback((i: number) => {
    setActivePhase(i);
    setSelected({ kind: "phase", id: plan.phases[i].id });
  }, [plan.phases]);

  const handleOpenMaterial = useCallback((material: Material) => {
    onClose();
    const params = new URLSearchParams({ sourceVersionId: material.id });
    navigate(`/courses/${encodeURIComponent(courseId)}?${params.toString()}`);
  }, [courseId, navigate, onClose]);

  // 完成确认相关
  const handleRequestComplete = useCallback((taskId: string) => {
    setCompletionError(null);
    setConfirmTaskId(taskId);
  }, []);

  const handleCancelConfirm = useCallback(() => {
    setConfirmTaskId(null);
  }, []);

  const handleConfirmComplete = useCallback(async () => {
    if (confirmTaskId && completingTaskId === null) {
      setCompletingTaskId(confirmTaskId);
      setCompletionError(null);
      try {
        await completeLearningTask(confirmTaskId);
        setCompletedTasks((prev) => {
          const next = new Set(prev);
          next.add(confirmTaskId);
          return next;
        });
        setConfirmTaskId(null);
      } catch (error) {
        setCompletionError(error instanceof Error ? error.message : "更新学习进度失败");
      } finally {
        setCompletingTaskId(null);
      }
    }
  }, [completingTaskId, confirmTaskId]);

  const handleOpenRealAdjustment = useCallback(() => {
    if (!sessionId) return;
    sessionStorage.setItem(COURSE_SESSION_ID_KEY, sessionId);
    onClose();
    navigate("/courses/new/plan");
  }, [navigate, onClose, sessionId]);

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

  /** 清空三区 dirty 状态（星号消失），退出所有编辑模式 */
  const clearAllDirty = useCallback(() => {
    setChatChanged(false);
    setProfileChanged(false);
    setPlanChanged(false);
    setPlanEditing(false);
    setShowAddPhase(false);
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
      if (planChanged) {
        // 锁定模式 → 重新进入编辑
        setPlanChanged(false);
      } else {
        // 编辑中 → ✓ 确认保存，锁定表格
        setPlanChanged(true);
      }
    } else {
      setPlanEditing(true);
      // 进入编辑时拷贝原始阶段列表
      setEditPhases(plan.phases.map((p) => ({ id: p.id, title: p.title, objective: p.objective })));
    }
  }, [planEditing, planChanged]);

  const handlePlanEditCancel = useCallback(() => {
    // ✕ → 退出编辑，恢复原始阶段列表
    setPlanEditing(false);
    setPlanChanged(false);
    setShowAddPhase(false);
  }, []);

  /** 撤回计划更改：恢复原始阶段列表 + 退出编辑 + 清除 dirty */
  const handlePlanUndo = useCallback(() => {
    setPlanEditing(false);
    setPlanChanged(false);
    setShowAddPhase(false);
  }, []);

  // ── 阶段编辑表格：拖拽排序 ──

  const handlePhaseDragStart = useCallback((e: React.DragEvent, index: number) => {
    setDragIndex(index);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", String(index));
  }, []);

  const handlePhaseDragOver = useCallback((e: React.DragEvent, index: number) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (dragIndex === null || dragIndex === index) return;
    setEditPhases((prev) => {
      const next = [...prev];
      const [moved] = next.splice(dragIndex, 1);
      next.splice(index, 0, moved);
      return next;
    });
    setDragIndex(index);
  }, [dragIndex]);

  const handlePhaseDragEnd = useCallback(() => {
    setDragIndex(null);
  }, []);

  const handleAddPhase = useCallback((poolPhase: PoolPhase) => {
    setEditPhases((prev) => [
      ...prev,
      {
        id: poolPhase.id,
        position: prev.length,
        title: poolPhase.title,
        objective: poolPhase.objective,
        estimated_minutes: 0,
        units: [],
      },
    ]);
    setShowAddPhase(false);
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
  const [overviewSelectedTaskId, setOverviewSelectedTaskId] = useState<string | null>(null);
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

          {/* 3. 学习计划概览 */}
          <div className="ps-adjust-section ps-adjust-plan">
            <div className="ps-adjust-profile-header">
              <div className="ps-adjust-section-title">
                学习计划概览{planChanged && <span className="ps-adjust-dirty-star">*</span>}
              </div>
              <div className="ps-adjust-edit-actions">
                {/* planChanged → ↩ 撤回（任何时候只要有改动就显示） */}
                {planChanged && (
                  <button
                    className="ps-adjust-edit-btn ps-adjust-edit-undo"
                    type="button"
                    onClick={handlePlanUndo}
                    title="撤回更改"
                  >
                    <Undo2 size={14} />
                  </button>
                )}
                {/* planEditing && !planChanged → ✕ 取消 */}
                {planEditing && !planChanged && (
                  <button
                    className="ps-adjust-edit-btn ps-adjust-edit-cancel"
                    type="button"
                    onClick={handlePlanEditCancel}
                    title="取消编辑"
                  >
                    <X size={16} />
                  </button>
                )}
                <button
                  className="ps-adjust-edit-btn"
                  type="button"
                  onClick={handlePlanEditToggle}
                  title={planEditing && !planChanged ? "保存更改" : "编辑计划"}
                >
                  {planEditing && !planChanged ? <Check size={16} /> : <Pencil size={14} />}
                </button>
              </div>
            </div>

            {planEditing ? (
              /* ── 阶段编辑表格 ── */
              <div className="ps-plan-edit-table">
                <div className="ps-plan-edit-head">
                  <span className="ps-plan-edit-col-name">阶段</span>
                  <span className="ps-plan-edit-col-desc">简介</span>
                  {!planChanged && <span className="ps-plan-edit-col-grip"></span>}
                </div>
                {editPhases.map((ep, i) => (
                  <div
                    key={ep.id}
                    className={`ps-plan-edit-row${dragIndex === i && !planChanged ? " dragging" : ""}${planChanged ? " locked" : ""}`}
                  >
                    <span className="ps-plan-edit-cell ps-plan-edit-name">{ep.title}</span>
                    <span className="ps-plan-edit-cell ps-plan-edit-desc">{ep.objective}</span>
                    {!planChanged && (
                      <button
                        className="ps-plan-edit-grip"
                        type="button"
                        aria-label="拖拽排序"
                        draggable
                        onDragStart={(e) => handlePhaseDragStart(e, i)}
                        onDragOver={(e) => handlePhaseDragOver(e, i)}
                        onDragEnd={handlePhaseDragEnd}
                      >
                        <GripVertical size={14} />
                      </button>
                    )}
                  </div>
                ))}

                {/* + 添加阶段（确认后隐藏） */}
                {!planChanged && (
                  <div className="ps-plan-edit-add-area">
                    <button
                      className="ps-plan-edit-add-btn"
                      type="button"
                      onClick={() => setShowAddPhase((v) => !v)}
                      title="添加阶段"
                    >
                      <Plus size={16} />
                    </button>

                    {showAddPhase && (
                      <div className="ps-plan-edit-add-popup">
                        {(() => {
                          const selectedIds = new Set(editPhases.map((ep) => ep.id));
                          const available = MOCK_PHASE_POOL.filter((pp) => !selectedIds.has(pp.id));
                          if (available.length === 0) {
                            return <div className="ps-plan-edit-add-empty">没有更多可选阶段</div>;
                          }
                          return available.map((pp) => (
                            <button
                              key={pp.id}
                              className="ps-plan-edit-add-item"
                              type="button"
                              onClick={() => handleAddPhase(pp)}
                            >
                              <div className="ps-plan-edit-add-item-title">{pp.title}</div>
                              <div className="ps-plan-edit-add-item-desc">{pp.objective}</div>
                            </button>
                          ));
                        })()}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <>
                {plan.phases[trackPhaseIndex] ? (
                  <>
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

                <PlanOverviewCanvas
                  units={plan.phases[trackPhaseIndex].units}
                  selectedUnitId={overviewSelectedUnitId}
                  onSelectUnit={(id) => {
                    setOverviewSelectedUnitId(id);
                    setOverviewSelectedTaskId(null);
                  }}
                />

                <div className="ps-adjust-plan-detail">
                  {(() => {
                    const tp = plan.phases[trackPhaseIndex];
                    const selUnit = overviewSelectedUnitId
                      ? tp.units.find((u) => u.id === overviewSelectedUnitId) ?? null
                      : null;

                    if (selUnit) {
                      const selectedTask = overviewSelectedTaskId
                        ? selUnit.tasks.find((t) => t.id === overviewSelectedTaskId) ?? null
                        : null;

                      if (selectedTask) {
                        const taskIdx = selUnit.tasks.findIndex((t) => t.id === selectedTask.id);
                        return (
                          <>
                            <div className="ps-adjust-plan-detail-head">
                              <span className="ps-adjust-plan-detail-badge">任务</span>
                              <span className="ps-adjust-plan-detail-title">
                                {getTaskDetailTitle(selectedTask, taskIdx)}
                              </span>
                            </div>
                            <div className="ps-detail-section">
                              <div className="ps-detail-section-head">基础信息</div>
                              <dl className="ps-detail-basics">
                                <div className="ps-detail-basic-row">
                                  <dt>任务类型</dt>
                                  <dd>{getTaskTypeDetailLabel(selectedTask.task_type)}</dd>
                                </div>
                                <div className="ps-detail-basic-row">
                                  <dt>交付方式</dt>
                                  <dd>{getTaskDeliveryLabel(selectedTask.task_type, selectedTask.delivery_mode)}</dd>
                                </div>
                                <div className="ps-detail-basic-row">
                                  <dt>预估时长</dt>
                                  <dd>{formatMinutes(selectedTask.estimated_minutes)}</dd>
                                </div>
                              </dl>
                            </div>
                            <div className="ps-detail-section">
                              <div className="ps-detail-section-head">概述</div>
                              <p className="ps-detail-summary">
                                {buildTaskDetailSummary(
                                  selectedTask,
                                  selUnit.title || `第 ${selUnit.position + 1} 章`,
                                  taskIdx,
                                  selectedTask.estimated_minutes,
                                )}
                              </p>
                            </div>
                            <button
                              className="ps-task-card-back"
                              type="button"
                              onClick={() => setOverviewSelectedTaskId(null)}
                            >
                              返回章节任务列表
                            </button>
                          </>
                        );
                      }

                      const taskCount = selUnit.tasks.length;
                      const allMaterials: { id: string; title: string }[] = [];
                      for (const t of selUnit.tasks) {
                        if (t.materials) allMaterials.push(...t.materials);
                      }
                      const summary = summarizeUnitTasks(selUnit.tasks, selUnit.estimated_minutes);

                      return (
                        <>
                          <div className="ps-adjust-plan-detail-head">
                            <span className="ps-adjust-plan-detail-badge">第 {selUnit.position + 1} 章</span>
                            <span className="ps-adjust-plan-detail-title">{selUnit.title || `第 ${selUnit.position + 1} 章`}</span>
                          </div>
                          <div className="ps-detail-section">
                            <div className="ps-detail-section-head">基础信息</div>
                            <dl className="ps-detail-basics">
                              <div className="ps-detail-basic-row"><dt>章节序号</dt><dd>第 {selUnit.position + 1} 章</dd></div>
                              <div className="ps-detail-basic-row"><dt>任务数</dt><dd>{taskCount} 个</dd></div>
                              <div className="ps-detail-basic-row"><dt>目标深度</dt><dd>{DEPTH_LABEL[selUnit.target_depth] ?? selUnit.target_depth}</dd></div>
                              <div className="ps-detail-basic-row"><dt>预估时长</dt><dd>{formatMinutes(selUnit.estimated_minutes)}</dd></div>
                            </dl>
                          </div>
                          <div className="ps-detail-section">
                            <div className="ps-detail-section-head">概述</div>
                            <p className="ps-detail-summary">{summary}</p>
                          </div>
                          <div className="ps-detail-section">
                            <div className="ps-detail-section-head">学习任务</div>
                            <div className="ps-task-type-card-list">
                              {selUnit.tasks.map((task, taskIdx) => (
                                <button
                                  className="ps-task-type-card"
                                  key={task.id}
                                  type="button"
                                  onClick={() => setOverviewSelectedTaskId(task.id)}
                                >
                                  {getTaskCardLabelForUnit(selUnit.tasks, task, taskIdx)}
                                </button>
                              ))}
                            </div>
                          </div>
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

                    const taskCount = tp.units.reduce((s, u) => s + u.tasks.length, 0);
                    return (
                      <>
                        <div className="ps-adjust-plan-detail-head">
                          <span className="ps-adjust-plan-detail-badge">第 {tp.position + 1} 阶段</span>
                          <span className="ps-adjust-plan-detail-title">{tp.title}</span>
                        </div>
                        <div className="ps-detail-section">
                          <div className="ps-detail-section-head">基础信息</div>
                          <dl className="ps-detail-basics">
                            <div className="ps-detail-basic-row"><dt>阶段序号</dt><dd>第 {tp.position + 1} 阶段</dd></div>
                            <div className="ps-detail-basic-row"><dt>章节数</dt><dd>{tp.units.length} 章</dd></div>
                            <div className="ps-detail-basic-row"><dt>任务数</dt><dd>{taskCount} 个</dd></div>
                            <div className="ps-detail-basic-row"><dt>预估时长</dt><dd>{formatMinutes(tp.estimated_minutes)}</dd></div>
                          </dl>
                        </div>
                        <div className="ps-detail-section">
                          <div className="ps-detail-section-head">概述</div>
                          <p className="ps-detail-summary">{tp.objective}</p>
                        </div>
                      </>
                    );
                  })()}
                </div>
                  </>
                ) : (
                  <div className="ps-detail">
                    <p className="ps-detail-empty">学习计划暂时不可用</p>
                  </div>
                )}
              </>
            )}
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
          {phase ? (
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
                onRequestComplete={handleRequestComplete}
                onCancelConfirm={handleCancelConfirm}
                onConfirmComplete={handleConfirmComplete}
                completingTaskId={completingTaskId}
                completionError={completionError}
                courseId={courseId}
              />
            </div>
          ) : (
            <div className="ps-layout">
              <div className="ps-detail">
                <p className="ps-detail-empty">当前课程还没有可展示的学习计划</p>
              </div>
            </div>
          )}

          {/* 底部按钮 */}
          <div className="ps-layout-actions">
            <button className="ps-btn ps-btn-secondary" type="button" disabled={!sessionId} onClick={handleOpenRealAdjustment}>
              调整方案
            </button>
          </div>
        </>
      )}
    </div>
  );
}
