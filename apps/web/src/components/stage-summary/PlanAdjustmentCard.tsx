import {
  Check,
  ChevronDown,
  ChevronUp,
  CircleHelp,
  Clock3,
  Sparkles,
} from "lucide-react";

export type AdjustmentDecision = "pending" | "accepted" | "kept";

export interface PlanAdjustmentImpact {
  id: string;
  scope: string;
  change: string;
}

type PlanAdjustmentCardProps = {
  decision: AdjustmentDecision;
  impactOpen: boolean;
  onDecision: (decision: Exclude<AdjustmentDecision, "pending">) => void;
  onToggleImpact: () => void;
  suggestion?: string;
  triggerReason?: string;
  impacts?: PlanAdjustmentImpact[];
};

export function PlanAdjustmentCard({
  decision,
  impactOpen,
  onDecision,
  onToggleImpact,
  suggestion = "暂无调整建议。",
  triggerReason = "阶段进度数据尚未接入，建议保留当前方案。",
  impacts = [],
}: PlanAdjustmentCardProps) {
  const decisionLabel =
    decision === "accepted"
      ? "已应用"
      : decision === "kept"
        ? "已保留原方案"
        : "等待确认";

  return (
    <section className={`plan-adjustment-card ${decision}`}>
      <div className="adjustment-heading">
        <div>
          <Sparkles size={19} />
          <div>
            <h2>方案调整建议</h2>
            <p>AI 建议仅在你确认后应用。</p>
          </div>
        </div>
        <span className="adjustment-status">{decisionLabel}</span>
      </div>

      <div className="adjustment-summary">
        <div>
          <strong>建议内容</strong>
          <p>{suggestion}</p>
        </div>
        <div>
          <strong><CircleHelp size={15} /> 触发原因</strong>
          <p>{triggerReason}</p>
        </div>
        {impacts.length > 0 ? (
          <button className="impact-toggle" onClick={onToggleImpact} type="button">
            {impactOpen ? "收起调整影响" : "查看调整影响"}
            {impactOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </button>
        ) : null}
      </div>

      {impactOpen && impacts.length > 0 ? (
        <div className="adjustment-impact">
          <strong>调整影响（对比原方案）</strong>
          <div className="impact-flow">
            {impacts.map((item) => (
              <div className="impact-item" key={item.id}>
                <span>{item.scope}</span>
                <strong>{item.change}</strong>
              </div>
            ))}
            <div className="impact-workload">
              <Clock3 size={15} />
              <span>参考学习量变化不超过 ±5%</span>
            </div>
          </div>
        </div>
      ) : null}

      <div className="adjustment-actions">
        <button
          className={`button secondary${decision === "kept" ? " active" : ""}`}
          onClick={() => onDecision("kept")}
          type="button"
        >
          <Check size={16} /> 保留原方案
        </button>
        <button
          className={`button primary${decision === "accepted" ? " active" : ""}`}
          onClick={() => onDecision("accepted")}
          type="button"
        >
          <Check size={16} /> 应用建议
        </button>
      </div>
    </section>
  );
}
