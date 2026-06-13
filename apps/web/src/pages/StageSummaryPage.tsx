import { ArrowLeft, BookOpenCheck, CheckCircle2, ClipboardCheck } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useState } from "react";

import { AppShell } from "../components/AppShell";
import { NextPhasePreview } from "../components/stage-summary/NextPhasePreview";
import {
  PlanAdjustmentCard,
  type AdjustmentDecision,
} from "../components/stage-summary/PlanAdjustmentCard";
import { StageEvidenceList } from "../components/stage-summary/StageEvidenceList";
import { StageTransitionActions } from "../components/stage-summary/StageTransitionActions";
import { stageEvidence } from "../data/courses";

export function StageSummaryPage() {
  const { courseId = "computer-architecture" } = useParams();
  const navigate = useNavigate();
  const [impactOpen, setImpactOpen] = useState(false);
  const [adjustmentDecision, setAdjustmentDecision] =
    useState<AdjustmentDecision>("pending");
  const [transitionNotice, setTransitionNotice] = useState<string | null>(null);

  const enterNextPhase = () => {
    setTransitionNotice("下一阶段已激活，正在返回课程主页。");
    window.setTimeout(() => navigate(`/courses/${courseId}`), 450);
  };

  return (
    <AppShell>
      <main className="stage-summary-page">
        <Link className="summary-back-link" to={`/courses/${courseId}`}>
          <ArrowLeft size={17} /> 计算机组成原理
        </Link>
        <h1>重点突破 · 阶段总结</h1>

        <section className="summary-completion">
          <span className="completion-icon"><CheckCircle2 size={34} /></span>
          <div className="completion-copy">
            <strong>阶段检查已完成</strong>
            <h2>重点突破</h2>
            <p>可以进入下一阶段，建议保留 2 项补学任务。</p>
          </div>
          <div className="completion-facts">
            <div>
              <BookOpenCheck size={20} />
              <span>核心任务<strong>4 / 5</strong></span>
            </div>
            <div>
              <ClipboardCheck size={20} />
              <span>阶段检查<strong>82 分</strong></span>
            </div>
            <div className="quiet-fact">
              <span>参考学习量<strong>约 35%</strong></span>
            </div>
          </div>
        </section>

        <div className="stage-summary-grid">
          <StageEvidenceList evidence={stageEvidence} />
          <NextPhasePreview />
        </div>

        <PlanAdjustmentCard
          decision={adjustmentDecision}
          impactOpen={impactOpen}
          onDecision={setAdjustmentDecision}
          onToggleImpact={() => setImpactOpen((open) => !open)}
        />

        <StageTransitionActions
          notice={transitionNotice}
          onReinforce={() => navigate(`/courses/${courseId}?focus=reinforcement`)}
          onTransition={enterNextPhase}
        />
      </main>
    </AppShell>
  );
}
