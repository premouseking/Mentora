import { ArrowRight, Info } from "lucide-react";

type StageTransitionActionsProps = {
  notice: string | null;
  onReinforce: () => void;
  onTransition: () => void;
};

export function StageTransitionActions({
  notice,
  onReinforce,
  onTransition,
}: StageTransitionActionsProps) {
  return (
    <section className="stage-transition-actions">
      <div className="transition-note" role="status">
        <Info size={16} />
        <span>{notice ?? "未完成内容将保留在补学清单中，之后可以继续学习。"}</span>
      </div>
      <div>
        <button className="button secondary" onClick={onReinforce} type="button">
          先补强薄弱项
        </button>
        <button className="button primary" onClick={onTransition} type="button">
          进入下一阶段 <ArrowRight size={17} />
        </button>
      </div>
    </section>
  );
}
