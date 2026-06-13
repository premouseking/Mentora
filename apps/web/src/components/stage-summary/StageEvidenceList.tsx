import { AlertCircle, CheckCircle2, MinusCircle } from "lucide-react";

import type { EvidenceState, StageEvidence } from "../../data/courses";

const groupConfig: Array<{
  state: EvidenceState;
  label: string;
  icon: typeof CheckCircle2;
}> = [
  { state: "mastered", label: "已掌握", icon: CheckCircle2 },
  { state: "reinforce", label: "待巩固", icon: AlertCircle },
  { state: "unfinished", label: "未完成", icon: MinusCircle },
];

export function StageEvidenceList({ evidence }: { evidence: StageEvidence[] }) {
  return (
    <section className="summary-panel evidence-panel">
      <div className="summary-section-heading">
        <h2>本阶段学习证据</h2>
        <span>基于任务与检查结果</span>
      </div>
      <div className="evidence-groups">
        {groupConfig.map(({ state, label, icon: Icon }) => {
          const items = evidence.filter((item) => item.state === state);
          return (
            <section className={`evidence-group ${state}`} key={state}>
              <header>
                <Icon size={17} />
                <strong>{label}</strong>
                <span>（{items.length} 项）</span>
              </header>
              <div className="evidence-rows">
                {items.map((item) => (
                  <div className="evidence-row" key={item.id}>
                    <strong>{item.name}</strong>
                    <span>{item.source}</span>
                    <p>{item.detail}</p>
                  </div>
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </section>
  );
}
