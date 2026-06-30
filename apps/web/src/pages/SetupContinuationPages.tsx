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
      id: "p1", position: 0, title: "基础入门",
      objective: "掌握集合、函数等核心概念与基本方法", estimated_minutes: 480,
      units: [
        { id: "p1-u1", title: "集合与逻辑", position: 0, topic_id: null, target_depth: "understand", estimated_minutes: 160, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p1-u1-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true, knowledge_point: "集合的概念", materials: [{ id: "m-1-1", title: "集合概念讲义.pdf" }] },
          { id: "p1-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 40, required: true, materials: [{ id: "m-1-2", title: "集合运算练习.pdf" }] },
          { id: "p1-u1-t3", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true, knowledge_point: "命题与逻辑", materials: [{ id: "m-1-3", title: "命题与逻辑讲义.pdf" }] },
          { id: "p1-u1-t4", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 40, required: true, materials: [] },
        ] },
        { id: "p1-u2", title: "函数基础", position: 1, topic_id: null, target_depth: "understand", estimated_minutes: 150, prerequisite_unit_ids: ["p1-u1"], priority: 1, tasks: [
          { id: "p1-u2-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 50, required: true, knowledge_point: "函数的定义", materials: [{ id: "m-2-1", title: "函数定义讲义.pdf" }] },
          { id: "p1-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 50, required: true, materials: [{ id: "m-2-2", title: "定义域值域练习.pdf" }] },
          { id: "p1-u2-t3", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 50, required: true, knowledge_point: "函数的表示方法", materials: [] },
        ] },
        { id: "p1-u3", title: "基本初等函数", position: 2, topic_id: null, target_depth: "understand", estimated_minutes: 170, prerequisite_unit_ids: ["p1-u2"], priority: 1, tasks: [
          { id: "p1-u3-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true, knowledge_point: "正比例函数", materials: [{ id: "m-3-1", title: "正比例函数讲义.pdf" }] },
          { id: "p1-u3-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-3-2", title: "反比例函数练习.pdf" }] },
          { id: "p1-u3-t3", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 40, required: true, knowledge_point: "一次函数", materials: [{ id: "m-3-3", title: "一次函数讲义.pdf" }] },
          { id: "p1-u3-t4", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 45, required: true, materials: [{ id: "m-3-4", title: "二次函数复习题.pdf" }] },
        ] },
      ],
    },
    {
      id: "p2", position: 1, title: "知识梳理",
      objective: "系统学习教材，按章节深入梳理知识体系", estimated_minutes: 600,
      units: [
        { id: "p2-u1", title: "数列与极限", position: 0, topic_id: null, target_depth: "apply", estimated_minutes: 300, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p2-u1-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 60, required: true, knowledge_point: "数列的概念", materials: [{ id: "m-4-1", title: "数列概念讲义.pdf" }] },
          { id: "p2-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-4-2", title: "数列求和练习.pdf" }] },
          { id: "p2-u1-t3", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 60, required: true, knowledge_point: "极限的探究", materials: [{ id: "m-4-3", title: "极限探究项目.pdf" }] },
        ] },
        { id: "p2-u2", title: "三角函数", position: 1, topic_id: null, target_depth: "apply", estimated_minutes: 300, prerequisite_unit_ids: ["p2-u1"], priority: 1, tasks: [
          { id: "p2-u2-t1", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 60, required: true, knowledge_point: "三角函数定义", materials: [{ id: "m-5-1", title: "三角函数讲义.pdf" }] },
          { id: "p2-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-5-2", title: "三角恒等变换练习.pdf" }] },
        ] },
      ],
    },
    {
      id: "p3", position: 2, title: "专项训练",
      objective: "突破薄弱点，题型分类训练", estimated_minutes: 540,
      units: [
        { id: "p3-u1", title: "函数题型专项", position: 0, topic_id: null, target_depth: "apply", estimated_minutes: 270, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p3-u1-t1", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [{ id: "m-6-1", title: "函数题型专项训练.pdf" }] },
          { id: "p3-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [] },
          { id: "p3-u1-t3", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [{ id: "m-6-2", title: "函数易错题回顾.pdf" }] },
        ] },
        { id: "p3-u2", title: "几何题型专项", position: 1, topic_id: null, target_depth: "apply", estimated_minutes: 270, prerequisite_unit_ids: ["p3-u1"], priority: 1, tasks: [
          { id: "p3-u2-t1", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [{ id: "m-7-1", title: "几何题型专项训练.pdf" }] },
          { id: "p3-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [] },
          { id: "p3-u2-t3", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 90, required: true, knowledge_point: "立体几何综合", materials: [{ id: "m-7-2", title: "立体几何综合项目.pdf" }] },
        ] },
      ],
    },
    {
      id: "p4", position: 3, title: "综合应用",
      objective: "跨知识点实战，真题与综合项目", estimated_minutes: 480,
      units: [
        { id: "p4-u1", title: "综合真题训练", position: 0, topic_id: null, target_depth: "analyze", estimated_minutes: 240, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p4-u1-t1", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 120, required: true, knowledge_point: "高考真题实战", materials: [{ id: "m-8-1", title: "2025高考真题集.pdf" }] },
          { id: "p4-u1-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 120, required: true, materials: [{ id: "m-8-2", title: "真题分类训练.pdf" }] },
        ] },
        { id: "p4-u2", title: "跨章节综合", position: 1, topic_id: null, target_depth: "analyze", estimated_minutes: 240, prerequisite_unit_ids: ["p4-u1"], priority: 1, tasks: [
          { id: "p4-u2-t1", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 80, required: true, knowledge_point: "跨章节综合", materials: [{ id: "m-9-1", title: "跨章节综合项目.pdf" }] },
          { id: "p4-u2-t2", task_type: "exercise", delivery_mode: "self_paced", estimated_minutes: 80, required: true, materials: [] },
          { id: "p4-u2-t3", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 80, required: true, materials: [{ id: "m-9-2", title: "综合题解题思路.pdf" }] },
        ] },
      ],
    },
    {
      id: "p5", position: 4, title: "考前冲刺",
      objective: "考点回顾，临场策略与限时模拟", estimated_minutes: 360,
      units: [
        { id: "p5-u1", title: "考点回顾", position: 0, topic_id: null, target_depth: "analyze", estimated_minutes: 180, prerequisite_unit_ids: [], priority: 1, tasks: [
          { id: "p5-u1-t1", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 90, required: true, materials: [{ id: "m-10-1", title: "考点全回顾.pdf" }] },
          { id: "p5-u1-t2", task_type: "lecture", delivery_mode: "self_paced", estimated_minutes: 90, required: true, knowledge_point: "临场策略", materials: [{ id: "m-10-2", title: "临场策略讲义.pdf" }] },
        ] },
        { id: "p5-u2", title: "限时模拟", position: 1, topic_id: null, target_depth: "analyze", estimated_minutes: 180, prerequisite_unit_ids: ["p5-u1"], priority: 1, tasks: [
          { id: "p5-u2-t1", task_type: "project", delivery_mode: "self_paced", estimated_minutes: 120, required: true, knowledge_point: "限时模拟", materials: [{ id: "m-11-1", title: "限时模拟卷A.pdf" }, { id: "m-11-2", title: "限时模拟卷B.pdf" }] },
          { id: "p5-u2-t2", task_type: "review", delivery_mode: "self_paced", estimated_minutes: 60, required: true, materials: [{ id: "m-11-3", title: "模拟卷讲评.pdf" }] },
        ] },
      ],
    },
  ],
};

/* 阶段池（编辑模式下可选添加） */
interface PoolPhase { id: string; title: string; objective: string; }
const MOCK_PHASE_POOL: PoolPhase[] = [
  { id: "pool-k1", title: "知识衔接", objective: "补齐前置知识缺口" },
  { id: "pool-k2", title: "习题强化", objective: "大量针对性练习，巩固薄弱环节" },
  { id: "pool-k3", title: "阶段测评", objective: "定期检测学习效果，调整方向" },
  { id: "pool-k4", title: "拓展阅读", objective: "拓展学科视野，了解实际应用" },
  { id: "pool-k5", title: "思维训练", objective: "培养逻辑思维与解题策略" },
  { id: "pool-k6", title: "实战模拟", objective: "全真模拟考试，训练应试能力" },
];

/* mock 学习档案 */
interface ProfileItem { key: string; title: string; value: string; }
const MOCK_PROFILE: ProfileItem[] = [
  { key: "goal", title: "学习目标", value: "高中数学系统复习，备战高考" },
  { key: "level", title: "当前基础", value: "中等偏上，函数部分薄弱" },
  { key: "pace", title: "推进方式", value: "按知识板块逐步推进" },
  { key: "timeBudget", title: "每日时长", value: "2~3 小时" },
  { key: "deadline", title: "目标日期", value: "2026-08-15" },
  { key: "school", title: "学校/地区", value: "华南师大附中" },
];

/* ── 常量 / 辅助函数 ── */

const TASK_TYPE_LABEL: Record<string, string> = { lecture: "讲解", exercise: "练习", project: "项目", review: "复习" };
const DEPTH_LABEL: Record<string, string> = { understand: "理解", apply: "应用", analyze: "分析" };

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

  /* 是否有任何编辑变更 */
  const isDirty = profileChanged || planChanged;

  /* ── 开始学习：生成 mock 课程数据 ── */
  const handleStartLearning = useCallback(() => {
    const profileMap = Object.fromEntries(profileValues.map((p) => [p.key, p.value]));
    const now = new Date().toISOString();
    const mockId = `mock-${Date.now()}`;

    const mockCourse: CourseSessionListItem = {
      id: mockId,
      goal: profileMap.goal || "高中数学系统复习",
      title: profileMap.goal?.slice(0, 12) || "高中数学系统复习",
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
