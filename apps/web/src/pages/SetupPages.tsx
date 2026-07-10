import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Check, Circle, ExternalLink, Eye, FileWarning, FolderOpen, Loader, Plus, Upload, X } from "lucide-react";

import { SetupShell } from "../components/AppShell";
import { useCourseCreation } from "../components/CourseCreationContext";
import { InquiryStage, ProfileQaList, type QaDisplayItem } from "../components/ProfileQaDisplay";
import {
  bindSessionSources,
  createCourseSession,
  generatePlan,
  inquiryNext,
  previewSourceCoverage,
  updateCourseSession,
  type CoveragePreview,
  type InquiryEntry,
  type InquiryQuestion,
} from "../services/courseApi";
import { useLibrarySourcesQuery } from "../hooks/useLibrarySourcesQuery";
import { SourceUploadModal } from "../components/upload/SourceUploadModal";
import { type SourceItem } from "../services/documentApi";
import { buildLibraryReaderPath } from "../services/resourceCompat";
import { buildAdjustmentSupplement } from "./courseFlowHelpers";
import {
  clearCourseCreationStorage,
  COURSE_GOAL_KEY,
  COURSE_SESSION_ID_KEY,
  readStoredCourseGoal,
  shouldCreateFreshCourseSession,
} from "../lib/courseCreationStorage";
import { skipCourseInquiry } from "../lib/courseCreationFlags";

/* ── 子步骤定义 ── */

type SubStepType = "input" | "materials";
type SetupPhase = "profile" | "inquiry" | "trialConfirm";

interface SubStep {
  type: SubStepType;
  /** 副标题（当前步骤内容，灰色小字） */
  subtitle: string;
  /** 问题描述（显示在内容区上方） */
  question: string;
  /** type === "input" 时的 placeholder */
  placeholder?: string;
}

const SUB_STEPS: SubStep[] = [
  {
    type: "input",
    subtitle: "学习方向",
    question: "你想学习什么？",
    placeholder: "例如：我想学习高中数学的一轮复习，重点在函数、几何和概率统计…",
  },
  {
    type: "materials",
    subtitle: "学习资料",
    question: "选择你想使用的学习资料（至少 1 份已解析资料）",
  },
];

/* ── 步骤 1：建立学习档案 ── */

export function BuildProfilePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { addItem, setSessionId, sessionId, resetCreation } = useCourseCreation();

  const isAdjust = searchParams.get("adjust") === "true";
  const [phase, setPhase] = useState<SetupPhase>("profile");
  const [stepIndex, setStepIndex] = useState(0);
  const [inputValue, setInputValue] = useState("");
  const [selectedMaterials, setSelectedMaterials] = useState<Set<string>>(() => new Set());
  const [coveragePreview, setCoveragePreview] = useState<CoveragePreview | null>(null);
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  /* ── 上传弹窗 ── */
  const [showUpload, setShowUpload] = useState(false);

  /* ── 追问状态 ── */
  const [inquiryActive, setInquiryActive] = useState(false);
  const [inquiryLoading, setInquiryLoading] = useState(false);
  const [inquiryQuestions, setInquiryQuestions] = useState<InquiryQuestion[] | null>(null);
  const [inquiryHistory, setInquiryHistory] = useState<InquiryEntry[]>([]);
  const [inquiryAnswer, setInquiryAnswer] = useState("");
  const [inquirySummary, setInquirySummary] = useState<string | null>(null);
  const [inquirySessionId, setInquirySessionId] = useState<string | null>(null);

  /* ── 资料库数据 ── */
  const { data: librarySources = [], isLoading: sourcesLoading, refetch: reloadLibrarySources } = useLibrarySourcesQuery();
  const [uploadedVersionIds, setUploadedVersionIds] = useState<string[]>([]);

  const step = SUB_STEPS[stepIndex];
  const isGoalStep = stepIndex === 0;
  const isMaterialsStep = stepIndex === 1;

  function resetLocalSetupState() {
    setPhase("profile");
    setStepIndex(0);
    setInputValue("");
    setSelectedMaterials(new Set());
    setUploadedVersionIds([]);
    setCoveragePreview(null);
    setInquiryActive(false);
    setInquiryQuestions(null);
    setInquiryHistory([]);
    setInquiryAnswer("");
    setInquirySummary(null);
    setInquirySessionId(null);
  }

  // 新建建课入口必须隔离上一门课的 session / 追问 / 资料作用域
  useLayoutEffect(() => {
    if (isAdjust) return;
    resetCreation();
    clearCourseCreationStorage();
    resetLocalSetupState();
  }, [isAdjust, resetCreation]);

  function getSourceVersionId(source: SourceItem): string {
    return source.latestVersion?.id ?? source.id;
  }

  function isSourceCompleted(source: SourceItem): boolean {
    return source.latestVersion?.processingStatus === "completed";
  }

  function getSelectedSourceIds(): string[] {
    return [...new Set([...selectedMaterials, ...uploadedVersionIds])];
  }

  /** 右侧主按钮是否可用 */
  const canProceed = (() => {
    if (phase !== "profile") return false;
    switch (step.type) {
      case "input":
        return inputValue.trim().length > 0;
      case "materials": {
        const ids = getSelectedSourceIds();
        if (ids.length === 0) return false;
        return ids.every((id) => {
          const match = librarySources.find((s) => getSourceVersionId(s) === id);
          return match ? isSourceCompleted(match) : false;
        });
      }
    }
  })();

  /* ── 调整模式：重新生成方案 ── */
  async function goToPlan() {
    const storedSessionId = sessionId || sessionStorage.getItem("mentora-session-id");
    if (!storedSessionId) {
      navigate("/courses/new");
      return;
    }
    setActionLoading(true);
    try {
      const supplement = buildAdjustmentSupplement(inputValue, "");
      if (Object.keys(supplement).length > 0) {
        await updateCourseSession(storedSessionId, { profile_supplement: supplement });
      }
      await generatePlan(storedSessionId);
      navigate("/courses/new/plan");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "重新生成学习方案失败");
    } finally {
      setActionLoading(false);
    }
  }

  async function ensureSessionForGoal(): Promise<string> {
    const goal = inputValue.trim();
    const storedGoal = readStoredCourseGoal();
    let sid = sessionId || sessionStorage.getItem(COURSE_SESSION_ID_KEY);
    const needsFresh = shouldCreateFreshCourseSession(sid, storedGoal, goal);

    if (needsFresh) {
      const session = await createCourseSession(goal);
      sid = session.id;
      sessionStorage.setItem(COURSE_SESSION_ID_KEY, sid);
      setSessionId(sid);
      if (storedGoal && storedGoal !== goal) {
        setSelectedMaterials(new Set());
        setUploadedVersionIds([]);
        setCoveragePreview(null);
        setInquiryActive(false);
        setInquiryQuestions(null);
        setInquiryHistory([]);
        setInquiryAnswer("");
        setInquirySummary(null);
        setInquirySessionId(null);
      }
    } else if (sid) {
      await updateCourseSession(sid, { goal });
    }

    sessionStorage.setItem(COURSE_GOAL_KEY, goal);
    addItem({ key: "goal", title: "你想学习什么？", value: goal, source: "你的输入" });
    return sid!;
  }

  async function handleContinueFromGoal() {
    if (!canProceed) return;
    setActionLoading(true);
    try {
      await ensureSessionForGoal();
      setStepIndex(1);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "保存学习目标失败");
    } finally {
      setActionLoading(false);
    }
  }

  async function refreshCoveragePreview(sid: string, sourceIds: string[]) {
    setCoverageLoading(true);
    try {
      const preview = await previewSourceCoverage(sid, sourceIds);
      setCoveragePreview(preview);
    } catch {
      setCoveragePreview(null);
    } finally {
      setCoverageLoading(false);
    }
  }

  async function prepareSessionWithSources(): Promise<string> {
    const sourceIds = getSelectedSourceIds();
    if (sourceIds.length === 0) {
      throw new Error("请至少选择 1 份已解析资料");
    }

    const sid = await ensureSessionForGoal();
    await bindSessionSources(sid, sourceIds);
    await refreshCoveragePreview(sid, sourceIds);
    setInquirySessionId(sid);
    return sid;
  }

  async function handleStartInquiry() {
    setActionLoading(true);
    try {
      const sid = await prepareSessionWithSources();

      setInquiryActive(true);
      setPhase("inquiry");
      setInquiryLoading(true);
      try {
        const resp = await inquiryNext(sid);
        if (resp.ready) {
          setInquirySummary(resp.summary ?? "已收集足够信息。");
          setInquiryQuestions(null);
        } else if (resp.questions?.length) {
          setInquiryQuestions(resp.questions);
        }
      } catch {
        setInquirySummary("AI 追问暂时不可用。你可以稍后重试，或跳过追问进入试生成确认。");
      } finally {
        setInquiryLoading(false);
      }
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "绑定资料或启动追问失败");
    } finally {
      setActionLoading(false);
    }
  }

  async function handleSkipToTrialConfirm() {
    setActionLoading(true);
    try {
      await prepareSessionWithSources();
      setInquiryActive(false);
      setInquiryQuestions(null);
      setInquirySummary(null);
      setPhase("trialConfirm");
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "绑定资料失败");
    } finally {
      setActionLoading(false);
    }
  }

  /* ── 回答追问 ── */
  async function handleInquirySubmit(answerOverride?: string) {
    const answer = (answerOverride ?? inquiryAnswer).trim();
    if (!inquirySessionId || !answer || !inquiryQuestions?.[0]) return;

    const currentQuestion = inquiryQuestions[0].text;
    const historyIndex = inquiryHistory.length;

    setInquiryLoading(true);
    try {
      const resp = await inquiryNext(inquirySessionId, answer);
      setInquiryAnswer("");
      setInquiryHistory((prev) => [...prev, { question: currentQuestion, answer }]);
      addItem({
        key: `inquiry_${historyIndex}`,
        title: currentQuestion,
        value: answer,
        source: "你的回答",
      });

      if (resp.ready) {
        setInquirySummary(resp.summary ?? "已收集足够信息。");
        setInquiryQuestions(null);
      } else if (resp.questions?.length) {
        setInquiryQuestions(resp.questions);
      }
    } catch {
      setInquirySummary("AI 追问暂时不可用。你可以稍后重试，或跳过追问进入试生成确认。");
    } finally {
      setInquiryLoading(false);
    }
  }

  function handleInquiryComplete() {
    setInquiryActive(false);
    setPhase("trialConfirm");
  }

  function handleSkipInquiry() {
    setInquiryActive(false);
    setPhase("trialConfirm");
  }

  function handleTrialConfirm() {
    navigate("/courses/new/plan");
  }

  const trialQaItems: QaDisplayItem[] = [
    {
      key: "goal",
      title: "你想学习什么？",
      value: inputValue.trim(),
      source: "你的输入",
    },
    ...inquiryHistory.map((entry, index) => ({
      key: `inquiry_${index}`,
      title: entry.question,
      value: entry.answer,
      source: "你的回答",
    })),
  ];

  /* ── 资料选择 toggle ── */
  function toggleMaterial(id: string) {
    setSelectedMaterials((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
    setCoveragePreview(null);
  }

  /* ── 渲染内容区 ── */
  function renderCoveragePanel() {
    if (!isMaterialsStep || getSelectedSourceIds().length === 0) return null;
    if (coverageLoading) {
      return (
        <div className="bp-coverage-panel">
          <Loader size={16} className="spin" />
          <span>正在检查资料是否覆盖学习目标…</span>
        </div>
      );
    }
    if (!coveragePreview) return null;
    return (
      <div className={`bp-coverage-panel${coveragePreview.sufficient ? " bp-coverage-panel--ok" : " bp-coverage-panel--warn"}`}>
        <strong>{coveragePreview.sufficient ? "资料覆盖度良好" : "资料覆盖可能不足"}</strong>
        {!coveragePreview.sufficient && coveragePreview.gaps.length > 0 && (
          <ul className="bp-coverage-gaps">
            {coveragePreview.gaps.map((gap) => (
              <li key={`${gap.topic}-${gap.reason}`}>
                <span>{gap.topic}</span>
                <em>{gap.reason}</em>
              </li>
            ))}
          </ul>
        )}
        <p className="bp-coverage-note">已选 {coveragePreview.sources.length} 份资料将作为本课程唯一规划范围。</p>
      </div>
    );
  }

  function renderContent() {
    switch (step.type) {
      case "input":
        return (
          <div className="bp-input-box">
            <textarea
              className="bp-textarea"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={step.placeholder}
              rows={8}
            />
          </div>
        );

      case "materials":
        return (
          <div className="material-list">
            <div className="material-list-top">
              <button
                className="button secondary compact"
                onClick={() => setShowUpload(true)}
                type="button"
              >
                <Plus size={15} />上传资料
              </button>
            </div>
            {sourcesLoading ? (
              <div className="material-empty"><Loader size={20} className="spin" /><span>加载资料库…</span></div>
            ) : librarySources.length === 0 ? (
              <div className="material-empty"><span>资料库为空，请上传资料</span></div>
            ) : (
              librarySources.map((s) => {
                const vid = getSourceVersionId(s);
                const checked = selectedMaterials.has(vid);
                const completed = isSourceCompleted(s);
                const name = s.displayTitle || s.latestVersion?.originalFilename || "未命名";
                const size = s.latestVersion?.byteSize
                  ? s.latestVersion.byteSize > 1024 * 1024
                    ? `${(s.latestVersion.byteSize / (1024 * 1024)).toFixed(1)} MB`
                    : `${Math.round(s.latestVersion.byteSize / 1024)} KB`
                  : "";
                return (
                  <div className="material-row-wrap" key={vid}>
                    <button
                      className={`material-row${checked ? " selected" : ""}${completed ? "" : " material-row--disabled"}`}
                      disabled={!completed}
                      onClick={() => completed && toggleMaterial(vid)}
                      type="button"
                    >
                      <div className="material-row-left">
                        <FolderOpen size={16} />
                        <span className="material-name">{name}</span>
                        {size && <span className="bp-material-size">{size}</span>}
                        {!completed && <span className="bp-material-status">解析中，完成后可预览</span>}
                      </div>
                      <div className={`material-check${checked ? " selected" : ""}`}>
                        {checked ? <Check size={14} /> : <Circle size={18} />}
                      </div>
                    </button>
                    {completed ? (
                      <button
                        className="button secondary compact material-preview-btn"
                        onClick={() => navigate(buildLibraryReaderPath(vid, { returnTo: "/courses/new/profile" }))}
                        title="预览资料"
                        type="button"
                      >
                        <Eye size={14} />
                        <ExternalLink size={12} />
                      </button>
                    ) : null}
                  </div>
                );
              })
            )}
            {renderCoveragePanel()}
          </div>
        );
    }
  }

  function renderTrialConfirm() {
    return (
      <div className="trial-confirm-stage">
        <header className="trial-confirm-header">
          <h2>确认试生成上下文</h2>
          <p>请确认学习目标、资料范围与追问补充信息，确认后将进入试生成学习方案。</p>
        </header>
        <ProfileQaList items={trialQaItems} />
        {coveragePreview && (
          <div className={`bp-coverage-panel${coveragePreview.sufficient ? " bp-coverage-panel--ok" : " bp-coverage-panel--warn"}`}>
            <strong>{coveragePreview.sufficient ? "资料覆盖度良好" : "资料覆盖可能不足"}</strong>
            {!coveragePreview.sufficient && coveragePreview.gaps.length > 0 && (
              <ul className="bp-coverage-gaps">
                {coveragePreview.gaps.map((gap) => (
                  <li key={`${gap.topic}-${gap.reason}`}>
                    <span>{gap.topic}</span>
                    <em>{gap.reason}</em>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        <div className="trial-confirm-sources">
          <h3>已选资料（课程作用域）</h3>
          <ul>
            {(coveragePreview?.sources ?? []).map((source) => (
              <li key={source.sourceVersionId}>{source.displayTitle}</li>
            ))}
          </ul>
        </div>
      </div>
    );
  }

  useEffect(() => {
    if (phase !== "profile" || !isMaterialsStep) return;
    const sourceIds = getSelectedSourceIds();
    const sid = sessionId || sessionStorage.getItem("mentora-session-id");
    if (!sid || sourceIds.length === 0) {
      setCoveragePreview(null);
      return;
    }
    const timer = window.setTimeout(() => {
      void refreshCoveragePreview(sid, sourceIds);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [phase, isMaterialsStep, selectedMaterials, uploadedVersionIds, sessionId, inputValue]);

  return (
    <SetupShell
      current={1}
      footer={
        inquiryActive || phase === "inquiry" ? null :
        phase === "trialConfirm" ? (
          <div className="build-profile-actions">
            <button className="button secondary" onClick={() => { setPhase("profile"); setStepIndex(1); }} type="button">
              返回修改
            </button>
            <button className="button primary" onClick={handleTrialConfirm} type="button">
              确认试生成学习方案
            </button>
          </div>
        ) : isAdjust ? (
          <div className="build-profile-actions">
            <button
              className="button primary"
              disabled={!canProceed || actionLoading}
              onClick={goToPlan}
              type="button"
            >
              确认并生成学习方案
            </button>
            <button className="button secondary" onClick={() => navigate("/courses/new/plan")} type="button">
              返回确认方案
            </button>
          </div>
        ) : isGoalStep ? (
          <div className="build-profile-actions build-profile-actions--single">
            <button
              className="button primary"
              disabled={!canProceed || actionLoading}
              onClick={handleContinueFromGoal}
              type="button"
            >
              继续选择资料
            </button>
          </div>
        ) : skipCourseInquiry ? (
          <div className="build-profile-actions build-profile-actions--single">
            <button
              className="button primary"
              disabled={!canProceed || actionLoading || coverageLoading}
              onClick={handleSkipToTrialConfirm}
              type="button"
            >
              继续试生成确认
            </button>
          </div>
        ) : (
          <div className="build-profile-actions">
            <button
              className="button secondary"
              disabled={!canProceed || actionLoading || coverageLoading}
              onClick={handleSkipToTrialConfirm}
              type="button"
            >
              跳过追问
            </button>
            <button
              className="button primary"
              disabled={!canProceed || actionLoading || coverageLoading}
              onClick={handleStartInquiry}
              type="button"
            >
              开始追问补充信息
            </button>
          </div>
        )
      }
    >
      {inquiryActive ? (
        <InquiryStage
          answer={inquiryAnswer}
          currentQuestion={inquiryQuestions?.[0] ?? null}
          history={inquiryHistory}
          loading={inquiryLoading}
          onAnswerChange={setInquiryAnswer}
          onConfirm={handleInquiryComplete}
          onSkip={handleSkipInquiry}
          onSubmit={handleInquirySubmit}
          summary={inquirySummary}
        />
      ) : phase === "trialConfirm" ? (
        renderTrialConfirm()
      ) : (
      <div className="build-profile-page">
        {/* 大标题 */}
        <div className="build-profile-heading">
          <h1>建立学习档案</h1>
          <p>与 AI 讨论并建立你的学习档案</p>
        </div>

        {isAdjust ? (
          <>
            {/* 调整模式：问题描述 */}
            <p className="bp-question">已收到你的更改。是否重新生成学习方案？</p>

            {/* 内容区：输入框 */}
            <div className="build-profile-content">
              <div className="bp-input-box">
                <textarea
                  className="bp-textarea"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder="描述你希望如何调整学习方案…"
                  rows={8}
                />
              </div>
            </div>
          </>
        ) : (
          <>
            {/* 副标题：当前步骤 */}
            <p className="build-profile-subtitle">{step.subtitle}</p>

            {/* 问题描述 */}
            <p className="bp-question">{step.question}</p>

            {/* 内容区 */}
            <div className="build-profile-content">
              {renderContent()}
            </div>
          </>
        )}
      </div>
      )}

      {/* ── 上传资料弹窗 ── */}
      {showUpload && (
        <SourceUploadModal
          showLibraryNote={false}
          onClose={() => setShowUpload(false)}
          onUploaded={(result) => {
            setUploadedVersionIds((prev) => [...prev, result.sourceVersionId]);
            reloadLibrarySources();
          }}
        />
      )}
    </SetupShell>
  );
}
