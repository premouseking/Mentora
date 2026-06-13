import { ArrowRight, Clock3, Link2, Target } from "lucide-react";

import { nextPhasePreview } from "../../data/courses";

export function NextPhasePreview() {
  return (
    <aside className="summary-panel next-phase-panel">
      <div className="summary-section-heading">
        <h2>下一阶段：{nextPhasePreview.name}</h2>
        <span>第 3 阶段</span>
      </div>
      <div className="next-phase-goal">
        <Target size={18} />
        <div>
          <strong>阶段目标</strong>
          <p>{nextPhasePreview.goal}</p>
        </div>
      </div>
      <div className="next-phase-tasks">
        <strong>代表任务（{nextPhasePreview.tasks.length} 项）</strong>
        {nextPhasePreview.tasks.map((task) => (
          <div key={task}>
            <span>{task}</span>
            <ArrowRight size={15} />
          </div>
        ))}
      </div>
      <div className="phase-connection">
        <Link2 size={17} />
        <div>
          <strong>与本阶段的衔接</strong>
          <p>{nextPhasePreview.connection}</p>
        </div>
      </div>
      <span className="next-phase-workload">
        <Clock3 size={14} /> {nextPhasePreview.workload}
      </span>
    </aside>
  );
}
