import { ArrowLeft, BookOpenCheck, CheckCircle2, ClipboardCheck } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";

import { AppShell } from "../components/AppShell";
import {
  NextPhasePreview,
  type NextPhasePreviewData,
} from "../components/stage-summary/NextPhasePreview";
import {
  PlanAdjustmentCard,
  type AdjustmentDecision,
  type PlanAdjustmentImpact,
} from "../components/stage-summary/PlanAdjustmentCard";
import { StageEvidenceList } from "../components/stage-summary/StageEvidenceList";
import { StageTransitionActions } from "../components/stage-summary/StageTransitionActions";
import { getActivePlan, getCourseSession } from "../services/courseApi";
import { fetchSessionPhases } from "../services/documentApi";

function formatMinutes(m: number): string {
  if (m >= 60) return `约 ${Math.round(m / 60 * 10) / 10} 小时`;
  return `${m} 分钟`;
}

export function StageSummaryPage() {
  const { courseId, phaseId } = useParams();
  const navigate = useNavigate();
  const [impactOpen, setImpactOpen] = useState(false);
  const [adjustmentDecision, setAdjustmentDecision] =
    useState<AdjustmentDecision>("pending");
  const [transitionNotice, setTransitionNotice] = useState<string | null>(null);
  const [courseTitle, setCourseTitle] = useState("课程");
  const [phaseTitle, setPhaseTitle] = useState("阶段总结");
  const [phaseObjective, setPhaseObjective] = useState("");
  const [nextPreview, setNextPreview] = useState<NextPhasePreviewData | null>(null);
  const [adjustmentImpacts, setAdjustmentImpacts] = useState<PlanAdjustmentImpact[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!courseId) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([
      getActivePlan(courseId),
      getCourseSession(courseId),
      fetchSessionPhases(courseId),
    ])
      .then(([plan, session, phasesResp]) => {
        if (cancelled) return;
        setCourseTitle(session.title || session.goal || "课程");

        const phaseIndex = phaseId
          ? plan.phases.findIndex((p) => p.id === phaseId)
          : 0;
        const currentPhase = phaseIndex >= 0 ? plan.phases[phaseIndex] : plan.phases[0];
        if (currentPhase) {
          setPhaseTitle(currentPhase.title);
          setPhaseObjective(currentPhase.objective);
        }

        const nextPhase = phaseIndex >= 0 ? plan.phases[phaseIndex + 1] : plan.phases[1];
        if (nextPhase) {
          const tasks = nextPhase.units.flatMap((unit) =>
            unit.tasks.slice(0, 2).map((task) => {
              const label = task.task_type === "lecture" ? "讲解" : task.task_type === "exercise" ? "练习" : task.task_type;
              return `${unit.title || "学习单元"} · ${label}`;
            }),
          ).slice(0, 4);
          setNextPreview({
            name: nextPhase.title,
            phaseNumber: nextPhase.position + 1,
            goal: nextPhase.objective,
            tasks: tasks.length ? tasks : ["待生成具体任务"],
            connection: currentPhase
              ? `承接「${currentPhase.title}」的学习成果，进入「${nextPhase.title}」。`
              : "继续按学习计划推进。",
            workload: formatMinutes(nextPhase.estimated_minutes),
          });
        } else {
          setNextPreview(null);
        }

        setAdjustmentImpacts(
          (phasesResp.adjustments ?? []).map((item, index) => ({
            id: item.id || `adj-${index}`,
            scope: item.scope,
            change: item.change,
          })),
        );
      })
      .catch(() => {
        if (cancelled) return;
        setNextPreview(null);
        setAdjustmentImpacts([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [courseId, phaseId]);

  const adjustmentSuggestion = useMemo(() => {
    if (!adjustmentImpacts.length) return undefined;
    return adjustmentImpacts.map((item) => `${item.scope}：${item.change}`).join("；");
  }, [adjustmentImpacts]);

  if (!courseId) {
    navigate("/courses");
    return null;
  }

  const enterNextPhase = () => {
    setTransitionNotice("下一阶段已激活，正在返回课程主页。");
    window.setTimeout(() => navigate(`/courses/${courseId}`), 450);
  };

  return (
    <AppShell>
      <main className="stage-summary-page">
        <Link className="summary-back-link" to={`/courses/${courseId}`}>
          <ArrowLeft size={17} /> {courseTitle}
        </Link>
        <h1>{phaseTitle} · 阶段总结</h1>

        <section className="summary-completion">
          <span className="completion-icon"><CheckCircle2 size={34} /></span>
          <div className="completion-copy">
            <strong>阶段检查已完成</strong>
            <h2>{phaseTitle}</h2>
            <p>{phaseObjective || "可以进入下一阶段。"}</p>
          </div>
          <div className="completion-facts">
            <div>
              <BookOpenCheck size={20} />
              <span>核心任务<strong>—</strong></span>
            </div>
            <div>
              <ClipboardCheck size={20} />
              <span>阶段检查<strong>—</strong></span>
            </div>
            <div className="quiet-fact">
              <span>进度数据<strong>待接入</strong></span>
            </div>
          </div>
        </section>

        {loading ? (
          <p className="stage-summary-loading">正在加载阶段数据…</p>
        ) : (
          <>
            <div className="stage-summary-grid">
              <StageEvidenceList evidence={[]} />
              <NextPhasePreview preview={nextPreview} />
            </div>

            <PlanAdjustmentCard
              decision={adjustmentDecision}
              impactOpen={impactOpen}
              onDecision={setAdjustmentDecision}
              onToggleImpact={() => setImpactOpen((open) => !open)}
              suggestion={adjustmentSuggestion}
              impacts={adjustmentImpacts}
            />
          </>
        )}

        <StageTransitionActions
          notice={transitionNotice}
          onReinforce={() => navigate(`/courses/${courseId}?focus=reinforcement`)}
          onTransition={enterNextPhase}
        />
      </main>
    </AppShell>
  );
}
