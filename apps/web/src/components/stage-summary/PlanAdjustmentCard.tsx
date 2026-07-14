import {
  Check,
  ChevronDown,
  ChevronUp,
  CircleHelp,
  Clock3,
  Sparkles,
} from "lucide-react";

import { adjustmentImpact } from "../../data/courses";

export type AdjustmentDecision = "pending" | "accepted" | "kept";

type PlanAdjustmentCardProps = {
  decision: AdjustmentDecision;
  impactOpen: boolean;
  onDecision: (decision: Exclude<AdjustmentDecision, "pending">) => void;
  onToggleImpact: () => void;
};

export function PlanAdjustmentCard({
  decision,
  impactOpen,
  onDecision,
  onToggleImpact,
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
          <p>
            将“Cache 替换策略”加入补学清单，并把下一阶段第一项综合题调整为引导式练习。
          </p>
        </div>
        <div>
          <strong><CircleHelp size={15} /> 触发原因</strong>
          <p>2 项任务掌握度不足，1 项任务尚未完成。</p>
        </div>
        <button className="impact-toggle" onClick={onToggleImpact} type="button">
          {impactOpen ? "收起调整影响" : "查看调整影响"}
          {impactOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </button>
      </div>

      {impactOpen ? (
        <div className="adjustment-impact">
          <strong>调整影响（对比原方案）</strong>
          <div className="impact-flow">
            {adjustmentImpact.map((item) => (
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
        {decision === "pending" ? (
          <>
            <button className="button secondary" onClick={() => onDecision("kept")} type="button">
              保持原方案
            </button>
            <button className="button primary" onClick={() => onDecision("accepted")} type="button">
              <Check size={16} /> 接受调整
            </button>
          </>
        ) : (
          <p>
            <Check size={16} />
            {decision === "accepted"
              ? "调整已应用，下一阶段将使用引导式练习。"
              : "已保留原方案，仍可正常进入下一阶段。"}
          </p>
        )}
      </div>
    </section>
  );
}
