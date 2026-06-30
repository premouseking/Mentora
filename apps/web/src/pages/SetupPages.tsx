import { useRef, useState, type DragEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Check, Circle, FileWarning, FolderOpen, Folders, Globe, Loader, Plus, Upload, X } from "lucide-react";

import { SetupShell } from "../components/AppShell";
import { useCourseCreation } from "../components/CourseCreationContext";
import { createCourseSession } from "../services/courseApi";
import { uploadFile, type UploadProgress } from "../services/uploadService";

/* ── 子步骤定义 ── */

type SubStepType = "input" | "choice" | "materials";

interface SubStep {
  type: SubStepType;
  /** 副标题（当前步骤内容，灰色小字） */
  subtitle: string;
  /** 问题描述（显示在内容区上方） */
  question: string;
  /** type === "input" 时的 placeholder */
  placeholder?: string;
  /** type === "choice" 时的选项列表 */
  options?: string[];
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
    question: "选择你想使用的学习资料",
  },
  {
    type: "choice",
    subtitle: "学习方式",
    question: "你更喜欢哪种学习方式？",
    options: ["视频课程", "阅读教材", "练习题", "动手实践", "小组讨论", "一对一辅导"],
  },
  {
    type: "choice",
    subtitle: "时间安排",
    question: "你的学习时间安排大致是怎样的？",
    options: ["每天 30 分钟", "每天 1 小时", "每天 2 小时", "工作日晚上", "周末集中", "灵活安排"],
  },
];

/* ── Mock 资料 ── */

const MOCK_MATERIALS = [
  { id: "m1", name: "人教版高中数学必修一.pdf", size: "12.4 MB" },
  { id: "m2", name: "人教版高中数学必修二.pdf", size: "11.8 MB" },
  { id: "m3", name: "五年高考三年模拟·数学.pdf", size: "45.2 MB" },
  { id: "m4", name: "高中数学公式大全.pdf", size: "3.1 MB" },
  { id: "m5", name: "数学错题集·上学期.docx", size: "2.3 MB" },
  { id: "m6", name: "高考数学真题汇编 2019-2025.pdf", size: "28.7 MB" },
];

/* ── 步骤 1：建立学习档案 ── */

export function BuildProfilePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { addItem, setSessionId, sessionId } = useCourseCreation();

  const isAdjust = searchParams.get("adjust") === "true";
  const [stepIndex, setStepIndex] = useState(0);
  const [inputValue, setInputValue] = useState("");
  const [selectedChoices, setSelectedChoices] = useState<Record<number, Set<string>>>({});
  const [selectedMaterials, setSelectedMaterials] = useState<Set<string>>(() => new Set());

  /* ── 上传弹窗 ── */
  const [showUpload, setShowUpload] = useState(false);
  const [uploadDragOver, setUploadDragOver] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const step = SUB_STEPS[stepIndex];
  const isLastStep = stepIndex === SUB_STEPS.length - 1;

  /* ── 按钮可用性 ── */
  const isStep1 = stepIndex === 0;

  /** 右侧"继续完善档案"按钮是否可用 */
  const canProceed = (() => {
    switch (step.type) {
      case "input":
        return inputValue.trim().length > 0;
      case "choice":
        return (selectedChoices[stepIndex]?.size ?? 0) > 0;
      case "materials":
        return true; // 资料可什么都不选
    }
  })();

  /** 左侧"生成学习方案"按钮是否可用 — 第 1 步始终不可用，调整模式除外 */
  const canGenerate = isAdjust ? canProceed : (isStep1 ? false : canProceed);

  /* ── 创建会话并跳转方案页 ── */
  async function goToPlan() {
    if (!sessionId) {
      try {
        const goal = inputValue.trim() || sessionStorage.getItem("mentora-course-goal") || "待完善的学习目标";
        const session = await createCourseSession(goal);
        sessionStorage.setItem("mentora-session-id", session.id);
        setSessionId(session.id);
        addItem({ key: "goal", title: "学习目标", value: goal, source: "AI 对话" });
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "创建会话失败";
        alert(msg);
        return;
      }
    }
    navigate("/courses/new/plan");
  }

  /* ── 继续完善档案 → 进入下一步或跳转方案 ── */
  function handleContinue() {
    if (isLastStep) {
      goToPlan();
    } else {
      setStepIndex((i) => i + 1);
    }
  }

  /* ── 资料选择 toggle ── */
  function toggleMaterial(id: string) {
    setSelectedMaterials((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  /* ── 上传资料 ── */
  function pickFile() {
    fileInputRef.current?.click();
  }

  async function handleUploadFile(file: File) {
    setUploadProgress({ step: "create", message: "正在创建上传会话…" });
    try {
      await uploadFile(file, (p) => setUploadProgress(p));
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

  /* ── 选项 toggle ── */
  function toggleChoice(option: string) {
    setSelectedChoices((prev) => {
      const existing = prev[stepIndex] ?? new Set<string>();
      const next = new Set(existing);
      if (next.has(option)) next.delete(option);
      else next.add(option);
      return { ...prev, [stepIndex]: next };
    });
  }

  function isChoiceSelected(option: string) {
    return selectedChoices[stepIndex]?.has(option) ?? false;
  }

  /* ── 渲染内容区 ── */
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

      case "choice":
        return (
          <div className="bp-choice-grid">
            {step.options!.map((opt) => {
              const sel = isChoiceSelected(opt);
              return (
                <button
                  key={opt}
                  className={`bp-choice-chip${sel ? " selected" : ""}`}
                  onClick={() => toggleChoice(opt)}
                  type="button"
                >
                  {opt}
                </button>
              );
            })}
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
            {MOCK_MATERIALS.map((m) => {
              const checked = selectedMaterials.has(m.id);
              return (
                <button
                  key={m.id}
                  className={`material-row${checked ? " selected" : ""}`}
                  onClick={() => toggleMaterial(m.id)}
                  type="button"
                >
                  <div className="material-row-left">
                    <FolderOpen size={16} />
                    <span className="material-name">{m.name}</span>
                    <span className="bp-material-size">{m.size}</span>
                  </div>
                  <div className={`material-check${checked ? " selected" : ""}`}>
                    {checked ? <Check size={14} /> : <Circle size={18} />}
                  </div>
                </button>
              );
            })}
          </div>
        );
    }
  }

  return (
    <SetupShell
      current={1}
      footer={
        isAdjust ? (
          /* 调整模式：始终双按钮 */
          <div className="build-profile-actions">
            <button
              className="button primary"
              disabled={!canProceed}
              onClick={goToPlan}
              type="button"
            >
              确认并生成学习方案
            </button>
            <button
              className="button secondary"
              disabled={!canProceed}
              onClick={handleContinue}
              type="button"
            >
              确认并继续完善档案
            </button>
          </div>
        ) : isLastStep ? (
          <div className="build-profile-actions build-profile-actions--single">
            <button
              className="button primary"
              disabled={!canProceed}
              onClick={goToPlan}
              type="button"
            >
              确认并生成学习方案
            </button>
          </div>
        ) : (
          <div className="build-profile-actions">
            <button
              className="button primary"
              disabled={!canGenerate}
              onClick={goToPlan}
              type="button"
            >
              确认并生成学习方案
            </button>
            <button
              className="button secondary"
              disabled={!canProceed}
              onClick={handleContinue}
              type="button"
            >
              确认并继续完善档案
            </button>
          </div>
        )
      }
    >
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
