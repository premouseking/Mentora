import { useMemo, useState } from "react";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Check,
  ChevronRight,
  CircleCheck,
  Clock3,
  File,
  FileText,
  FolderOpen,
  Link as LinkIcon,
  ListTree,
  LockKeyhole,
  Sparkles,
  Target,
  Upload,
  UserRound,
  X,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { SetupShell } from "../components/AppShell";

type SourceItem = {
  id: string;
  name: string;
  type: "PDF" | "DOCX" | "LINK" | "OFFICIAL";
  size?: string;
  purpose: string;
  state: "ready" | "processing";
};

const initialSources: SourceItem[] = [
  {
    id: "textbook",
    name: "计算机组成原理（第 6 版）.pdf",
    type: "PDF",
    size: "23.4 MB",
    purpose: "主要参考书",
    state: "ready",
  },
  {
    id: "class-notes",
    name: "计算机组成原理课堂笔记.docx",
    type: "DOCX",
    size: "1.8 MB",
    purpose: "课堂笔记",
    state: "processing",
  },
];

const libraryCandidates: SourceItem[] = [
  {
    id: "exam-outline",
    name: "期末考试范围与重点.pdf",
    type: "PDF",
    size: "860 KB",
    purpose: "考试范围",
    state: "ready",
  },
  {
    id: "cache-notes",
    name: "Cache 重点整理.md",
    type: "LINK",
    purpose: "重点补充",
    state: "ready",
  },
];

function readSources(): SourceItem[] {
  const stored = sessionStorage.getItem("mentora-course-sources");
  if (!stored) return initialSources;
  try {
    return JSON.parse(stored) as SourceItem[];
  } catch {
    return initialSources;
  }
}

function persistSources(sources: SourceItem[]) {
  sessionStorage.setItem("mentora-course-sources", JSON.stringify(sources));
}

function SourceTypeIcon({ type }: { type: SourceItem["type"] }) {
  if (type === "OFFICIAL") return <BookOpen size={19} />;
  if (type === "LINK") return <LinkIcon size={19} />;
  return <FileText size={19} />;
}

export function SelectSourcesPage() {
  const navigate = useNavigate();
  const [sources, setSources] = useState<SourceItem[]>(readSources);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState("exam-outline");
  const [officialAdded, setOfficialAdded] = useState(
    sources.some((source) => source.type === "OFFICIAL"),
  );

  function updateSources(nextSources: SourceItem[]) {
    setSources(nextSources);
    persistSources(nextSources);
  }

  function addCandidate() {
    const candidate = libraryCandidates.find((item) => item.id === selectedCandidate);
    if (candidate && !sources.some((source) => source.id === candidate.id)) {
      updateSources([...sources, candidate]);
    }
    setPickerOpen(false);
  }

  function simulateUpload() {
    if (sources.some((source) => source.id === "uploaded-review")) return;
    updateSources([
      ...sources,
      {
        id: "uploaded-review",
        name: "老师划重点整理.pdf",
        type: "PDF",
        size: "2.1 MB",
        purpose: "考试范围",
        state: "processing",
      },
    ]);
  }

  function addLink() {
    if (sources.some((source) => source.id === "linked-video")) return;
    updateSources([
      ...sources,
      {
        id: "linked-video",
        name: "CPU 指令执行过程讲解",
        type: "LINK",
        purpose: "重点补充",
        state: "ready",
      },
    ]);
  }

  function toggleOfficial() {
    if (officialAdded) {
      const next = sources.filter((source) => source.type !== "OFFICIAL");
      updateSources(next);
      setOfficialAdded(false);
      return;
    }
    updateSources([
      ...sources,
      {
        id: "official-base",
        name: "计算机组成原理 · 官方基础资源",
        type: "OFFICIAL",
        purpose: "基础讲解",
        state: "ready",
      },
    ]);
    setOfficialAdded(true);
  }

  function continueToProfile() {
    persistSources(sources);
    navigate("/courses/new/profile");
  }

  return (
    <SetupShell current={3}>
      <div className="sources-page">
        <div className="setup-heading compact-heading">
          <h1>添加资料 <span>（可选）</span></h1>
          <p>资料可以帮助 AI 更好地理解学习范围，但没有资料也能继续。</p>
        </div>

        <div className="source-actions">
          <button type="button" onClick={() => setPickerOpen(true)}>
            <FolderOpen size={27} />
            <strong>从资源库选择</strong>
            <span>从已有资料中筛选</span>
          </button>
          <button type="button" onClick={simulateUpload}>
            <Upload size={27} />
            <strong>上传本地文件</strong>
            <span>支持 PDF、DOCX、PPTX</span>
          </button>
          <button type="button" onClick={addLink}>
            <LinkIcon size={27} />
            <strong>添加链接</strong>
            <span>添加网页或教学视频</span>
          </button>
        </div>

        {pickerOpen ? (
          <section className="source-picker" aria-label="从资源库选择资料">
            <div className="source-picker-head">
              <div>
                <strong>从资源库选择</strong>
                <span>选择一项加入当前课程</span>
              </div>
              <button aria-label="关闭资料选择" onClick={() => setPickerOpen(false)} type="button">
                <X size={18} />
              </button>
            </div>
            <div className="candidate-list">
              {libraryCandidates.map((candidate) => (
                <button
                  aria-pressed={selectedCandidate === candidate.id}
                  className={selectedCandidate === candidate.id ? "selected" : ""}
                  key={candidate.id}
                  onClick={() => setSelectedCandidate(candidate.id)}
                  type="button"
                >
                  <SourceTypeIcon type={candidate.type} />
                  <span>
                    <strong>{candidate.name}</strong>
                    <small>{candidate.purpose} · {candidate.size ?? "链接"}</small>
                  </span>
                  <i>{selectedCandidate === candidate.id ? <Check size={13} /> : null}</i>
                </button>
              ))}
            </div>
            <div className="picker-footer">
              <button className="button secondary" onClick={() => setPickerOpen(false)} type="button">
                取消
              </button>
              <button className="button primary" onClick={addCandidate} type="button">
                添加到课程
              </button>
            </div>
          </section>
        ) : null}

        <section className="selected-sources">
          <div className="section-heading-row">
            <h2>已选择的资料</h2>
            <span>{sources.length} 项</span>
          </div>
          <div className="source-list">
            {sources.length === 0 ? (
              <div className="source-list-empty">暂未添加资料，你仍然可以继续确认学习需求。</div>
            ) : (
              sources.map((source) => (
                <div className="source-row" key={source.id}>
                  <span className={`source-type ${source.type.toLowerCase()}`}>
                    <SourceTypeIcon type={source.type} />
                    <small>{source.type}</small>
                  </span>
                  <div className="source-name">
                    <strong>{source.name}</strong>
                    <span>{source.size ?? "平台资源"}</span>
                  </div>
                  <span className="source-purpose">{source.purpose}</span>
                  <span className={`source-state ${source.state}`}>
                    {source.state === "ready" ? (
                      <>
                        <CircleCheck size={16} />
                        已就绪
                      </>
                    ) : (
                      <>
                        <span className="processing-dot" />
                        解析中
                        <small>约 1 分钟</small>
                      </>
                    )}
                  </span>
                  <button
                    aria-label={`移除${source.name}`}
                    className="remove-source"
                    onClick={() => updateSources(sources.filter((item) => item.id !== source.id))}
                    type="button"
                  >
                    <X size={17} />
                  </button>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="official-source">
          <div>
            <span className="official-icon"><BookOpen size={20} /></span>
            <div>
              <strong>计算机组成原理 · 官方基础资源</strong>
              <span>包含核心概念、常见考点和基础练习</span>
            </div>
          </div>
          <span className="official-state">{officialAdded ? "已加入课程" : "尚未添加"}</span>
          <button className="button secondary compact" onClick={toggleOfficial} type="button">
            {officialAdded ? "移除" : "添加"}
          </button>
        </section>

        <div className="sources-footer">
          <button className="button secondary" onClick={() => {
            updateSources([]);
            setOfficialAdded(false);
          }} type="button">
            暂不添加
          </button>
          <button className="button primary" onClick={continueToProfile} type="button">
            继续确认学习需求
          </button>
        </div>
        <p className="privacy-note"><LockKeyhole size={13} /> 资料仅用于本课程学习。</p>
      </div>
    </SetupShell>
  );
}

type ProfileKey = "goal" | "level" | "pace" | "focus" | "sources" | "suggestion";

const profileMeta: Array<{
  key: ProfileKey;
  title: string;
  icon: typeof Target;
  source: string;
}> = [
  { key: "goal", title: "学习目标", icon: Target, source: "你的输入" },
  { key: "level", title: "当前基础", icon: UserRound, source: "你的回答" },
  { key: "pace", title: "推进方式", icon: Clock3, source: "你的输入" },
  { key: "focus", title: "学习重点", icon: Sparkles, source: "资料识别" },
  { key: "sources", title: "课程资料", icon: File, source: "资料选择" },
  { key: "suggestion", title: "系统建议", icon: Sparkles, source: "AI 建议" },
];

export function ConfirmProfilePage() {
  const navigate = useNavigate();
  const sources = readSources();
  const [editing, setEditing] = useState<ProfileKey | null>(null);
  const [profile, setProfile] = useState({
    goal: sessionStorage.getItem("mentora-course-goal") || "两周后完成计算机组成原理重点复习",
    level: sessionStorage.getItem("mentora-course-level") || "了解基础",
    pace: "按阶段推进，有时间时可以连续学习多个任务",
    focus: "存储系统、指令系统、CPU 组成与工作原理",
    sources: `${sources.length} 项资料，其中 ${sources.filter((source) => source.state === "processing").length} 项仍在解析`,
    suggestion: "建议分为 4 个阶段，从基础梳理开始，并根据检查结果动态加快",
  });

  function editValue(key: ProfileKey, value: string) {
    setProfile((current) => ({ ...current, [key]: value }));
    setEditing(null);
  }

  function generatePlan() {
    sessionStorage.setItem("mentora-course-profile", JSON.stringify(profile));
    navigate("/courses/new/plan");
  }

  return (
    <SetupShell current={4}>
      <div className="profile-page">
        <div className="setup-heading compact-heading">
          <h1>确认学习需求</h1>
          <p>请确认或补充以下信息，AI 将基于这些事实生成学习方案。</p>
        </div>

        <div className="profile-summary-list">
          {profileMeta.map(({ key, title, icon: Icon, source }) => (
            <section className={`profile-summary-row ${key === "suggestion" ? "suggested" : ""}`} key={key}>
              <Icon size={23} />
              <div className="profile-copy">
                <div>
                  <h2>{title}</h2>
                  <span>来源：{source}</span>
                </div>
                {editing === key ? (
                  <div className="inline-editor">
                    <input
                      autoFocus
                      defaultValue={profile[key]}
                      onKeyDown={(event) => {
                        if (event.key === "Enter") {
                          editValue(key, event.currentTarget.value);
                        }
                      }}
                    />
                    <button
                      onClick={(event) => {
                        const input = event.currentTarget.previousElementSibling as HTMLInputElement;
                        editValue(key, input.value);
                      }}
                      type="button"
                    >
                      保存
                    </button>
                  </div>
                ) : (
                  <p>{profile[key]}</p>
                )}
              </div>
              <button className="modify-button" onClick={() => setEditing(key)} type="button">
                修改 <ChevronRight size={15} />
              </button>
            </section>
          ))}
        </div>

        <div className="profile-footer">
          <button className="button secondary" onClick={() => navigate("/courses/new/sources")} type="button">
            <ArrowLeft size={17} />
            返回修改资料
          </button>
          <button className="button primary" onClick={generatePlan} type="button">
            <Sparkles size={17} />
            生成学习方案
          </button>
        </div>
        <p className="privacy-note"><LockKeyhole size={13} /> 以上内容可随时修改，方案生成后也可以继续调整。</p>
      </div>
    </SetupShell>
  );
}

type Phase = {
  id: string;
  name: string;
  goal: string;
  share: number;
  tasks: string[];
};

const initialPhases: Phase[] = [
  {
    id: "foundation",
    name: "基础梳理",
    goal: "建立完整知识框架，理解核心概念与基本原理。",
    share: 25,
    tasks: ["理解计算机系统的层次结构", "掌握数据的表示与运算", "理解指令系统与寻址方式", "理解存储系统的基本组成"],
  },
  {
    id: "focus",
    name: "重点突破",
    goal: "集中突破考试高频主题和当前薄弱环节。",
    share: 35,
    tasks: ["Cache 映射与替换策略", "CPU 数据通路", "指令流水线与相关冲突"],
  },
  {
    id: "application",
    name: "综合应用",
    goal: "通过综合问题建立跨主题联系。",
    share: 25,
    tasks: ["综合计算题", "跨章节概念辨析", "典型题型迁移练习"],
  },
  {
    id: "review",
    name: "检验巩固",
    goal: "检查掌握情况并安排针对性回顾。",
    share: 15,
    tasks: ["阶段检查", "错题回顾", "考前快速复盘"],
  },
];

export function ConfirmPlanPage() {
  const navigate = useNavigate();
  const [phases, setPhases] = useState(initialPhases);
  const [activePhaseId, setActivePhaseId] = useState(initialPhases[0].id);
  const activePhase = useMemo(
    () => phases.find((phase) => phase.id === activePhaseId) ?? phases[0],
    [activePhaseId, phases],
  );

  function adjustActivePhase(direction: "simplify" | "deepen") {
    setPhases((current) =>
      current.map((phase) => {
        if (phase.id !== activePhaseId) return phase;
        if (direction === "simplify") {
          return {
            ...phase,
            share: Math.max(10, phase.share - 5),
            tasks: phase.tasks.length > 2 ? phase.tasks.slice(0, -1) : phase.tasks,
          };
        }
        return {
          ...phase,
          share: Math.min(50, phase.share + 5),
          tasks: phase.tasks.includes("补充迁移练习") ? phase.tasks : [...phase.tasks, "补充迁移练习"],
        };
      }),
    );
  }

  function startCourse() {
    sessionStorage.setItem("mentora-course-started", "true");
    navigate("/courses");
  }

  return (
    <SetupShell current={5}>
      <div className="plan-page">
        <div className="setup-heading compact-heading">
          <h1>确认学习方案</h1>
          <p>AI 已根据你的需求生成阶段方案，请确认并按需调整。</p>
        </div>

        <section className="plan-goal">
          <Target size={24} />
          <div>
            <strong>学习目标</strong>
            <p>两周后完成计算机组成原理重点复习，掌握考试高频知识点。</p>
          </div>
          <button onClick={() => navigate("/courses/new/profile")} type="button">修改</button>
        </section>

        <div className="phase-heading">
          <h2>学习阶段 <span>（共 {phases.length} 个阶段）</span></h2>
          <small>阶段是主要结构，完成节奏可根据实际情况调整。</small>
        </div>

        <div className="phase-path">
          {phases.map((phase, index) => (
            <div className="phase-path-item" key={phase.id}>
              <button
                aria-pressed={phase.id === activePhaseId}
                className={phase.id === activePhaseId ? "active" : ""}
                onClick={() => setActivePhaseId(phase.id)}
                type="button"
              >
                <span>{index + 1}</span>
                {phase.name}
              </button>
              {index < phases.length - 1 ? <ArrowRight size={18} /> : null}
            </div>
          ))}
        </div>

        <section className="phase-detail">
          <div className="phase-detail-row">
            <span><Target size={18} /> 阶段目标</span>
            <p>{activePhase.goal}</p>
          </div>
          <div className="phase-detail-row">
            <span><ListTree size={18} /> 相对学习量</span>
            <div className="share-display">
              <strong>约占全部内容的 {activePhase.share}%</strong>
              <div>
                {[10, 20, 30, 40, 50, 60].map((threshold) => (
                  <i className={activePhase.share >= threshold ? "filled" : ""} key={threshold} />
                ))}
              </div>
            </div>
          </div>
          <div className="phase-detail-row task-detail">
            <span><FileText size={18} /> 代表性任务</span>
            <ul>
              {activePhase.tasks.slice(0, 5).map((task) => <li key={task}>{task}</li>)}
            </ul>
          </div>
          <div className="phase-operations">
            <span>本阶段操作</span>
            <button onClick={() => adjustActivePhase("simplify")} type="button">
              <ArrowDown size={16} /> 简化阶段
            </button>
            <button onClick={() => adjustActivePhase("deepen")} type="button">
              <ArrowUp size={16} /> 加强阶段
            </button>
            <button type="button">
              <ListTree size={16} /> 查看全部任务
            </button>
          </div>
        </section>

        <div className="plan-footer">
          <button className="button secondary" onClick={() => navigate("/courses/new/profile")} type="button">
            返回修改学习需求
          </button>
          <button className="button primary" onClick={startCourse} type="button">
            开始学习
          </button>
        </div>
        <p className="privacy-note"><LockKeyhole size={13} /> 开始后仍可调整阶段顺序、内容重点和学习节奏。</p>
      </div>
    </SetupShell>
  );
}
