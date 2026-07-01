import { Check, GripVertical, Pencil, Plus, Undo2, X } from "lucide-react";
import { useCallback, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { SetupShell } from "../components/AppShell";
import { addMockCourse } from "../data/mockCourses";
import type { CourseSessionListItem } from "../services/courseApi";

/* ── Mock 数据（从 PhaseSummary 复制）── */

const MOCK_PLAN = {
  plan_id: "mock-plan",
  revision_id: "mock-rev-1",
  status: "active",
  feasibility_status: "feasible",
  profile_revision_id: "mock-profile-1",
  phases: [
    {
      id: "p1", position: 0, title: "基础知识",
      objective: "按教材章节系统学习，掌握核心知识点", estimated_minutes: 480,
      units: [
        { id: "p1-u1", title: "第一章 计算机系统概述", position: 0, topic_id: null, target_depth: "understand", estimated_minutes: 80, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p1-u1-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "计算机系统层次结构", materials: [{ id: "m-1-1", title: "计算机系统概述讲义.pdf" }] },
          { id: "p1-u1-t2", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "计算机性能指标", materials: [] },
          { id: "p1-u1-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 20, required: true, materials: [{ id: "m-1-2", title: "系统概述练习.pdf" }] },
        ] },
        { id: "p1-u2", title: "第二章 数据的表示和运算", position: 1, topic_id: null, target_depth: "understand", estimated_minutes: 100, prerequisite_unit_ids: ["p1-u1"], priority: 1, tasks: [
          { id: "p1-u2-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "定点数的表示与运算", materials: [{ id: "m-2-1", title: "数据表示讲义.pdf" }] },
          { id: "p1-u2-t2", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "浮点数的表示与运算", materials: [] },
          { id: "p1-u2-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 40, required: true, materials: [{ id: "m-2-2", title: "数据运算练习.pdf" }] },
        ] },
        { id: "p1-u3", title: "第三章 存储系统", position: 2, topic_id: null, target_depth: "understand", estimated_minutes: 100, prerequisite_unit_ids: ["p1-u2"], priority: 1, tasks: [
          { id: "p1-u3-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "主存储器与Cache", materials: [{ id: "m-3-1", title: "存储系统讲义.pdf" }] },
          { id: "p1-u3-t2", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "虚拟存储器", materials: [] },
          { id: "p1-u3-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 40, required: true, materials: [{ id: "m-3-2", title: "存储系统练习.pdf" }] },
        ] },
        { id: "p1-u4", title: "第四章 指令系统", position: 3, topic_id: null, target_depth: "understand", estimated_minutes: 80, prerequisite_unit_ids: ["p1-u3"], priority: 1, tasks: [
          { id: "p1-u4-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "指令格式与寻址方式", materials: [{ id: "m-4-1", title: "指令系统讲义.pdf" }] },
          { id: "p1-u4-t2", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "CISC与RISC", materials: [] },
          { id: "p1-u4-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 20, required: true, materials: [{ id: "m-4-2", title: "指令系统练习.pdf" }] },
        ] },
        { id: "p1-u5", title: "第五章 中央处理器", position: 4, topic_id: null, target_depth: "understand", estimated_minutes: 100, prerequisite_unit_ids: ["p1-u4"], priority: 1, tasks: [
          { id: "p1-u5-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "CPU数据通路", materials: [{ id: "m-5-1", title: "CPU讲义.pdf" }] },
          { id: "p1-u5-t2", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "指令流水线", materials: [] },
          { id: "p1-u5-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 40, required: true, materials: [{ id: "m-5-2", title: "CPU练习.pdf" }] },
        ] },
        { id: "p1-u6", title: "第六章 总线", position: 5, topic_id: null, target_depth: "understand", estimated_minutes: 60, prerequisite_unit_ids: ["p1-u5"], priority: 1, tasks: [
          { id: "p1-u6-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 20, required: true, knowledge_point: "总线标准与仲裁", materials: [{ id: "m-6-1", title: "总线讲义.pdf" }] },
          { id: "p1-u6-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 40, required: true, materials: [{ id: "m-6-2", title: "总线练习.pdf" }] },
        ] },
        { id: "p1-u7", title: "第七章 输入输出系统", position: 6, topic_id: null, target_depth: "understand", estimated_minutes: 80, prerequisite_unit_ids: ["p1-u6"], priority: 1, tasks: [
          { id: "p1-u7-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "I/O接口与方式", materials: [{ id: "m-7-1", title: "I/O系统讲义.pdf" }] },
          { id: "p1-u7-t2", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 30, required: true, knowledge_point: "中断与DMA", materials: [] },
          { id: "p1-u7-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 20, required: true, materials: [{ id: "m-7-2", title: "I/O系统练习.pdf" }] },
        ] },
      ],
    },
    {
      id: "p2", position: 1, title: "重点突破",
      objective: "按重要知识块深入，构建完整知识体系", estimated_minutes: 360,
      units: [
        { id: "p2-u1", title: "数据表示与运算体系", position: 0, topic_id: null, target_depth: "apply", estimated_minutes: 180, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p2-u1-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 60, required: true, knowledge_point: "原码补码移码综合", materials: [{ id: "m-8-1", title: "数据表示重点讲义.pdf" }] },
          { id: "p2-u1-t2", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 60, required: true, knowledge_point: "ALU运算与溢出判断", materials: [] },
          { id: "p2-u1-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-8-2", title: "数据表示综合练习.pdf" }] },
        ] },
        { id: "p2-u2", title: "存储与CPU体系", position: 1, topic_id: null, target_depth: "apply", estimated_minutes: 180, prerequisite_unit_ids: ["p2-u1"], priority: 1, tasks: [
          { id: "p2-u2-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 60, required: true, knowledge_point: "Cache映射与替换策略", materials: [{ id: "m-9-1", title: "存储重点讲义.pdf" }] },
          { id: "p2-u2-t2", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 60, required: true, knowledge_point: "指令流水线冒险与冲突", materials: [] },
          { id: "p2-u2-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-9-2", title: "存储CPU综合练习.pdf" }] },
        ] },
      ],
    },
    {
      id: "p3", position: 2, title: "专项训练",
      objective: "按题型分类训练，提升解题熟练度", estimated_minutes: 360,
      units: [
        { id: "p3-u1", title: "选择题专项", position: 0, topic_id: null, target_depth: "apply", estimated_minutes: 120, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p3-u1-t1", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-10-1", title: "选择题基础练习.pdf" }] },
          { id: "p3-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-10-2", title: "选择题进阶练习.pdf" }] },
        ] },
        { id: "p3-u2", title: "计算题专项", position: 1, topic_id: null, target_depth: "apply", estimated_minutes: 120, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p3-u2-t1", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-10-3", title: "计算题基础练习.pdf" }] },
          { id: "p3-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-10-4", title: "计算题进阶练习.pdf" }] },
        ] },
        { id: "p3-u3", title: "分析题专项", position: 2, topic_id: null, target_depth: "apply", estimated_minutes: 120, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p3-u3-t1", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-10-5", title: "分析题基础练习.pdf" }] },
          { id: "p3-u3-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-10-6", title: "分析题进阶练习.pdf" }] },
        ] },
      ],
    },
    {
      id: "p4", position: 3, title: "综合应用",
      objective: "专门练习综合大题，先讲解思路再实战", estimated_minutes: 360,
      units: [
        { id: "p4-u1", title: "存储系统综合大题", position: 0, topic_id: null, target_depth: "analyze", estimated_minutes: 180, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p4-u1-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 60, required: true, knowledge_point: "Cache+主存综合题解题思路", materials: [{ id: "m-11-1", title: "存储综合大题讲义.pdf" }] },
          { id: "p4-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-11-2", title: "存储综合大题练习.pdf" }] },
          { id: "p4-u1-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [] },
        ] },
        { id: "p4-u2", title: "CPU综合大题", position: 1, topic_id: null, target_depth: "analyze", estimated_minutes: 180, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p4-u2-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 60, required: true, knowledge_point: "流水线+数据通路综合题解题思路", materials: [{ id: "m-11-3", title: "CPU综合大题讲义.pdf" }] },
          { id: "p4-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-11-4", title: "CPU综合大题练习.pdf" }] },
          { id: "p4-u2-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [] },
        ] },
      ],
    },
    {
      id: "p5", position: 4, title: "真题练习",
      objective: "按真题套题完整模拟，分题型逐一练习", estimated_minutes: 360,
      units: [
        { id: "p5-u1", title: "2024年真题", position: 0, topic_id: null, target_depth: "analyze", estimated_minutes: 180, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p5-u1-t1", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-12-1", title: "选择题部分.pdf" }] },
          { id: "p5-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-12-2", title: "计算题部分.pdf" }] },
          { id: "p5-u1-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-12-3", title: "分析题部分.pdf" }] },
          { id: "p5-u1-t4", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-12-4", title: "综合题部分.pdf" }] },
        ] },
        { id: "p5-u2", title: "2023年真题", position: 1, topic_id: null, target_depth: "analyze", estimated_minutes: 180, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p5-u2-t1", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-12-5", title: "选择题部分.pdf" }] },
          { id: "p5-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-12-6", title: "计算题部分.pdf" }] },
          { id: "p5-u2-t3", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-12-7", title: "分析题部分.pdf" }] },
          { id: "p5-u2-t4", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-12-8", title: "综合题部分.pdf" }] },
        ] },
      ],
    },

  ],
};

/* 阶段池（编辑模式下可选添加） */
interface PoolPhase { id: string; title: string; objective: string; }
const MOCK_PHASE_POOL: PoolPhase[] = [
  { id: "pool-1", title: "基础知识", objective: "按教材章节系统学习，知识点与练习结合" },
  { id: "pool-2", title: "重点突破", objective: "按知识块划分，深入学习每个知识体系" },
  { id: "pool-3", title: "专项训练", objective: "按题型分类训练，基础与进阶练习结合" },
  { id: "pool-4", title: "综合应用", objective: "讲解解题思路，练习综合大题" },
  { id: "pool-5", title: "真题练习", objective: "按真题套题划分，分题型练习" },
  { id: "pool-6", title: "易错题", objective: "按考点划分，针对易错点专项训练" },
  { id: "pool-7", title: "复习巩固", objective: "按教材章节回顾重点知识点并练习" },
  { id: "pool-8", title: "错题再练", objective: "按教材章节重做错过的题目" },
];

/* mock 学习档案 */
interface ProfileItem { key: string; title: string; value: string; }
const MOCK_PROFILE: ProfileItem[] = [
  { key: "goal", title: "学习目标", value: "计算机组成原理系统复习，备战期末" },
  { key: "level", title: "当前基础", value: "中等，存储系统部分薄弱" },
  { key: "pace", title: "推进方式", value: "按知识板块逐步推进" },
  { key: "timeBudget", title: "每日时长", value: "2~3 小时" },
  { key: "deadline", title: "目标日期", value: "2026-08-15" },
  { key: "school", title: "学校/地区", value: "华南理工大学" },
];

/* ── 常量 / 辅助函数 ── */

const TASK_TYPE_LABEL: Record<string, string> = { lecture: "讲解", exercise: "练习", project: "项目", review: "复习" };
const DEPTH_LABEL: Record<string, string> = { understand: "理解", apply: "应用", analyze: "分析", review: "复习" };

function formatMinutes(m: number): string {
  if (m >= 60) return `${Math.round(m / 60 * 10) / 10} 小时`;
  return `${m} 分钟`;
}

/* ── Phase-track 滚动辅助 ── */

function offsetOf(index: number, blockBasis: number) {
  if (index <= 0) return 0;
  return index * blockBasis - 4 * index;
}

/* ── PlanOverviewCanvas（从 PhaseSummary 复制）── */

const OV_CANVAS = { UNIT_W: 130, UNIT_H: 60, ARROW_W: 40, PAD_H: 16, PAD_V: 14 };

interface OverviewUnitNode {
  id: string; title: string; position: number;
  x: number; y: number; w: number; h: number;
}

type UnitData = typeof MOCK_PLAN.phases[0]["units"];

function computeOverviewLayout(units: UnitData) {
  const N = units.length;
  const contentW = 2 * OV_CANVAS.PAD_H + N * OV_CANVAS.UNIT_W + Math.max(0, N - 1) * OV_CANVAS.ARROW_W;
  const contentH = 2 * OV_CANVAS.PAD_V + OV_CANVAS.UNIT_H;
  const nodes: OverviewUnitNode[] = units.map((u, i) => ({
    id: u.id, title: u.title || `第 ${u.position + 1} 章`, position: u.position,
    x: OV_CANVAS.PAD_H + i * (OV_CANVAS.UNIT_W + OV_CANVAS.ARROW_W),
    y: OV_CANVAS.PAD_V, w: OV_CANVAS.UNIT_W, h: OV_CANVAS.UNIT_H,
  }));
  return { contentW, contentH, nodes };
}

function PlanOverviewCanvas({
  units, selectedUnitId, onSelectUnit,
}: {
  units: UnitData; selectedUnitId: string | null; onSelectUnit: (unitId: string | null) => void;
}) {
  const layout = useMemo(() => computeOverviewLayout(units), [units]);
  const { contentW, contentH, nodes } = layout;
  return (
    <div className="ps-adjust-plan-canvas">
      <div className="ps-adjust-plan-canvas-scroll" style={{ minWidth: contentW, minHeight: contentH }}>
        <div className="ps-adjust-plan-canvas-content" style={{ width: contentW + 1, height: contentH }}>
          <svg className="ps-adjust-plan-canvas-svg" width={contentW} height={contentH} viewBox={`0 0 ${contentW} ${contentH}`}>
            <defs>
              <marker id="ps-overview-arrow" markerWidth="10" markerHeight="10" refX="9" refY="5" orient="auto">
                <path d="M2,2 L9,5 L2,8" fill="none" stroke="var(--border-strong)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </marker>
            </defs>
            {nodes.map((n, i) => {
              if (i >= nodes.length - 1) return null;
              const next = nodes[i + 1];
              const cy = n.y + n.h / 2;
              return <line key={`oa-${n.id}`} x1={n.x + n.w} y1={cy} x2={next.x} y2={cy} stroke="var(--border-strong)" strokeWidth="1.5" markerEnd="url(#ps-overview-arrow)" />;
            })}
          </svg>
          {nodes.map((n) => (
            <button key={n.id} type="button"
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

/* ── 步骤 2：确认学习方案 ── */

export function ConfirmPlanPage() {
  const navigate = useNavigate();
  const plan = MOCK_PLAN;

  /* phase-track 状态 */
  const [trackPhaseIndex, setTrackPhaseIndex] = useState(0);
  const trackNavRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef(0);
  const N = plan.phases.length;

  const scrollTrackTo = useCallback((index: number) => {
    const el = trackNavRef.current;
    if (!el) return;
    const prev = targetRef.current;
    const down = index > prev;
    targetRef.current = index;
    setTrackPhaseIndex(index);
    const basis = el.clientWidth / 4;
    const maxStart = Math.max(0, N - 4);
    const anchor = down ? index - 2 : index - 1;
    const snapIndex = Math.max(0, Math.min(anchor, maxStart));
    el.scrollTo({ left: offsetOf(snapIndex, basis), behavior: "smooth" });
  }, [N]);

  function handleTrackClick(index: number) {
    if (index === targetRef.current) return;
    scrollTrackTo(index);
  }

  function handleTrackWheel(e: React.WheelEvent) {
    e.preventDefault();
    if (N <= 1) return;
    const dir = e.deltaY > 0 ? 1 : -1;
    const next = Math.max(0, Math.min(N - 1, targetRef.current + dir));
    if (next === targetRef.current) return;
    scrollTrackTo(next);
  }

  /* 计划概览章节选中 */
  const [overviewSelectedUnitId, setOverviewSelectedUnitId] = useState<string | null>(null);

  /* ── 档案编辑 ── */
  const [profileEditing, setProfileEditing] = useState(false);
  const [profileValues, setProfileValues] = useState<ProfileItem[]>(() =>
    MOCK_PROFILE.map((p) => ({ ...p })),
  );
  const [profileChanged, setProfileChanged] = useState(false);

  /* ── 计划编辑 ── */
  const [planEditing, setPlanEditing] = useState(false);
  const [planChanged, setPlanChanged] = useState(false);
  const [editPhases, setEditPhases] = useState(() =>
    plan.phases.map((p) => ({ id: p.id, title: p.title, objective: p.objective })),
  );
  const [showAddPhase, setShowAddPhase] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  /* ── 档案编辑 handler ── */

  const handleProfileEditToggle = useCallback(() => {
    if (profileEditing) {
      // ✓ → 标记已更改，退出编辑
      setProfileEditing(false);
      setProfileChanged(true);
    } else {
      setProfileEditing(true);
    }
  }, [profileEditing]);

  const handleProfileEditCancel = useCallback(() => {
    setProfileEditing(false);
    setProfileValues(MOCK_PROFILE.map((p) => ({ ...p })));
  }, []);

  const handleProfileUndo = useCallback(() => {
    setProfileChanged(false);
    setProfileValues(MOCK_PROFILE.map((p) => ({ ...p })));
  }, []);

  const handleProfileValueChange = useCallback((key: string, value: string) => {
    setProfileValues((prev) => prev.map((p) => (p.key === key ? { ...p, value } : p)));
  }, []);

  /* ── 计划编辑 handler ── */

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
      setEditPhases(plan.phases.map((p) => ({ id: p.id, title: p.title, objective: p.objective })));
    }
  }, [planEditing, planChanged, plan.phases]);

  const handlePlanEditCancel = useCallback(() => {
    setPlanEditing(false);
    setPlanChanged(false);
    setShowAddPhase(false);
  }, []);

  const handlePlanUndo = useCallback(() => {
    setPlanEditing(false);
    setPlanChanged(false);
    setShowAddPhase(false);
  }, []);

  /* ── 阶段编辑表格：拖拽排序 ── */

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
      { id: poolPhase.id, title: poolPhase.title, objective: poolPhase.objective },
    ]);
    setShowAddPhase(false);
  }, []);

  const handleDeletePhase = useCallback((index: number) => {
    setEditPhases((prev) => {
      if (prev.length <= 1) return prev;
      return prev.filter((_, i) => i !== index);
    });
  }, []);

  /* 是否有任何编辑变更 */
  const isDirty = profileChanged || planChanged;

  /* ── 开始学习：生成 mock 课程数据 ── */
  const handleStartLearning = useCallback(() => {
    const profileMap = Object.fromEntries(profileValues.map((p) => [p.key, p.value]));
    const now = new Date().toISOString();
    const mockId = `mock-${Date.now()}`;

    const mockCourse: CourseSessionListItem = {
      id: mockId,
      goal: profileMap.goal || "计算机组成原理系统复习",
      title: profileMap.goal?.slice(0, 12) || "计算机组成原理",
      status: "started",
      level: profileMap.level || "中等",
      pace: profileMap.pace || "按知识板块逐步推进",
      time_budget: profileMap.timeBudget || "2~3 小时",
      school: profileMap.school || "",
      deadline: profileMap.deadline || null,
      current_phase: editPhases[0]?.title || "基础入门",
      next_task: "lecture",
      created_at: now,
      updated_at: now,
      last_studied_at: now,
    };

    addMockCourse(mockCourse);
    sessionStorage.setItem("mentora-course-started", "true");
    navigate("/courses");
  }, [profileValues, editPhases, navigate]);

  return (
    <SetupShell
      current={2}
      hideInfoBar
      footer={
        <div className="setup-footer">
          <button
            className={`ps-btn ${isDirty ? "ps-btn-primary" : "ps-btn-secondary"}`}
            type="button"
            onClick={() => navigate("/courses/new?adjust=true")}
          >
            调整方案
          </button>
          <button
            className={`ps-btn ${!isDirty ? "ps-btn-primary" : "ps-btn-secondary"}`}
            type="button"
            onClick={handleStartLearning}
          >
            开始学习
          </button>
        </div>
      }
    >
      <div className="ps-adjust-body">
        {/* 标题 */}
        <div className="setup-heading compact-heading">
          <h1 className="course-title-main">确认学习方案</h1>
          <p>请确认学习档案和学习计划概览，确认后即可开始学习。</p>
        </div>

        {/* 1. 学习档案 */}
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

        {/* 2. 学习计划概览 */}
        <div className="ps-adjust-section ps-adjust-plan">
          <div className="ps-adjust-profile-header">
            <div className="ps-adjust-section-title">
              学习计划概览{planChanged && <span className="ps-adjust-dirty-star">*</span>}
            </div>
            <div className="ps-adjust-edit-actions">
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
            /* 阶段编辑表格 */
            <div className="ps-plan-edit-table">
              <div className="ps-plan-edit-head">
                <span className="ps-plan-edit-col-name">阶段</span>
                <span className="ps-plan-edit-col-desc">简介</span>
                {!planChanged && <span className="ps-plan-edit-col-grip"></span>}
              </div>
              {editPhases.map((ep, i) => (
                <div key={ep.id} className={`ps-plan-edit-row${dragIndex === i && !planChanged ? " dragging" : ""}${planChanged ? " locked" : ""}`}>
                  <span className="ps-plan-edit-cell ps-plan-edit-name">{ep.title}</span>
                  <span className="ps-plan-edit-cell ps-plan-edit-desc">{ep.objective}</span>
                  {!planChanged && (
                    <>
                      <button
                        className="ps-plan-edit-delete"
                        type="button"
                        aria-label="删除阶段"
                        disabled={editPhases.length <= 1}
                        onClick={() => handleDeletePhase(i)}
                      >
                        <X size={14} />
                      </button>
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
                    </>
                  )}
                </div>
              ))}
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
                        const selectedTitles = new Set(editPhases.map((ep) => ep.title));
                        const available = MOCK_PHASE_POOL.filter((pp) => !selectedTitles.has(pp.title));
                        if (available.length === 0) {
                          return <div className="ps-plan-edit-add-empty">没有更多可选阶段</div>;
                        }
                        return available.map((pp) => (
                          <button key={pp.id} className="ps-plan-edit-add-item" type="button" onClick={() => handleAddPhase(pp)}>
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
              {/* phase-track 横向滑轨 */}
              <div className="phase-track" ref={trackNavRef} onWheel={handleTrackWheel}>
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

              {/* 章节概览画布 */}
              <PlanOverviewCanvas
                units={plan.phases[trackPhaseIndex].units}
                selectedUnitId={overviewSelectedUnitId}
                onSelectUnit={(id) => setOverviewSelectedUnitId(id)}
              />

              {/* 阶段 / 章节详情 */}
              <div className="ps-adjust-plan-detail">
                {(() => {
                  const tp = plan.phases[trackPhaseIndex];
                  const selUnit = overviewSelectedUnitId
                    ? tp.units.find((u) => u.id === overviewSelectedUnitId) ?? null
                    : null;

                  if (selUnit) {
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

                  /* 阶段信息 */
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
          )}
        </div>
      </div>
    </SetupShell>
  );
}
