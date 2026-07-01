import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Check, Circle, FileWarning, FolderOpen, Folders, Globe, Loader, Plus, Upload, X } from "lucide-react";

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
import { fetchSources, type SourceItem } from "../services/documentApi";
import { uploadFile, type UploadProgress } from "../services/uploadService";
import { buildAdjustmentSupplement } from "./courseFlowHelpers";

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
  const { addItem, setSessionId, sessionId } = useCourseCreation();

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
  const [uploadDragOver, setUploadDragOver] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* ── 追问状态 ── */
  const [inquiryActive, setInquiryActive] = useState(false);
  const [inquiryLoading, setInquiryLoading] = useState(false);
  const [inquiryQuestions, setInquiryQuestions] = useState<InquiryQuestion[] | null>(null);
  const [inquiryHistory, setInquiryHistory] = useState<InquiryEntry[]>([]);
  const [inquiryAnswer, setInquiryAnswer] = useState("");
  const [inquirySummary, setInquirySummary] = useState<string | null>(null);
  const [inquirySessionId, setInquirySessionId] = useState<string | null>(null);

  /* ── 资料库数据 ── */
  const [librarySources, setLibrarySources] = useState<SourceItem[]>([]);
  const [uploadedVersionIds, setUploadedVersionIds] = useState<string[]>([]);
  const [sourcesLoading, setSourcesLoading] = useState(true);

  const loadLibrarySources = useCallback(async () => {
    try {
      const sources = await fetchSources();
      setLibrarySources(sources);
    } catch {
      // 静默降级
    } finally {
      setSourcesLoading(false);
    }
  }, []);

  useEffect(() => { loadLibrarySources(); }, [loadLibrarySources]);

  const step = SUB_STEPS[stepIndex];
  const isGoalStep = stepIndex === 0;
  const isMaterialsStep = stepIndex === 1;

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
    let sid = sessionId || sessionStorage.getItem("mentora-session-id");
    if (!sid) {
      const session = await createCourseSession(goal);
      sid = session.id;
      sessionStorage.setItem("mentora-session-id", sid);
      setSessionId(sid);
    } else {
      await updateCourseSession(sid, { goal });
    }
    sessionStorage.setItem("mentora-course-goal", goal);
    addItem({ key: "goal", title: "你想学习什么？", value: goal, source: "你的输入" });
    return sid;
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

  async function handleStartInquiry() {
    const sourceIds = getSelectedSourceIds();
    if (sourceIds.length === 0) {
      alert("请至少选择 1 份已解析资料");
      return;
    }

    setActionLoading(true);
    try {
      const sid = await ensureSessionForGoal();
      await bindSessionSources(sid, sourceIds);
      await refreshCoveragePreview(sid, sourceIds);

      setInquiryActive(true);
      setPhase("inquiry");
      setInquirySessionId(sid);
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

  /* ── 上传资料 ── */
  function pickFile() {
    fileInputRef.current?.click();
  }

  async function handleUploadFile(file: File) {
    setUploadProgress({ step: "create", message: "正在创建上传会话…" });
    try {
      const result = await uploadFile(file, (p) => setUploadProgress(p));
      // 记录上传的 sourceVersionId，后续绑定到课程
      setUploadedVersionIds((prev) => [...prev, result.sourceVersionId]);
      // 刷新资料列表
      loadLibrarySources();
      setUploadProgress({ step: "done", message: "上传完成，解析中…" });
      setTimeout(() => {
        setShowUpload(false);
        setUploadProgress(null);
      }, 800);
    } catch (err: unknown) {
      setUploadProgress({
        step: "error",
        message: err instanceof Error ? err.message : "上传失败",
      });
    }
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) handleUploadFile(f);
    e.target.value = "";
  }

  function onUploadDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setUploadDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleUploadFile(f);
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
                  <button
                    key={vid}
                    className={`material-row${checked ? " selected" : ""}${completed ? "" : " material-row--disabled"}`}
                    disabled={!completed}
                    onClick={() => completed && toggleMaterial(vid)}
                    type="button"
                  >
                    <div className="material-row-left">
                      <FolderOpen size={16} />
                      <span className="material-name">{name}</span>
                      {size && <span className="bp-material-size">{size}</span>}
                      {!completed && <span className="bp-material-status">解析中</span>}
                    </div>
                  <div className={`material-check${checked ? " selected" : ""}`}>
                    {checked ? <Check size={14} /> : <Circle size={18} />}
                  </div>
                </button>
              );
            }))}
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
        ) : (
          <div className="build-profile-actions build-profile-actions--single">
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
        <>
          <input
            ref={fileInputRef}
            accept=".pdf,.docx,.pptx,.xlsx,.png,.jpg,.jpeg,.mp4,.mp3"
            style={{ display: "none" }}
            type="file"
            onChange={onFileChange}
          />
          <div className="library-modal-overlay" onClick={() => setShowUpload(false)}>
            <div className="library-modal" onClick={(e) => e.stopPropagation()}>
              {uploadProgress ? (
                uploadProgress.step === "error" ? (
                  <>
                    <header className="library-modal-header">
                      <strong>上传失败</strong>
                      <button aria-label="关闭" onClick={() => setShowUpload(false)} type="button"><X size={17} /></button>
                    </header>
                    <div className="library-upload-zone" style={{ textAlign: "center", padding: "40px 24px" }}>
                      <FileWarning size={32} color="#e74c3c" />
                      <p style={{ color: "#e74c3c", marginTop: 12 }}>{uploadProgress.message}</p>
                      <button className="button secondary" onClick={() => setUploadProgress(null)} style={{ marginTop: 12 }}>重新上传</button>
                    </div>
                  </>
                ) : (
                  <>
                    <header className="library-modal-header">
                      <strong>正在上传</strong>
                      <button aria-label="关闭" onClick={() => setShowUpload(false)} type="button"><X size={17} /></button>
                    </header>
                    <div className="library-upload-zone" style={{ textAlign: "center", padding: "40px 24px" }}>
                      <Loader size={32} className="spin" />
                      <p style={{ marginTop: 12 }}>{uploadProgress.message}</p>
                    </div>
                  </>
                )
              ) : (
                <>
                  <header className="library-modal-header">
                    <strong>添加资料</strong>
                    <button aria-label="关闭" onClick={() => setShowUpload(false)} type="button"><X size={17} /></button>
                  </header>
                  <div
                    className={`library-upload-zone${uploadDragOver ? " drag-over" : ""}`}
                    onDragEnter={() => setUploadDragOver(true)}
                    onDragLeave={() => setUploadDragOver(false)}
                    onDragOver={(e) => e.preventDefault()}
                    onDrop={onUploadDrop}
                  >
                    <Upload size={28} />
                    <strong>拖拽文件到此处上传</strong>
                    <span>支持 PDF、Word、PPT、图片、视频、音频</span>
                  </div>
                  <div className="library-modal-separator"><span>或者</span></div>
                  <div className="library-add-options">
                    <button className="button secondary" type="button" onClick={pickFile}><Folders size={16} />从本地选择文件</button>
                    <button className="button secondary" type="button" onClick={() => {}}><Globe size={16} />添加网页链接</button>
                  </div>
                  <p className="library-upload-note">上传资料仅进入资源库，不会自动授权任何课程访问。</p>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </SetupShell>
  );
}
