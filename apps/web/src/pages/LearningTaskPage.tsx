import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ArrowLeft, BookOpen, Bot, Check, ChevronRight, Clock3,
  ExternalLink, Lightbulb, RefreshCw, Sparkles, X,
} from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { DesktopTitleBar } from "../components/DesktopTitleBar";
import { QuizPracticeView } from "../components/QuizPracticeView";
import { ReferenceEvidenceBlock } from "../components/ReferenceEvidenceBlock";
import { resolveTaskLearningMode } from "./courseFlowHelpers";
import { getCourseDetail } from "../services/courseApi";
import { fetchSources, sourcesToFileNodes } from "../services/documentApi";
import {
  completeLearningTask,
  fetchTask,
  type CalloutBlock,
  type CitationBlock,
  type ContentBlock,
  type DiagramBlock,
  type HeadingBlock,
  type LearningTaskDetail,
  type ParagraphBlock,
  type QuizBlock,
} from "../services/learningApi";
import type { FileNode } from "../data/files";

/* ── 辅助面板 ── */

type HelperPanel = "source" | "ai" | null;

/* ── 内容块渲染器 ── */

function BlockHeading({ block, active, onClick }: { block: HeadingBlock; active: boolean; onClick: () => void }) {
  const Tag = block.level === 2 ? "h2" : "h3";
  return <Tag id={block.id} className={active ? "active" : ""} onClick={onClick}>{block.label}</Tag>;
}

function BlockParagraph({ block, mode, onModeChange }: {
  block: ParagraphBlock;
  mode: "standard" | "simple" | "example";
  onModeChange: (m: "standard" | "simple" | "example") => void;
}) {
  const text = block.modes
    ? (block.modes[mode] ?? block.modes.standard)
    : block.text;

  return (
    <div className="paragraph-block">
      <p>{text}</p>
      {block.modes && (
        <div className="paragraph-modes">
          <button className={mode === "simple" ? "active" : ""} onClick={() => onModeChange("simple")} type="button">
            <RefreshCw size={14} /> 简单解释
          </button>
          <button className={mode === "example" ? "active" : ""} onClick={() => onModeChange("example")} type="button">
            <Lightbulb size={14} /> 举例说明
          </button>
          <button className={mode === "standard" ? "active" : ""} onClick={() => onModeChange("standard")} type="button">
            标准
          </button>
        </div>
      )}
    </div>
  );
}

function BlockCitation({ block, onOpenPanel }: { block: CitationBlock; onOpenPanel: () => void }) {
  return (
    <button className="source-citation" onClick={onOpenPanel} type="button">
      <span>来源：{block.source_title}{block.chapter ? ` · ${block.chapter}` : ""}</span>
      <strong>查看原文 <ExternalLink size={13} /></strong>
    </button>
  );
}

function BlockCallout({ block }: { block: CalloutBlock }) {
  const icon = block.variant === "tip" ? <Sparkles size={16} /> : <Lightbulb size={16} />;
  return (
    <div className={`callout-block callout-${block.variant}`}>
      {icon}
      <p>{block.text}</p>
    </div>
  );
}

function BlockQuiz({ block }: { block: QuizBlock }) {
  const [open, setOpen] = useState(false);
  const [answer, setAnswer] = useState<number | null>(null);

  return (
    <section className="quiz-block">
      {!open ? (
        <button className="quiz-open-btn" onClick={() => setOpen(true)} type="button">
          开始检查 <ChevronRight size={17} />
        </button>
      ) : (
        <div className="inline-check">
          <h3>{block.question}</h3>
          <div className="check-options">
            {block.options.map((opt, i) => (
              <button
                key={i}
                className={answer === i ? "selected" : ""}
                onClick={() => setAnswer(i)}
                type="button"
              >
                {opt}
              </button>
            ))}
          </div>
          {answer !== null && (
            <p className={answer === block.correct_index ? "correct" : "retry"}>
              {answer === block.correct_index
                ? `回答正确。${block.explanation}`
                : "再想一下。"}
            </p>
          )}
          {block.next_step_link && answer === block.correct_index && (
            <Link className="check-summary-link" to={block.next_step_link}>
              查看阶段总结 <ChevronRight size={16} />
            </Link>
          )}
        </div>
      )}
    </section>
  );
}

/* ── 主页面 ── */

export function LearningTaskPage() {
  const { courseId, taskId } = useParams<{ courseId: string; taskId: string }>();
  const navigate = useNavigate();

  const [task, setTask] = useState<LearningTaskDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [courseSessionId, setCourseSessionId] = useState<string | undefined>();
  const [fileNodes, setFileNodes] = useState<FileNode[]>([]);

  /* 切换段落解释模式 */
  const [paraMode, setParaMode] = useState<"standard" | "simple" | "example">("standard");

  /* 侧栏高亮 */
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const [helperPanel, setHelperPanel] = useState<HelperPanel>(null);
  const [citationSource, setCitationSource] = useState<CitationBlock | null>(null);

  useEffect(() => {
    if (!taskId) {
      setError("缺少任务 ID");
      setLoading(false);
      return;
    }

    let cancelled = false;
    fetchTask(taskId)
      .then((data) => { if (!cancelled) setTask(data); })
      .catch((err) => { if (!cancelled) setError(err instanceof Error ? err.message : "加载失败"); })
      .finally(() => { if (!cancelled) setLoading(false); });

    return () => { cancelled = true; };
  }, [taskId]);

  useEffect(() => {
    if (!courseId) return;
    let cancelled = false;
    getCourseDetail(courseId)
      .then((course) => {
        if (!cancelled) setCourseSessionId(course?.session_id || courseId);
      })
      .catch(() => {
        if (!cancelled) setCourseSessionId(courseId);
      });
    fetchSources(courseId)
      .then((items) => { if (!cancelled) setFileNodes(sourcesToFileNodes(items)); })
      .catch(() => { if (!cancelled) setFileNodes([]); });
    return () => { cancelled = true; };
  }, [courseId]);

  const learningMode = task ? resolveTaskLearningMode(task.task_type) : "content";
  const taskSourceVersionIds = useMemo(
    () => [...new Set(task?.sources.map((source) => source.source_version_id) ?? [])],
    [task],
  );
  const taskEvidenceIds = useMemo(
    () => task?.sources.map((source) => source.evidence_id) ?? [],
    [task],
  );

  /* 提取标题块作为侧栏导航 */
  const headings = useMemo<HeadingBlock[]>(() => {
    if (!task) return [];
    return task.content_blocks.filter(
      (b): b is HeadingBlock => b.type === "heading",
    );
  }, [task]);

  /* 滚动到指定 id */
  const scrollTo = useCallback((id: string) => {
    setActiveSection(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  /* 渲染内容块 */
  const renderBlock = useCallback((block: ContentBlock) => {
    switch (block.type) {
      case "heading":
        return <BlockHeading key={block.id} block={block} active={activeSection === block.id} onClick={() => scrollTo(block.id)} />;
      case "paragraph":
        return <BlockParagraph key={block.id} block={block} mode={paraMode} onModeChange={setParaMode} />;
      case "citation":
        return <BlockCitation key={block.id} block={block} onOpenPanel={() => { setCitationSource(block); setHelperPanel("source"); }} />;
      case "diagram":
        return <DiagramPlaceholder key={block.id} block={block} />;
      case "callout":
        return <BlockCallout key={block.id} block={block} />;
      case "quiz":
        return <BlockQuiz key={block.id} block={block} />;
      default:
        return null;
    }
  }, [activeSection, paraMode, scrollTo]);

  /* ── 加载态 / 错误态 ── */
  if (loading) {
    return (
      <div className="learning-shell">
        <DesktopTitleBar />
        <div className="loading-container"><span>正在加载任务内容…</span></div>
      </div>
    );
  }

  if (error || !task) {
    return (
      <div className="learning-shell">
        <DesktopTitleBar />
        <div className="error-container">
          <p>{error ?? "任务不存在"}</p>
          <Link to={courseId ? `/courses/${courseId}` : "/courses"}>返回课程</Link>
        </div>
      </div>
    );
  }

  if (learningMode === "exercise" && courseId) {
    return (
      <div className="learning-shell learning-shell-quiz">
        <DesktopTitleBar />
        <QuizPracticeView
          files={fileNodes}
          defaultSourceId={taskSourceVersionIds[0] ?? null}
          onBack={() => navigate(`/courses/${courseId}`)}
          onOpenSource={(id) => navigate(`/courses/${courseId}?sourceVersionId=${encodeURIComponent(id)}`)}
          taskMode={{
            taskId: task.task_id,
            taskTitle: task.title,
            sourceEvidenceIds: taskEvidenceIds,
            sourceVersionIds: taskSourceVersionIds,
            courseSessionId,
            onCompleted: () => {
              void completeLearningTask(task.task_id).catch(() => {});
            },
          }}
        />
      </div>
    );
  }

  return (
    <div className="learning-shell">
      <DesktopTitleBar />
      <header className="learning-topbar">
        <Link to={courseId ? `/courses/${courseId}` : "/courses"}>
          <ArrowLeft size={18} />
          返回课程主页
        </Link>
      </header>

      <header className="task-titlebar">
        <div>
          <span>{task.phase_title} · {task.unit_title} · #{task.position}</span>
          <h1>{task.title}</h1>
        </div>
        <span className="task-estimate"><Clock3 size={15} /> 约 {task.estimated_minutes} 分钟</span>
      </header>

      <div className={`learning-layout${helperPanel ? " helper-open" : ""}`}>
        <aside className="lesson-outline">
          <span className="outline-toggle" role="button" tabIndex={-1}>
            本节内容
          </span>
          <nav aria-label="本节目录">
            {headings.map((h) => (
              <button
                key={h.id}
                className={activeSection === h.id ? "active" : ""}
                onClick={() => scrollTo(h.id)}
                type="button"
              >
                <span>{activeSection === h.id ? <Check size={12} /> : null}</span>
                {h.label}
              </button>
            ))}
          </nav>
        </aside>

        <main className="lesson-content">
          <article className="lesson-article">
            {courseId && <ReferenceEvidenceBlock courseId={courseId} sources={task.sources} />}
            {task.content_blocks.length === 0 && task.sources.length > 0 && (
              <p className="task-content-placeholder">本任务以参考资料为主，请阅读上方依据后开始学习。</p>
            )}
            {task.content_blocks.map(renderBlock)}
          </article>
        </main>

        <aside className="learning-helper-rail">
          <button
            className={helperPanel === "ai" ? "active" : ""}
            onClick={() => setHelperPanel(helperPanel === "ai" ? null : "ai")}
            type="button"
          >
            <Bot size={21} />
            <span>AI 助手</span>
            <ChevronRight size={16} />
          </button>
        </aside>

        {helperPanel && (
          <aside className="helper-panel">
            <div className="helper-panel-head">
              <div>
                {helperPanel === "source" ? <BookOpen size={18} /> : <Bot size={18} />}
                <strong>{helperPanel === "source" ? "资料原文" : "AI 助手"}</strong>
              </div>
              <button aria-label="关闭辅助面板" onClick={() => { setHelperPanel(null); setCitationSource(null); }} type="button">
                <X size={17} />
              </button>
            </div>
            {helperPanel === "source" && citationSource ? (
              <div className="source-preview">
                {citationSource.chapter && <span>{citationSource.chapter}</span>}
                <h3>{citationSource.source_title}</h3>
                <p>页码：第 {citationSource.page_number} 页</p>
                <mark>evidence_id: {citationSource.evidence_id}</mark>
              </div>
            ) : helperPanel === "ai" ? (
              <div className="assistant-panel-content">
                <p>我会围绕当前任务和已授权课程资料回答。</p>
                <button onClick={() => setParaMode("simple")} type="button">用更简单的话解释</button>
                <button onClick={() => setParaMode("example")} type="button">再举一个例子</button>
              </div>
            ) : null}
          </aside>
        )}
      </div>
    </div>
  );
}

/* ── 图解占位（后端 diagram_type + data 由前端按类型渲染）── */

function DiagramPlaceholder({ block }: { block: DiagramBlock }) {
  return (
    <section className="diagram-block" aria-label={block.label}>
      <strong>{block.label}</strong>
      <p className="diagram-fallback">[{block.diagram_type} 图解 — 渲染器待实现]</p>
    </section>
  );
}
