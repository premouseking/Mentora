import { Check, GripVertical, Pencil, Plus, Undo2, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import { SetupShell } from "../components/AppShell";
import { ProfileQaList, type QaDisplayItem } from "../components/ProfileQaDisplay";
import {
  ApiError,
  generatePlan,
  getActivePlan,
  getCourseSession,
  startCourse,
  updateCourseSession,
  type ActivePlan,
  type CoverageGap,
  type SessionDetail,
} from "../services/courseApi";
import {
  buildAdjustmentSupplement,
  buildTaskDetailSummary,
  describePlanPhaseChanges,
  getTaskCardLabelForUnit,
  getTaskDeliveryLabel,
  getTaskDetailTitle,
  getTaskTypeDetailLabel,
  profileItemsToSessionUpdate,
  summarizeUnitTasks,
} from "./courseFlowHelpers";

/* ── 类型 ── */

interface PoolPhase { id: string; title: string; objective: string; }

/* 阶段池（编辑模式下可选添加） */
const PHASE_POOL_TEMPLATES: PoolPhase[] = [
  { id: "pool-k1", title: "知识衔接", objective: "补齐前置知识缺口" },
  { id: "pool-k2", title: "习题强化", objective: "大量针对性练习，巩固薄弱环节" },
  { id: "pool-k3", title: "阶段测评", objective: "定期检测学习效果，调整方向" },
  { id: "pool-k4", title: "拓展阅读", objective: "拓展学科视野，了解实际应用" },
  { id: "pool-k5", title: "思维训练", objective: "培养逻辑思维与解题策略" },
  { id: "pool-k6", title: "实战模拟", objective: "全真模拟考试，训练应试能力" },
];

interface ProfileItem extends QaDisplayItem {}

const PROFILE_FIELD_LABELS: Record<string, string> = {
  goal: "你想学习什么？",
  level: "你目前的基础如何？",
  pace: "你希望的推进方式？",
  timeBudget: "每天可投入多少时间？",
  deadline: "你的目标日期是？",
  school: "你就读/所在学校或地区？",
};

/* 从 SessionDetail 构建档案项（Q&A 结构） */
function buildProfileItems(session: SessionDetail): ProfileItem[] {
  const fields: Array<{ key: keyof typeof PROFILE_FIELD_LABELS; value: string }> = [
    { key: "goal", value: session.goal || "" },
    { key: "level", value: session.level || "" },
    { key: "pace", value: session.pace || "" },
    { key: "timeBudget", value: session.time_budget || "" },
    { key: "deadline", value: session.deadline || "" },
    { key: "school", value: session.school || "" },
  ];

  const items: ProfileItem[] = fields.map((f) => ({
    key: f.key,
    title: PROFILE_FIELD_LABELS[f.key],
    value: f.value,
    source: "你的输入",
    editable: true,
  }));

  session.inquiry_history?.forEach((entry, i) => {
    if (entry.question.trim() && entry.answer.trim()) {
      items.push({
        key: `inquiry_${i}`,
        title: entry.question,
        value: entry.answer,
        source: "你的回答",
        editable: true,
      });
    }
  });

  return items;
}

/* ── 常量 ── */

const DEPTH_LABEL: Record<string, string> = {
  basic: "基础",
  reinforce: "强化",
  review: "复习",
  skip: "跳过",
  understand: "理解",
  apply: "应用",
  analyze: "分析",
};

function formatMinutes(m: number): string {
  if (m >= 60) return `${Math.round(m / 60 * 10) / 10} 小时`;
  return `${m} 分钟`;
}

/* ── Phase-track 滚动辅助 ── */

function offsetOf(index: number, blockBasis: number) {
  if (index <= 0) return 0;
  return index * blockBasis - 4 * index;
}

/* ── PlanOverviewCanvas ── */

const OV_CANVAS = { UNIT_W: 130, UNIT_H: 60, ARROW_W: 40, PAD_H: 16, PAD_V: 14 };

interface OverviewUnitNode {
  id: string; title: string; position: number;
  x: number; y: number; w: number; h: number;
}

function computeOverviewLayout(units: ActivePlan["phases"][0]["units"]) {
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
  units: ActivePlan["phases"][0]["units"]; selectedUnitId: string | null; onSelectUnit: (unitId: string | null) => void;
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
              if (!next) return null;
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
  const sid = sessionStorage.getItem("mentora-session-id");

  /* 加载状态 */
  const [plan, setPlan] = useState<ActivePlan | null>(null);
  const [sessionDetail, setSessionDetail] = useState<SessionDetail | null>(null);
  const [profileItems, setProfileItems] = useState<ProfileItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [awaitingTrialGenerate, setAwaitingTrialGenerate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [scopePrompt, setScopePrompt] = useState<{ message: string; gaps: CoverageGap[] } | null>(null);
  const [planCoverageGaps, setPlanCoverageGaps] = useState<CoverageGap[]>([]);

  async function runPlanGeneration(allowPartial = false) {
    if (!sid) return false;
    setGenerating(true);
    setAwaitingTrialGenerate(false);
    setError(null);
    try {
      const generated = await generatePlan(sid, { allow_partial_plan: allowPartial });
      const planData = await getActivePlan(sid);
      setPlan(planData);
      setPlanCoverageGaps(generated.coverage_gaps ?? []);
      setScopePrompt(null);
      return true;
    } catch (genErr) {
      if (
        genErr instanceof ApiError
        && genErr.status === 409
        && genErr.code === "insufficient_scope"
      ) {
        setScopePrompt({
          message: genErr.message,
          gaps: genErr.coverageGaps ?? [],
        });
        return false;
      }
      setError(genErr instanceof Error ? genErr.message : "方案生成失败");
      return false;
    } finally {
      setGenerating(false);
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!sid) {
      navigate("/courses/new");
      return;
    }

    let cancelled = false;
    const safeSid = sid!;

    async function loadPlan() {
      try {
        const sessionData = await getCourseSession(safeSid);
        if (cancelled) return;
        setSessionDetail(sessionData);
        setProfileItems(buildProfileItems(sessionData));
      } catch {
        // 会话信息失败不阻塞
      }

      try {
        const planData = await getActivePlan(safeSid);
        if (cancelled) return;
        setPlan(planData);
        setAwaitingTrialGenerate(false);
        if (!cancelled) setLoading(false);
      } catch {
        if (cancelled) return;
        setAwaitingTrialGenerate(true);
        setLoading(false);
      }
    }

    loadPlan();

    return () => { cancelled = true; };
  }, [sid, navigate]);

  /* phase-track 状态 */
  const [trackPhaseIndex, setTrackPhaseIndex] = useState(0);
  const trackNavRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef(0);

  const phases = plan?.phases ?? [];
  const N = phases.length;

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

  /* 计划概览章节 / 任务选中 */
  const [overviewSelectedUnitId, setOverviewSelectedUnitId] = useState<string | null>(null);
  const [overviewSelectedTaskId, setOverviewSelectedTaskId] = useState<string | null>(null);

  /* ── 档案编辑 ── */
  const [profileEditing, setProfileEditing] = useState(false);
  const [profileValues, setProfileValues] = useState<ProfileItem[]>([]);
  const [profileChanged, setProfileChanged] = useState(false);

  // profileItems 变化时同步本地编辑态
  useEffect(() => {
    setProfileValues(profileItems.map((p) => ({ ...p })));
  }, [profileItems]);

  /* ── 计划编辑 ── */
  const [planEditing, setPlanEditing] = useState(false);
  const [planChanged, setPlanChanged] = useState(false);
  const [editPhases, setEditPhases] = useState<{ id: string; title: string; objective: string }[]>([]);
  const [showAddPhase, setShowAddPhase] = useState(false);
  const [dragIndex, setDragIndex] = useState<number | null>(null);

  // plan 变化时同步编辑态
  useEffect(() => {
    if (plan) {
      setEditPhases(plan.phases.map((p) => ({ id: p.id, title: p.title, objective: p.objective })));
    }
  }, [plan]);

  /* ── 档案编辑 handler ── */

  const handleProfileEditToggle = useCallback(() => {
    if (profileEditing) {
      setProfileEditing(false);
      setProfileChanged(true);
    } else {
      setProfileEditing(true);
    }
  }, [profileEditing]);

  const handleProfileEditCancel = useCallback(() => {
    setProfileEditing(false);
    setProfileValues(profileItems.map((p) => ({ ...p })));
  }, [profileItems]);

  const handleProfileUndo = useCallback(() => {
    setProfileChanged(false);
    setProfileValues(profileItems.map((p) => ({ ...p })));
  }, [profileItems]);

  const handleProfileValueChange = useCallback((key: string, value: string) => {
    setProfileValues((prev) => prev.map((p) => (p.key === key ? { ...p, value } : p)));
  }, []);

  /* ── 计划编辑 handler ── */

  const handlePlanEditToggle = useCallback(() => {
    if (planEditing) {
      if (planChanged) {
        setPlanChanged(false);
      } else {
        setPlanChanged(true);
      }
    } else {
      setPlanEditing(true);
      if (plan) setEditPhases(plan.phases.map((p) => ({ id: p.id, title: p.title, objective: p.objective })));
    }
  }, [planEditing, planChanged, plan]);

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

  /* ── 拖拽排序 ── */

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

  const isDirty = profileChanged || planChanged;
  const [adjusting, setAdjusting] = useState(false);

  const handleAdjustPlan = useCallback(async () => {
    if (!sid) return;
    if (!isDirty) {
      navigate("/courses/new?adjust=true");
      return;
    }

    setAdjusting(true);
    setError(null);
    try {
      const originalPhases = plan?.phases.map((p) => ({ id: p.id, title: p.title, objective: p.objective })) ?? [];
      const planSummary = planChanged ? describePlanPhaseChanges(originalPhases, editPhases) : "";
      const supplement = buildAdjustmentSupplement("", planSummary);
      await updateCourseSession(sid, {
        ...(profileChanged ? profileItemsToSessionUpdate(profileValues) : {}),
        ...(Object.keys(supplement).length > 0
          ? { profile_supplement: { ...(sessionDetail?.profile_supplement ?? {}), ...supplement } }
          : {}),
      });

      await generatePlan(sid);
      const [sessionData, planData] = await Promise.all([
        getCourseSession(sid),
        getActivePlan(sid),
      ]);
      setSessionDetail(sessionData);
      setProfileItems(buildProfileItems(sessionData));
      setPlan(planData);
      setProfileChanged(false);
      setPlanEditing(false);
      setPlanChanged(false);
      setShowAddPhase(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "调整方案失败");
    } finally {
      setAdjusting(false);
    }
  }, [
    editPhases,
    isDirty,
    navigate,
    plan,
    planChanged,
    profileChanged,
    profileValues,
    sessionDetail,
    sid,
  ]);

  /* ── 开始学习：调用后端激活课程 ── */
  const [starting, setStarting] = useState(false);

  const handleStartLearning = useCallback(async () => {
    if (!sid) return;
    setStarting(true);
    try {
      const result = await startCourse(sid);
      sessionStorage.setItem("mentora-course-started", "true");
      // 优先用后端返回的 course_id（路径 A 统一后的 Course ID）
      const courseId = result.course_id || sid;
      navigate(`/courses/${courseId}`);
    } catch (err) {
      setStarting(false);
      setError(err instanceof Error ? err.message : "启动课程失败");
    }
  }, [sid, navigate]);

  /* ── 加载中 / 错误 / 空 plan ── */

  if (loading) {
    return (
      <SetupShell current={2} hideInfoBar footer={null}>
        <div className="setup-heading compact-heading">
          <h1 className="course-title-main">正在加载…</h1>
        </div>
      </SetupShell>
    );
  }

  if (awaitingTrialGenerate && !plan) {
    const coverageItems: ProfileItem[] = sessionDetail?.sources?.map((source) => ({
      key: `source_${source.sourceVersionId}`,
      title: "已选资料",
      value: source.displayTitle,
      source: "课程作用域",
      editable: false,
    })) ?? [];

    return (
      <SetupShell
        current={2}
        hideInfoBar
        footer={
          <div className="setup-footer">
            <button className="ps-btn ps-btn-secondary" type="button" onClick={() => navigate("/courses/new")}>
              返回修改
            </button>
            <button
              className="ps-btn ps-btn-primary"
              disabled={generating}
              type="button"
              onClick={() => void runPlanGeneration(false)}
            >
              {generating ? "试生成中…" : "开始试生成学习方案"}
            </button>
          </div>
        }
      >
        <div className="setup-heading compact-heading">
          <h1 className="course-title-main">确认试生成上下文</h1>
          <p>请确认以下信息。试生成将基于学习目标、资料作用域与追问补充信息制定方案。</p>
        </div>
        <ProfileQaList items={[...profileItems, ...coverageItems]} />
        {error && <p className="cw-preview-text">{error}</p>}
      </SetupShell>
    );
  }

  if (generating) {
    return (
      <SetupShell current={2} hideInfoBar footer={null}>
        <div className="setup-heading compact-heading">
          <h1 className="course-title-main">正在生成学习方案…</h1>
          <p>AI 正在根据你的学习目标制定个性化方案，请稍候。</p>
        </div>
        <div className="ps-adjust-loading">
          <div className="ps-spinner" />
          <p>PlanGenerator 正在分析资料并构建方案</p>
        </div>
      </SetupShell>
    );
  }

  if (scopePrompt) {
    return (
      <SetupShell current={2} hideInfoBar footer={null}>
        <div className="setup-heading compact-heading">
          <h1 className="course-title-main">所选资料覆盖不足</h1>
          <p>{scopePrompt.message}</p>
        </div>
        <div className="ps-scope-gap-panel">
          <ul className="ps-scope-gap-list">
            {scopePrompt.gaps.map((gap) => (
              <li className="ps-scope-gap-item" key={`${gap.topic}-${gap.reason}`}>
                <strong>{gap.topic}</strong>
                <span>{gap.reason}</span>
                {gap.suggested_action && <em>{gap.suggested_action}</em>}
              </li>
            ))}
          </ul>
        </div>
        <div className="setup-footer">
          <button className="ps-btn ps-btn-secondary" type="button" onClick={() => navigate("/courses/new")}>
            补充资料
          </button>
          <button
            className="ps-btn ps-btn-primary"
            type="button"
            onClick={() => {
              setLoading(true);
              void runPlanGeneration(true);
            }}
          >
            仍按现有资料生成
          </button>
        </div>
      </SetupShell>
    );
  }

  if (error) {
    return (
      <SetupShell current={2} hideInfoBar footer={null}>
        <div className="setup-heading compact-heading">
          <h1 className="course-title-main">方案生成失败</h1>
          <p>{error}</p>
        </div>
        <div className="setup-footer">
          <button className="ps-btn ps-btn-primary" type="button" onClick={() => navigate("/courses/new")}>
            返回重试
          </button>
        </div>
      </SetupShell>
    );
  }

  if (!plan || phases.length === 0) {
    return (
      <SetupShell current={2} hideInfoBar footer={null}>
        <div className="setup-heading compact-heading">
          <h1 className="course-title-main">暂无学习方案</h1>
          <p>请返回上一步确认资料上传和方案生成是否完成。</p>
        </div>
        <div className="setup-footer">
          <button className="ps-btn ps-btn-primary" type="button" onClick={() => navigate("/courses/new")}>
            返回重新生成
          </button>
        </div>
      </SetupShell>
    );
  }

  return (
    <SetupShell
      current={2}
      hideInfoBar
      footer={
        <div className="setup-footer">
          <button
            className={`ps-btn ${isDirty ? "ps-btn-primary" : "ps-btn-secondary"}`}
            type="button"
            onClick={handleAdjustPlan}
            disabled={adjusting || starting}
          >
            {adjusting ? "正在调整…" : "调整方案"}
          </button>
          <button
            className={`ps-btn ${!isDirty ? "ps-btn-primary" : "ps-btn-secondary"}`}
            type="button"
            onClick={handleStartLearning}
            disabled={starting || adjusting}
          >
            {starting ? "正在启动…" : "开始学习"}
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

        {planCoverageGaps.length > 0 && (
          <div className="ps-scope-gap-banner">
            <strong>以下学习目标未完全被当前资料覆盖，未纳入本次计划：</strong>
            <ul className="ps-scope-gap-list">
              {planCoverageGaps.map((gap) => (
                <li className="ps-scope-gap-item" key={`${gap.topic}-${gap.reason}`}>
                  <span>{gap.topic}</span>
                  <span>{gap.reason}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

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
          <ProfileQaList
            editing={profileEditing}
            items={profileValues}
            onValueChange={handleProfileValueChange}
          />
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
                        const available = PHASE_POOL_TEMPLATES.filter((pp) => !selectedIds.has(pp.id));
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
                  {phases.map((p, i) => (
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
              {phases[trackPhaseIndex] && (
                <PlanOverviewCanvas
                  units={phases[trackPhaseIndex].units}
                  selectedUnitId={overviewSelectedUnitId}
                  onSelectUnit={(id) => {
                    setOverviewSelectedUnitId(id);
                    setOverviewSelectedTaskId(null);
                  }}
                />
              )}

              {/* 阶段 / 章节详情 */}
              <div className="ps-adjust-plan-detail">
                {(() => {
                  const tp = phases[trackPhaseIndex];
                  if (!tp) return null;

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
                              <div className="ps-detail-basic-row">
                                <dt>是否必修</dt>
                                <dd>{selectedTask.required ? "必修" : "选修"}</dd>
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
                      </>
                    );
                  }

                  /* 阶段信息 */
                  const unitCount = tp.units.length;
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
                          <div className="ps-detail-basic-row"><dt>章节数</dt><dd>{unitCount} 章</dd></div>
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
