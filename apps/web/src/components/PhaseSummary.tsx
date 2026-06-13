import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  Clock3,
  Lightbulb,
  Target,
  TrendingUp,
} from "lucide-react";

/* ── Mock data ── */

const completedTasks = [
  { id: "1-1", title: "计算机系统层次结构", check: "3/3", time: "25 分钟", mastered: true },
  { id: "1-2", title: "数据表示与运算基础", check: "2/3", time: "32 分钟", mastered: true },
  { id: "1-3", title: "指令系统概述", check: "2/2", time: "18 分钟", mastered: true },
  { id: "1-4", title: "CPU 基本组成", check: "2/2", time: "22 分钟", mastered: true },
  { id: "1-5", title: "数据通路与时序控制", check: "1/2", time: "28 分钟", mastered: false },
  { id: "1-6", title: "存储系统层次结构", check: "3/3", time: "20 分钟", mastered: true },
  { id: "1-7", title: "总线与 I/O 基础", check: "2/2", time: "15 分钟", mastered: true },
  { id: "1-8", title: "性能指标与评估", check: "2/3", time: "24 分钟", mastered: false },
];

const revisitItems = [
  { id: "r1", title: "数据通路与时序控制", reason: "即时检查正确率 50%，建议回顾微操作序列" },
  { id: "r2", title: "性能指标与评估", reason: "MIPS 与 CPI 的计算关系未完全掌握" },
];

const nextPhase = {
  name: "重点突破",
  tasks: 6,
  focus: ["Cache 映射与命中率", "流水线冒险与优化", "指令级并行"],
  representative: "Cache 替换算法与性能分析",
};

const aiSuggestions = [
  "在「数据通路」任务中，你对微操作序列的理解偏弱，建议在下阶段开始前先做一次针对性的回顾练习。",
  "目前的掌握速度略高于预估，可以考虑将下一阶段的「流水线冒险」任务调整为标准深度。",
];

export function PhaseSummary() {
  const masteredCount = completedTasks.filter((t) => t.mastered).length;
  const totalChecks = completedTasks.reduce((sum, t) => sum + parseInt(t.check.split("/")[1], 10), 0);
  const correctChecks = completedTasks.reduce((sum, t) => sum + parseInt(t.check.split("/")[0], 10), 0);

  return (
    <div className="phase-summary">
      <div className="ps-body">
        {/* ── Phase header ── */}
        <div className="ps-phase-badge">
          <Check size={14} /> 阶段完成
        </div>
        <h2 className="ps-phase-title">阶段一：基础梳理</h2>
        <p className="ps-phase-desc">
          已覆盖计算机组成原理的核心基础知识，为后续的重点突破阶段打下基础。
        </p>

        {/* ── Key metrics ── */}
        <div className="ps-metrics">
          <div className="ps-metric">
            <div className="ps-metric-value">{completedTasks.length}</div>
            <div className="ps-metric-label">完成任务</div>
          </div>
          <div className="ps-metric">
            <div className="ps-metric-value">{masteredCount}/{completedTasks.length}</div>
            <div className="ps-metric-label">已掌握</div>
          </div>
          <div className="ps-metric">
            <div className="ps-metric-value">{correctChecks}/{totalChecks}</div>
            <div className="ps-metric-label">检查正确</div>
          </div>
          <div className="ps-metric">
            <div className="ps-metric-value">~4.5h</div>
            <div className="ps-metric-label">投入时间</div>
          </div>
        </div>

        {/* ── Mastery bar ── */}
        <div className="ps-mastery-section">
          <div className="ps-section-head">
            <TrendingUp size={16} />
            <span>阶段掌握度</span>
          </div>
          <div className="ps-mastery-bar-track">
            <div className="ps-mastery-bar-fill" style={{ width: "85%" }} />
          </div>
          <div className="ps-mastery-meta">
            <span>良好</span>
            <span>{masteredCount}/{completedTasks.length} 个任务标记为已掌握</span>
          </div>
        </div>

        {/* ── Completed tasks ── */}
        <div className="ps-section">
          <div className="ps-section-head">
            <BookOpen size={16} />
            <span>已完成的任务</span>
          </div>
          <div className="ps-task-list">
            {completedTasks.map((task) => (
              <div className={`ps-task-row${task.mastered ? "" : " weak"}`} key={task.id}>
                <div className="ps-task-status">
                  {task.mastered ? (
                    <Check size={14} className="ps-check-icon" />
                  ) : (
                    <span className="ps-need-review">待巩固</span>
                  )}
                </div>
                <div className="ps-task-info">
                  <span className="ps-task-title">{task.title}</span>
                  <span className="ps-task-meta">
                    <Clock3 size={11} /> {task.time} · 检查 {task.check}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Revisit items ── */}
        {revisitItems.length > 0 && (
          <div className="ps-section">
            <div className="ps-section-head">
              <Target size={16} />
              <span>待巩固 / 已跳过</span>
            </div>
            <div className="ps-revisit-list">
              {revisitItems.map((item) => (
                <div className="ps-revisit-row" key={item.id}>
                  <ChevronRight size={13} className="ps-revisit-arrow" />
                  <div>
                    <span className="ps-revisit-title">{item.title}</span>
                    <span className="ps-revisit-reason">{item.reason}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Next phase preview ── */}
        <div className="ps-section ps-next-phase">
          <div className="ps-section-head">
            <ArrowRight size={16} />
            <span>下一阶段</span>
          </div>
          <div className="ps-next-card">
            <div className="ps-next-header">
              <span className="ps-next-label">阶段二</span>
              <strong>{nextPhase.name}</strong>
            </div>
            <div className="ps-next-detail">
              <div>
                <span className="ps-next-meta-label">任务数</span>
                <span>{nextPhase.tasks} 个</span>
              </div>
              <div>
                <span className="ps-next-meta-label">重点主题</span>
                <span>{nextPhase.focus.join("、")}</span>
              </div>
              <div>
                <span className="ps-next-meta-label">代表性任务</span>
                <span>{nextPhase.representative}</span>
              </div>
            </div>
          </div>
        </div>

        {/* ── AI suggestions ── */}
        <div className="ps-section">
          <div className="ps-section-head">
            <Lightbulb size={16} />
            <span>AI 建议</span>
          </div>
          <div className="ps-suggestions">
            {aiSuggestions.map((s, i) => (
              <div className="ps-suggestion-card" key={i}>
                <p>{s}</p>
              </div>
            ))}
          </div>
        </div>

        {/* ── Actions ── */}
        <div className="ps-actions">
          <button className="ps-btn ps-btn-secondary" type="button">
            调整计划
          </button>
          <button className="ps-btn ps-btn-primary" type="button">
            进入下一阶段 <ChevronRight size={18} />
          </button>
        </div>

        <div className="ps-footer-note">
          调整截止时间或目标深度请返回课程画像面板
        </div>
      </div>
    </div>
  );
}
