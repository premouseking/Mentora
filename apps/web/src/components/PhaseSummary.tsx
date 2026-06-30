import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  Lightbulb,
  Target,
  TrendingUp,
  X,
} from "lucide-react";
import { useMemo } from "react";
import type { ActivePlan } from "../services/courseApi";

/* ── 辅助 ── */

const TASK_TYPE_LABEL: Record<string, string> = {
  lecture: "讲解",
  exercise: "练习",
  project: "项目",
  review: "复习",
};

function formatMinutes(m: number): string {
  if (m >= 60) return `${Math.round(m / 60)}h`;
  return `${m} 分钟`;
}

/* ── 组件 ── */

export function PhaseSummary({
  plan,
  onClose,
}: {
  plan: ActivePlan;
  onClose: () => void;
}) {
  const phases = plan.phases;

  // 总分阶段数
  const phaseCount = phases.length;

  // 总任务数（所有 unit 的 task_templates 数量）
  const totalTasks = useMemo(
    () =>
      phases.reduce(
        (sum, p) =>
          sum + p.units.reduce((usum, u) => usum + u.tasks.length, 0),
        0,
      ),
    [phases],
  );

  // 总预估时长
  const totalMinutes = useMemo(
    () => phases.reduce((sum, p) => sum + p.estimated_minutes, 0),
    [phases],
  );

  return (
    <div className="phase-summary">
      {/* Top hint bar */}
      <div className="quiz-swipe-hint" onPointerDown={(e) => e.stopPropagation()}>
        <div className="quiz-swipe-hint-left">
          <ChevronDown size={14} />
          <span>下拉收起</span>
        </div>
        <button className="quiz-hint-close" onClick={onClose} title="关闭">
          <X size={14} />
        </button>
      </div>
      <div className="ps-body">
        {/* ── 方案概览 ── */}
        <div className="ps-phase-badge">
          <Check size={14} /> 学习方案
        </div>
        <h2 className="ps-phase-title">共 {phaseCount} 个阶段</h2>
        <p className="ps-phase-desc">
          共 {totalTasks} 个任务 · 预计 {formatMinutes(totalMinutes)}
        </p>

        {/* ── Key metrics ── */}
        <div className="ps-metrics">
          <div className="ps-metric">
            <div className="ps-metric-value">{phaseCount}</div>
            <div className="ps-metric-label">学习阶段</div>
          </div>
          <div className="ps-metric">
            <div className="ps-metric-value">{phases.reduce((s, p) => s + p.units.length, 0)}</div>
            <div className="ps-metric-label">学习单元</div>
          </div>
          <div className="ps-metric">
            <div className="ps-metric-value">{totalTasks}</div>
            <div className="ps-metric-label">任务</div>
          </div>
          <div className="ps-metric">
            <div className="ps-metric-value">{formatMinutes(totalMinutes)}</div>
            <div className="ps-metric-label">预估时长</div>
          </div>
        </div>

        {/* ── Mastery bar（暂无评估数据，占位） ── */}
        <div className="ps-mastery-section">
          <div className="ps-section-head">
            <TrendingUp size={16} />
            <span>整体掌握度</span>
          </div>
          <div className="ps-mastery-bar-track">
            <div className="ps-mastery-bar-fill" style={{ width: "0%" }} />
          </div>
          <div className="ps-mastery-meta">
            <span>尚未开始</span>
            <span>开始学习第一单元后可查看进度</span>
          </div>
        </div>

        {/* ── 各阶段概览 ── */}
        <div className="ps-section">
          <div className="ps-section-head">
            <BookOpen size={16} />
            <span>阶段安排</span>
          </div>
          <div className="ps-task-list">
            {phases.map((phase) => {
              const unitCount = phase.units.length;
              const taskCount = phase.units.reduce(
                (s, u) => s + u.tasks.length,
                0,
              );
              const sharePct = totalMinutes > 0
                ? Math.round((phase.estimated_minutes / totalMinutes) * 100)
                : 0;

              return (
                <div className="ps-task-row" key={phase.id}>
                  <div className="ps-task-status">
                    <span className="ps-phase-num">{phase.position + 1}</span>
                  </div>
                  <div className="ps-task-info">
                    <span className="ps-task-title">
                      {phase.title}
                      <span className="ps-phase-share">（{sharePct}%）</span>
                    </span>
                    <span className="ps-task-meta">
                      <Clock3 size={11} /> {formatMinutes(phase.estimated_minutes)}
                      {" · "}{unitCount} 单元 · {taskCount} 任务
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* ── 首阶段单元详览 ── */}
        {phases.length > 0 && phases[0].units.length > 0 && (
          <div className="ps-section">
            <div className="ps-section-head">
              <Target size={16} />
              <span>第一阶段「{phases[0].title}」单元</span>
            </div>
            <div className="ps-revisit-list">
              {phases[0].units.map((unit) => (
                <div className="ps-revisit-row" key={unit.id}>
                  <ChevronRight size={13} className="ps-revisit-arrow" />
                  <div>
                    <span className="ps-revisit-title">
                      {unit.title || `单元 ${unit.position + 1}`}
                    </span>
                    <span className="ps-revisit-reason">
                      {unit.tasks
                        .map((t) => TASK_TYPE_LABEL[t.task_type] ?? t.task_type)
                        .join("、")}
                      {" · "}{formatMinutes(unit.estimated_minutes)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── 下一阶段预览 ── */}
        {phases.length > 1 && (() => {
          const next = phases[1];
          return (
            <div className="ps-section ps-next-phase">
              <div className="ps-section-head">
                <ArrowRight size={16} />
                <span>下一阶段</span>
              </div>
              <div className="ps-next-card">
                <div className="ps-next-header">
                  <span className="ps-next-label">阶段{next.position + 1}</span>
                  <strong>{next.title}</strong>
                </div>
                <div className="ps-next-detail">
                  <div>
                    <span className="ps-next-meta-label">任务数</span>
                    <span>
                      {next.units.reduce((s, u) => s + u.tasks.length, 0)} 个
                    </span>
                  </div>
                  <div>
                    <span className="ps-next-meta-label">预估时长</span>
                    <span>{formatMinutes(next.estimated_minutes)}</span>
                  </div>
                  <div>
                    <span className="ps-next-meta-label">目标</span>
                    <span>{next.objective || next.title}</span>
                  </div>
                </div>
              </div>
            </div>
          );
        })()}

        {/* ── AI 建议（暂无，占位） ── */}
        <div className="ps-section">
          <div className="ps-section-head">
            <Lightbulb size={16} />
            <span>AI 建议</span>
          </div>
          <div className="ps-suggestions">
            <div className="ps-suggestion-card">
              <p>开始学习第一个单元后，AI 会根据你的表现提供个性化建议。</p>
            </div>
          </div>
        </div>

        {/* ── Actions ── */}
        <div className="ps-actions">
          <button className="ps-btn ps-btn-secondary" type="button">
            调整计划
          </button>
          <button className="ps-btn ps-btn-primary" type="button">
            开始学习 <ChevronRight size={18} />
          </button>
        </div>

        <div className="ps-footer-note">
          调整截止时间或目标深度请返回课程画像面板
        </div>
      </div>
    </div>
  );
}
