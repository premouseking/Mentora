import { useEffect, useState } from "react";
import { ArrowLeft, Check, FolderOpen, Link as LinkIcon, Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { SetupShell } from "../components/AppShell";
import { useCourseCreation } from "../components/CourseCreationContext";

/* ── 步骤 1：描述目标 ── */

export function DescribeGoalPage() {
  const navigate = useNavigate();
  const { addItem } = useCourseCreation();
  const savedGoal = sessionStorage.getItem("mentora-course-goal") || "";
  const [goal, setGoal] = useState(savedGoal);
  const canContinue = goal.trim().length >= 4;

  useEffect(() => {
    if (savedGoal) {
      addItem({ key: "goal", title: "学习目标", value: savedGoal, source: "你的输入" });
    }
  }, []);

  function submitGoal(event: React.FormEvent) {
    event.preventDefault();
    if (!canContinue) return;
    const value = goal.trim();
    sessionStorage.setItem("mentora-course-goal", value);
    addItem({ key: "goal", title: "学习目标", value, source: "你的输入" });
    navigate("/courses/new/info");
  }

  return (
    <SetupShell
      current={1}
      footer={
        <div className="setup-footer" style={{ justifyContent: "flex-end" }}>
          <button className="button primary" disabled={!canContinue} form="goal-form" type="submit">下一步</button>
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
];

const paceOptions = [
  { id: "intensive", title: "集中多学", description: "有时间时可以连续学习多个任务" },
  { id: "short", title: "短时间推进", description: "每天只能抽少量时间学习" },
  { id: "steady", title: "相对稳定", description: "每天有固定时间投入" },
  { id: "uncertain", title: "暂不确定", description: "保持灵活，后续再调整" },
];

type SourceItem = {
  id: string;
  name: string;
  type: "PDF" | "DOCX" | "LINK" | "OFFICIAL";
  purpose: string;
};

function readSources(): SourceItem[] {
  const stored = sessionStorage.getItem("mentora-course-sources-info");
  if (!stored) return [];
  try { return JSON.parse(stored) as SourceItem[]; } catch { return []; }
}

export function AddInfoPage() {
  const navigate = useNavigate();
  const { addItem } = useCourseCreation();
  const storedGoal = sessionStorage.getItem("mentora-course-goal") || "";
  const savedLevel = sessionStorage.getItem("mentora-course-level") || "basic";
  const savedPace = sessionStorage.getItem("mentora-course-pace") || "intensive";

  const [level, setLevel] = useState(savedLevel);
  const [pace, setPace] = useState(savedPace);
  const [sources] = useState<SourceItem[]>(readSources);

  useEffect(() => {
    if (storedGoal) addItem({ key: "goal", title: "学习目标", value: storedGoal, source: "你的输入" });
  }, []);

  function submit() {
    const lev = levelOptions.find((o) => o.id === level);
    const pc = paceOptions.find((o) => o.id === pace);
    if (!lev || !pc) return;
    sessionStorage.setItem("mentora-course-level", lev.title);
    sessionStorage.setItem("mentora-course-pace", pc.title);
    addItem({ key: "level", title: "当前基础", value: lev.title, source: "你的回答" });
    addItem({ key: "pace", title: "推进方式", value: pc.title, source: "你的输入" });
    if (sources.length > 0) {
      addItem({ key: "sources", title: "课程资料", value: `${sources.length} 项`, source: "资料选择" });
    }
    navigate("/courses/new/materials");
  }

  return (
    <SetupShell
      current={2}
      footer={
        <div className="setup-footer">
          <button className="button secondary" onClick={() => navigate("/courses/new")} type="button">
            <ArrowLeft size={15} /> 上一步
          </button>
          <button
            className="button primary"
            onClick={() => {
              try {
                submit();
              } catch (e) {
                alert("错误: " + String(e));
              }
            }}
            type="button"
          >
            下一步
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
          <div className="choice-grid">
            {levelOptions.map((opt) => (
              <button
                key={opt.id}
                aria-pressed={level === opt.id}
                className={level === opt.id ? "choice selected" : "choice"}
                onClick={() => setLevel(opt.id)}
                type="button"
              >
                <strong>{opt.title}</strong>
                <span>{opt.description}</span>
                <i>{level === opt.id ? <Check size={14} /> : null}</i>
              </button>
            ))}
          </div>
        </section>

        <section className="info-block">
          <h2>推进方式</h2>
          <div className="choice-grid">
            {paceOptions.map((opt) => (
              <button
                key={opt.id}
                aria-pressed={pace === opt.id}
                className={pace === opt.id ? "choice selected" : "choice"}
                onClick={() => setPace(opt.id)}
                type="button"
              >
                <strong>{opt.title}</strong>
                <span>{opt.description}</span>
                <i>{pace === opt.id ? <Check size={14} /> : null}</i>
              </button>
            ))}
          </div>
        </section>
      </div>
    </SetupShell>
  );
}

/* ── 步骤 3：资料上传 ── */

export function MaterialUploadPage() {
  const navigate = useNavigate();
  const { addItem } = useCourseCreation();

  function skip() {
    navigate("/courses/new/inquiry");
  }

  function handleUpload() {
    // TODO: 实际上传逻辑，接入 AI 解读
    addItem({ key: "sources", title: "参考资料", value: "已上传", source: "资料上传" });
    navigate("/courses/new/inquiry");
  }

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
            <button className="button primary" onClick={handleUpload} type="button">
              上传并继续
            </button>
          </div>
        </div>
      }
    >
      <div className="addinfo-page">
        <div className="setup-heading compact-heading">
          <h1>资料上传</h1>
          <p>上传学习资料，AI 会解读内容并生成更精准的学习方案。</p>
        </div>

        <section className="info-block">
          <h2>添加资料</h2>
          <p className="info-desc">支持 PDF、Word、图片等格式，可同时上传多个文件。</p>
          <div className="source-quick-actions">
            <button className="source-quick-btn" type="button">
              <FolderOpen size={18} /> 从资源库选择
            </button>
            <button className="source-quick-btn" type="button">
              <Upload size={18} /> 上传文件
            </button>
            <button className="source-quick-btn" type="button">
              <LinkIcon size={18} /> 添加链接
            </button>
          </div>
        </section>
      </div>
    </SetupShell>
  );
}
