import { ArrowRight, Clock3, Link2, Target } from "lucide-react";

export interface NextPhasePreviewData {
  name: string;
  phaseNumber: number;
  goal: string;
  tasks: string[];
  connection: string;
  workload: string;
}

export function NextPhasePreview({ preview }: { preview?: NextPhasePreviewData | null }) {
  if (!preview) {
    return (
      <aside className="summary-panel next-phase-panel">
        <div className="summary-section-heading">
          <h2>下一阶段</h2>
        </div>
        <p>暂无下一阶段信息</p>
      </aside>
    );
  }

  return (
    <aside className="summary-panel next-phase-panel">
      <div className="summary-section-heading">
        <h2>下一阶段：{preview.name}</h2>
        <span>第 {preview.phaseNumber} 阶段</span>
      </div>
      <div className="next-phase-goal">
        <Target size={18} />
        <div>
          <strong>阶段目标</strong>
          <p>{preview.goal}</p>
        </div>
      </div>
      <div className="next-phase-tasks">
        <strong>代表任务（{preview.tasks.length} 项）</strong>
        {preview.tasks.map((task) => (
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
          <p>{preview.connection}</p>
        </div>
      </div>
      <span className="next-phase-workload">
        <Clock3 size={14} /> {preview.workload}
      </span>
    </aside>
  );
}
