import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, Circle, FolderOpen, Loader, Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { SetupShell } from "../components/AppShell";
import { useCourseCreation } from "../components/CourseCreationContext";
import { createCourseSession, updateCourseSession } from "../services/courseApi";
import {
  fetchSources,
  getCourseSources,
  setCourseSources,
  type SourceItem as ApiSource,
} from "../services/documentApi";
import { uploadFile } from "../services/uploadService";

/* ── 步骤 1：描述目标 ── */

export function DescribeGoalPage() {
  const navigate = useNavigate();
  const { addItem, setSessionId } = useCourseCreation();
  const savedGoal = sessionStorage.getItem("mentora-course-goal") || "";
  const [goal, setGoal] = useState(savedGoal);
  const [submitting, setSubmitting] = useState(false);
  const canContinue = goal.trim().length >= 4;

  useEffect(() => {
    if (savedGoal) {
      addItem({ key: "goal", title: "学习目标", value: savedGoal, source: "你的输入" });
    }
  }, []);

  async function submitGoal(event: React.FormEvent) {
    event.preventDefault();
    if (!canContinue || submitting) return;
    const value = goal.trim();
    setSubmitting(true);

    try {
      const session = await createCourseSession(value);
      sessionStorage.setItem("mentora-course-goal", value);
      sessionStorage.setItem("mentora-session-id", session.id);
      setSessionId(session.id);
      addItem({ key: "goal", title: "学习目标", value, source: "你的输入" });
      navigate("/courses/new/info");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "创建会话失败";
      alert(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <SetupShell
      current={1}
      footer={
        <div className="setup-footer" style={{ justifyContent: "flex-end" }}>
          <button className="button primary" disabled={!canContinue || submitting} form="goal-form" type="submit">
            {submitting ? "创建中…" : "下一步"}
          </button>
        </div>
      }
    >
      <form className="goal-form" id="goal-form" onSubmit={submitGoal}>
        <div className="setup-heading">
          <h1>你现在想学什么？</h1>
          <p>尽量描述你的学习目标、应用场景，以及希望达到的能力。</p>
        </div>
        <label className="goal-input">
          <textarea
            autoFocus
            maxLength={1000}
            onChange={(event) => setGoal(event.target.value)}
            placeholder="例如：两周后要考计算机组成原理，目前只了解一些基础，希望重点复习存储系统、指令系统和 CPU。"
            value={goal}
          />
          <span>{goal.length} / 1000</span>
        </label>
        <div className="example-prompts">
          <button type="button" onClick={() => setGoal("两周后要考计算机组成原理，希望完成重点复习。")}>
            准备一场考试
          </button>
          <button type="button" onClick={() => setGoal("我想系统学习机器学习，建立完整的基础知识框架。")}>
            系统学习一个领域
          </button>
          <button type="button" onClick={() => setGoal("我想通过一个数据分析项目学习 Python。")}>
            完成一个项目
          </button>
        </div>
      </form>
    </SetupShell>
  );
}

/* ── 步骤 2：补充信息 ── */

const levelOptions = [
  { id: "beginner", title: "完全新手", description: "几乎没有接触过" },
  { id: "basic", title: "了解基础", description: "知道一些概念和术语" },
  { id: "studied", title: "学过一遍", description: "需要梳理和巩固" },
  { id: "uncertain", title: "不太确定", description: "可以先由系统诊断" },
  { id: "other", title: "其他", description: "自定义输入" },
];

const paceOptions = [
  { id: "intensive", title: "集中多学", description: "有时间时连续学习多个任务" },
  { id: "short", title: "短时间推进", description: "每天少量时间" },
  { id: "steady", title: "相对稳定", description: "每天有固定时间投入" },
  { id: "flexible", title: "灵活", description: "保持灵活，后续再调整" },
  { id: "other", title: "其他", description: "自定义输入" },
];

const timeBudgetOptions = [
  { id: "batch", title: "集中投入", description: "有空时可以连续学很久" },
  { id: "daily_short", title: "每天少量", description: "每天 30 分钟左右" },
  { id: "daily_medium", title: "每天中等", description: "每天 1–2 小时" },
  { id: "daily_long", title: "每天较多", description: "每天 3 小时以上" },
  { id: "flexible", title: "灵活安排", description: "看情况，不固定" },
  { id: "other", title: "其他", description: "自定义输入" },
];

function choiceLabel(options: typeof levelOptions, id: string) {
  const opt = options.find((o) => o.id === id);
  return opt?.title ?? id;
}

export function AddInfoPage() {
  const navigate = useNavigate();
  const { addItem, sessionId } = useCourseCreation();
  const storedGoal = sessionStorage.getItem("mentora-course-goal") || "";

  const [level, setLevel] = useState("");
  const [pace, setPace] = useState("");
  const [timeBudget, setTimeBudget] = useState("");
  const [school, setSchool] = useState("华中科技大学");

  // 自定义输入
  const [levelCustom, setLevelCustom] = useState("");
  const [paceCustom, setPaceCustom] = useState("");
  const [budgetCustom, setBudgetCustom] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [validationError, setValidationError] = useState(false);
  const errorTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (storedGoal) addItem({ key: "goal", title: "学习目标", value: storedGoal, source: "你的输入" });
  }, []);

  // 选择任意选项时清除错误提示
  function selectLevel(id: string) { setLevel(id); setValidationError(false); }
  function selectPace(id: string) { setPace(id); setValidationError(false); }
  function selectBudget(id: string) { setTimeBudget(id); setValidationError(false); }
  function changeSchool(v: string) { setSchool(v); setValidationError(false); }

  async function submit() {
    if (submitting) return;

    const levLabel = level === "other" ? levelCustom.trim()
      : choiceLabel(levelOptions, level);
    const paceLabel = pace === "other" ? paceCustom.trim()
      : choiceLabel(paceOptions, pace);
    const budgetLabel = timeBudget === "other" ? budgetCustom.trim()
      : choiceLabel(timeBudgetOptions, timeBudget);

    if (!levLabel || !paceLabel || !budgetLabel || !school.trim()) {
      if (errorTimer.current) clearTimeout(errorTimer.current);
      setValidationError(true);
      errorTimer.current = setTimeout(() => setValidationError(false), 3000);
      return;
    }
    setSubmitting(true);

    sessionStorage.setItem("mentora-course-level", levLabel);
    sessionStorage.setItem("mentora-course-pace", paceLabel);
    sessionStorage.setItem("mentora-course-budget", budgetLabel || timeBudget);
    sessionStorage.setItem("mentora-course-school", school.trim());

    addItem({ key: "level", title: "当前基础", value: levLabel, source: "你的回答" });
    addItem({ key: "pace", title: "推进方式", value: paceLabel, source: "你的输入" });
    if (budgetLabel) {
      addItem({ key: "timeBudget", title: "时间分配", value: budgetLabel, source: "你的输入" });
    }
    if (school.trim()) {
      addItem({ key: "school", title: "学校", value: school.trim(), source: "你的输入" });
    }

    if (sessionId) {
      try {
        await updateCourseSession(sessionId, { level: levLabel, pace: paceLabel, school: school.trim() });
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "更新会话失败";
        alert(msg);
      }
    }

    setSubmitting(false);
    navigate("/courses/new/materials");
  }

  function renderChoiceGroup(
    options: typeof levelOptions,
    selected: string,
    onSelect: (id: string) => void,
    customValue: string,
    onCustomChange: (v: string) => void,
    showCustom: boolean,
  ) {
    return (
      <>
        <div className="choice-grid">
          {options.map((opt) => {
            const isOther = opt.id === "other";
            const isSelected = selected === opt.id;
            return (
              <button
                key={opt.id}
                aria-pressed={isSelected}
                className={isSelected ? "choice selected" : "choice"}
                onClick={() => onSelect(opt.id)}
                type="button"
              >
                <strong>{opt.title}</strong>
                <span>{isOther && showCustom && customValue ? customValue : opt.description}</span>
                <i>{isSelected ? <Check size={12} /> : null}</i>
              </button>
            );
          })}
        </div>
        {showCustom && selected === "other" && (
          <input
            className="choice-custom-input"
            onChange={(e) => onCustomChange(e.target.value)}
            placeholder="请输入自定义内容…"
            type="text"
            value={customValue}
          />
        )}
      </>
    );
  }

  return (
    <SetupShell
      current={2}
      footer={
        <div className="setup-footer">
          <button className="button secondary" onClick={() => navigate("/courses/new")} type="button">
            <ArrowLeft size={15} /> 上一步
          </button>
          {validationError && (
            <span className="footer-error">请填写全部信息后再进入下一步</span>
          )}
          <button
            className="button primary"
            disabled={submitting}
            onClick={() => { submit(); }}
            type="button"
          >
            {submitting ? "保存中…" : "下一步"}
          </button>
        </div>
      }
    >
      <div className="addinfo-page">
        <div className="setup-heading compact-heading">
          <h1>补充信息</h1>
          <p>以下信息帮助 AI 更准确地生成学习方案。</p>
        </div>

        <section className="info-block">
          <h2>当前基础</h2>
          {renderChoiceGroup(levelOptions, level, selectLevel, levelCustom, setLevelCustom, true)}
        </section>

        <section className="info-block">
          <h2>推进方式</h2>
          {renderChoiceGroup(paceOptions, pace, selectPace, paceCustom, setPaceCustom, true)}
        </section>

        <section className="info-block">
          <h2>时间分配</h2>
          <p className="info-desc">预计每天能投入多少时间学习？</p>
          {renderChoiceGroup(timeBudgetOptions, timeBudget, selectBudget, budgetCustom, setBudgetCustom, true)}
        </section>

        <section className="info-block">
          <h2>学校</h2>
          <p className="info-desc">填写所在学校，帮助 AI 了解你的学习背景。</p>
          <input
            className="school-input"
            onChange={(e) => changeSchool(e.target.value)}
            placeholder="请输入学校名称"
            type="text"
            value={school}
          />
        </section>
      </div>
    </SetupShell>
  );
}

/* ── 步骤 3：资料上传 ── */

const ACCEPTED_TYPES = ".pdf,.docx,.pptx,.xlsx,.png,.jpg,.jpeg";

/** 格式化字节数为可读大小。 */
/** 构建 AI 资料推荐提示词。 */
function buildMaterialPrompt(
  sources: ApiSource[],
  goal: string,
  level: string,
  pace: string,
  timeBudget: string,
  school: string,
): string {
  const fileLines = sources.map((s) => {
    const v = s.latestVersion!;
    return `- ${v.id} 《${s.displayTitle || v.originalFilename}》`;
  }).join("\n");

  const parts: string[] = [];
  if (level) parts.push(`当前基础：${level}`);
  if (pace) parts.push(`推进方式：${pace}`);
  if (timeBudget) parts.push(`时间分配：${timeBudget}`);
  if (school) parts.push(`学校：${school}`);
  const profile = parts.length > 0 ? parts.join("；") : "未知";

  return `你是 Mentora 智能学习平台的课程资料筛选助手。你的任务是根据课程目标和学习者的画像信息，为课程选出所有可能相关的学习资料。

【课程目标】
${goal || "未填写"}

【学习者画像】
${profile}

学习者正在创建一门课程，处于资料收集阶段。你的推荐将直接决定哪些资料被纳入学习方案，帮助学习者高效达成目标。请尽量全面挑出可能有用的资料。

【选材原则】
- 明显相关的资料：必选。
- 名称模糊但可能相关：选。宁可多选让学习者自己调整，也不要漏掉。
- 教材、笔记、讲义类：通常都相关。
- 习题、试卷类：如果课程目标涉及练习或考试，应该选。
- 只有明显不相关的才不选（例如完全不同的学科领域）。
- 如果无法判断，默认选上。

【可用资料】
${fileLines}

请只返回推荐资料的版本ID，每行一个（完整 UUID，不加序号、不加解释），例如：
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy

如果没有任何资料，不返回任何ID。不要加任何说明文字。`;
}

/** 从 AI 回复文本中提取匹配的资料版本 ID。 */
function parseRecommendedIds(reply: string, sources: ApiSource[]): string[] {
  const validIds = new Set(sources.map((s) => s.latestVersion!.id));
  // 尝试匹配 UUID 格式
  const uuidRe = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;
  const found = reply.match(uuidRe) ?? [];
  // 只保留在资料列表中实际存在的 ID
  return [...new Set(found.filter((id) => validIds.has(id)))];
}

function fmtSize(bytes?: number): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function MaterialUploadPage() {
  const navigate = useNavigate();
  const { addItem, sessionId } = useCourseCreation();

  const [sources, setSources] = useState<ApiSource[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [phase, setPhase] = useState<"loading" | "analyzing" | "ready">("loading");
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [saving, setSaving] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // 拉取资料 → AI 初筛推荐 → 展示列表
  useEffect(() => {
    setPhase("loading");

    fetchSources()
      .then(async (items) => {
        const completed = items.filter(
          (s) => s.latestVersion?.processingStatus === "completed",
        );
        setSources(completed);

        if (completed.length === 0) {
          setPhase("ready");
          return;
        }

        // 如果已有关联，直接恢复勾选，跳过 AI 分析
        if (sessionId) {
          try {
            const linked = await getCourseSources(sessionId);
            if (linked.length > 0) {
              setSelectedIds(new Set(linked.map((l) => l.sourceVersionId)));
              setPhase("ready");
              return;
            }
          } catch { /* 忽略 */ }
        }

        // 没有历史关联 → AI 初筛
        if (!sessionId) {
          setPhase("ready");
          return;
        }

        setPhase("analyzing");

        try {
          const goal = sessionStorage.getItem("mentora-course-goal") || "";
          const level = sessionStorage.getItem("mentora-course-level") || "";
          const pace = sessionStorage.getItem("mentora-course-pace") || "";
          const budget = sessionStorage.getItem("mentora-course-budget") || "";
          const school = sessionStorage.getItem("mentora-course-school") || "";
          const prompt = buildMaterialPrompt(completed, goal, level, pace, budget, school);
          const resp = await fetch("/api/chat/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ message: prompt }),
          });
          if (resp.ok) {
            const data = await resp.json();
            const aiIds = parseRecommendedIds(data.reply || "", completed);
            if (aiIds.length > 0) {
              setSelectedIds(new Set(aiIds));
            }
          }
        } catch {
          // AI 失败不阻塞，列表照常展示
        }

        setPhase("ready");
      })
      .catch(() => {
        setPhase("ready");
      });
  }, [sessionId]);

  const toggle = useCallback((versionId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(versionId)) next.delete(versionId);
      else next.add(versionId);
      return next;
    });
  }, []);

  // 上传新文件
  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg("正在上传…");
    try {
      const result = await uploadFile(file, (p) => setUploadMsg(p.message));
      setUploadMsg("上传完成，正在解析…");
      // 短暂等待解析完成
      await new Promise((r) => setTimeout(r, 2000));
      // 刷新列表
      const items = await fetchSources();
      const completed = items.filter(
        (s) => s.latestVersion?.processingStatus === "completed",
      );
      setSources(completed);
      // 自动选中新上传的文件
      if (result.sourceVersionId) {
        setSelectedIds((prev) => new Set(prev).add(result.sourceVersionId));
      }
      setUploadMsg("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "上传失败";
      setUploadMsg(msg);
    } finally {
      setUploading(false);
    }
    // 重置 input 以便重复上传同一文件
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  // 保存关联并继续
  async function handleSave() {
    setSaving(true);
    const versionIds = [...selectedIds];
    if (sessionId && versionIds.length > 0) {
      try {
        await setCourseSources(sessionId, versionIds);
      } catch {
        // 保存失败不阻塞
      }
    }
    addItem({
      key: "sources",
      title: "参考资料",
      value: `${versionIds.length} 份文件`,
      source: "资料上传",
    });
    setSaving(false);
    navigate("/courses/new/inquiry");
  }

  function skip() {
    navigate("/courses/new/inquiry");
  }

  /* ── render ── */

  return (
    <SetupShell
      current={3}
      footer={
        <div className="setup-footer">
          <button className="button secondary" onClick={() => navigate("/courses/new/info")} type="button">
            <ArrowLeft size={15} /> 上一步
          </button>
          <div className="footer-buttons">
            <button className="button secondary" onClick={skip} type="button">
              跳过
            </button>
            <button className="button primary" onClick={handleSave} disabled={saving} type="button">
              {saving ? "保存中…" : "上传并继续"}
            </button>
          </div>
        </div>
      }
    >
      <div className="addinfo-page">
        <div className="setup-heading compact-heading">
          <h1>资料上传</h1>
          <p>选择已有的学习资料，或上传新文件，AI 会解读内容并生成更精准的学习方案。</p>
        </div>

        <section className="info-block">
          <div className="material-toolbar">
            <h2>可选资料</h2>
            <div className="material-toolbar-actions">
              <span className="material-count">
                已选 <strong>{selectedIds.size}</strong> 份
              </span>
              {/* 隐藏的文件选择器 */}
              <input
                ref={fileInputRef}
                accept={ACCEPTED_TYPES}
                className="material-hidden-input"
                onChange={handleFileChange}
                type="file"
              />
              <button
                className="button secondary small"
                disabled={uploading || phase === "analyzing"}
                onClick={() => fileInputRef.current?.click()}
                type="button"
              >
                {uploading ? <Loader size={14} className="spin-icon" /> : <Upload size={14} />}
                上传新文件
              </button>
            </div>
          </div>

          {uploadMsg && <p className="material-upload-msg">{uploadMsg}</p>}

          {phase === "loading" ? (
            <p className="info-desc">加载资料中…</p>
          ) : phase === "analyzing" ? (
            <div className="material-analyzing">
              <Loader size={18} className="spin-icon" />
              <span>AI 正在根据课程目标筛选资料…</span>
            </div>
          ) : sources.length === 0 ? (
            <p className="info-desc">资源库中没有已解析完成的文件，请先上传。</p>
          ) : (
            <div className="material-list">
              {sources.map((src) => {
                const v = src.latestVersion!;
                const vid = v.id;
                const checked = selectedIds.has(vid);
                return (
                  <button
                    key={vid}
                    className={`material-row${checked ? " selected" : ""}`}
                    onClick={() => toggle(vid)}
                    type="button"
                  >
                    <div className="material-row-left">
                      <FolderOpen size={16} />
                      <span className="material-name">{src.displayTitle || v.originalFilename}</span>
                      <span className="material-size">{fmtSize(v.byteSize)}</span>
                    </div>
                    <div className={`material-check${checked ? " selected" : ""}`}>
                      {checked ? <Check size={14} /> : <Circle size={18} />}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </SetupShell>
  );
}
