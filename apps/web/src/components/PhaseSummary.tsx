import { X } from "lucide-react";
import { useCallback, useRef, useState } from "react";

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

/* ── 左栏：纵向阶段导航（复用建课确认页滑轨逻辑，方向横→纵）── */

/** PhaseNav 只需阶段的 id 与标题，定义本地最小类型以脱离合并接口 */
type NavPhase = { id: string; title: string };

/** 计算 block 在给定 index 的 offsetTop（含 margin-top: -14px 累积偏移） */
function offsetOf(index: number, blockBasis: number) {
  if (index <= 0) return 0;
  return index * blockBasis - 14 * index;
}

function PhaseNav({ phases }: { phases: NavPhase[] }) {
  const N = phases.length;
  const [activeIndex, setActiveIndex] = useState(0);
  const navRef = useRef<HTMLDivElement>(null);
  const targetRef = useRef(0); // 当前滚动的目标 phase index

  /* ── 取窗口起始 snap 块的实测 offsetTop（避免 basis 估算与负 margin 误差）── */
  const snapTopOf = useCallback((snapIndex: number) => {
    const el = navRef.current;
    if (!el) return 0;
    const blocks = el.querySelectorAll<HTMLElement>(".ps-phase-nav-block");
    const block = blocks[snapIndex];
    // offsetTop 相对 offsetParent（.ps-phase-nav 已设 position:relative）
    return block ? block.offsetTop : offsetOf(snapIndex, el.clientHeight / 4);
  }, []);

  /* ── 统一滚动到 phase[index]，方向感知的双向 snap ── */
  const scrollToPhase = useCallback(
    (index: number) => {
      const el = navRef.current;
      if (!el) return;
      const prev = targetRef.current;
      const down = index > prev; // 向下滚（index 增大）为 true；相等不会进此函数
      targetRef.current = index;
      setActiveIndex(index);
      const maxStart = Math.max(0, N - 4);
      // 向下滚：选中停在上起第 3 位（index - 2）；向上滚：选中停在下起第 3 位（index - 1）
      const anchor = down ? index - 2 : index - 1;
      const snapIndex = Math.max(0, Math.min(anchor, maxStart));
      el.scrollTo({ top: snapTopOf(snapIndex), behavior: "smooth" });
    },
    [N, snapTopOf],
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
    <div className="ps-phase-nav" ref={navRef} onWheel={handleWheel}>
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

/* ── 主体：v6 三栏布局 ── */

export function PhaseSummary({
  onClose,
}: {
  onClose: () => void;
}) {
  const plan = MOCK_PLAN;
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
        <PhaseNav phases={plan.phases} />
        {/* 中栏：主干 + 分支画板（占位，待实现） */}
        <div className="ps-canvas-placeholder">主干分支画板</div>
        {/* 右栏：可收起详情栏（占位，待实现） */}
        <div className="ps-detail-placeholder">详情</div>
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
