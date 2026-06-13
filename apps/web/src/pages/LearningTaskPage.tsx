import { useState } from "react";
import {
  ArrowLeft,
  BookOpen,
  Bot,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  ExternalLink,
  Lightbulb,
  RefreshCw,
  Sparkles,
  X,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

const contentSections = [
  { id: "goal", label: "本节目标" },
  { id: "locality", label: "局部性原理" },
  { id: "mapping", label: "三种映射方式" },
  { id: "example", label: "示例" },
  { id: "check", label: "即时检查" },
  { id: "summary", label: "小结" },
];

type HelperPanel = "source" | "ai" | null;

export function LearningTaskPage() {
  const { courseId = "computer-architecture" } = useParams();
  const [activeSection, setActiveSection] = useState("mapping");
  const [helperPanel, setHelperPanel] = useState<HelperPanel>(null);
  const [explanationMode, setExplanationMode] = useState<"standard" | "simple" | "example">("standard");
  const [checkOpen, setCheckOpen] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);

  const explanation =
    explanationMode === "simple"
      ? "主存像一整排书架，Cache 像桌面。映射规则决定某本书应该放在桌面的哪个位置，避免每次都从全部位置里寻找。"
      : explanationMode === "example"
        ? "例如主存块 12 采用直接映射时，只能进入由 12 mod Cache 行数计算出的固定行。这样查找很快，但多个主存块可能争用同一行。"
        : "Cache 的容量远小于主存。主存数据进入 Cache 时必须决定存放位置，这套规则就是映射规则。合理的规则可以降低查找成本，并在冲突与空间利用率之间取得平衡。";

  return (
    <div className="learning-shell">
      <header className="learning-topbar">
        <Link to={`/courses/${courseId}`}>
          <ArrowLeft size={18} />
          返回课程主页
        </Link>
        <div className="learning-window-controls" aria-hidden="true">
          <span>−</span><span>□</span><span>×</span>
        </div>
      </header>

      <header className="task-titlebar">
        <div>
          <span>重点突破 · 2.2</span>
          <h1>Cache 映射方式与命中率</h1>
        </div>
        <span className="task-estimate"><Clock3 size={15} /> 约 18 分钟</span>
      </header>

      <div className={`learning-layout${helperPanel ? " helper-open" : ""}`}>
        <aside className="lesson-outline">
          <button className="outline-toggle" type="button">
            本节内容 <ChevronDown size={15} />
          </button>
          <nav aria-label="本节目录">
            {contentSections.map((section) => (
              <button
                className={activeSection === section.id ? "active" : ""}
                key={section.id}
                onClick={() => setActiveSection(section.id)}
                type="button"
              >
                <span>{activeSection === section.id ? <Check size={12} /> : null}</span>
                {section.label}
              </button>
            ))}
          </nav>
        </aside>

        <main className="lesson-content">
          <section className="lesson-goal">
            <span>本节目标</span>
            <p>理解 Cache 为什么需要映射规则，掌握三种映射方式及命中率的基本概念。</p>
          </section>

          <article className="lesson-article">
            <h2>为什么 Cache 需要映射规则？</h2>
            <p>{explanation}</p>

            <button className="source-citation" onClick={() => setHelperPanel("source")} type="button">
              <span>来源：计算机组成原理（第 6 版）第 3 章</span>
              <strong>查看原文 <ExternalLink size={13} /></strong>
            </button>

            <section className="mapping-visual" aria-label="主存地址到 Cache 行的映射示例">
              <div>
                <strong>主存块号</strong>
                {["0000", "0001", "0010", "0011", "…", "1110", "1111"].map((value) => (
                  <span key={value}>{value}</span>
                ))}
              </div>
              <div className="mapping-arrows" aria-hidden="true">
                {Array.from({ length: 7 }, (_, index) => <span key={index}>→</span>)}
              </div>
              <div className="cache-lines">
                <strong>Cache 行（示例）</strong>
                {["0 · 有效位 / 标签 / 数据块", "1 · 有效位 / 标签 / 数据块", "2 · 有效位 / 标签 / 数据块", "3 · 有效位 / 标签 / 数据块", "…", "C-2 · 标签 / 数据块", "C-1 · 标签 / 数据块"].map((value) => (
                  <span key={value}>{value}</span>
                ))}
              </div>
            </section>

            <div className="ai-tip">
              <Sparkles size={16} />
              <p><strong>AI 小贴士：</strong>映射规则决定主存块需要落入哪些 Cache 行，常见冲突会导致命中率下降。</p>
            </div>

            {checkOpen ? (
              <section className="inline-check">
                <div>
                  <span>即时检查</span>
                  <h3>直接映射中，一个主存块可以放入几个 Cache 行？</h3>
                </div>
                <div className="check-options">
                  {["只能放入一个固定行", "可以放入任意行", "只能放入两个相邻行"].map((option) => (
                    <button
                      className={answer === option ? "selected" : ""}
                      key={option}
                      onClick={() => setAnswer(option)}
                      type="button"
                    >
                      {option}
                    </button>
                  ))}
                </div>
                {answer ? (
                  <p className={answer === "只能放入一个固定行" ? "correct" : "retry"}>
                    {answer === "只能放入一个固定行"
                      ? "回答正确。固定位置让硬件查找更快，但也更容易发生冲突。"
                      : "再想一下：直接映射的“直接”意味着位置由块号唯一计算。"}
                  </p>
                ) : null}
              </section>
            ) : null}
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

        {helperPanel ? (
          <aside className="helper-panel">
            <div className="helper-panel-head">
              <div>
                {helperPanel === "source" ? <BookOpen size={18} /> : <Bot size={18} />}
                <strong>{helperPanel === "source" ? "资料原文" : "AI 助手"}</strong>
              </div>
              <button aria-label="关闭辅助面板" onClick={() => setHelperPanel(null)} type="button">
                <X size={17} />
              </button>
            </div>
            {helperPanel === "source" ? (
              <div className="source-preview">
                <span>第 3 章 · 存储系统</span>
                <h3>3.4 Cache 映射方式</h3>
                <p>主存块装入 Cache 时，需要按照某种函数关系映射到 Cache 行。常用方式包括直接映射、全相联映射与组相联映射。</p>
                <mark>映射方式影响查找速度、硬件复杂度以及冲突概率。</mark>
              </div>
            ) : (
              <div className="assistant-panel-content">
                <p>我会围绕当前任务和已授权课程资料回答。</p>
                <button onClick={() => setExplanationMode("simple")} type="button">用更简单的话解释</button>
                <button onClick={() => setExplanationMode("example")} type="button">再举一个例子</button>
                <button type="button">这和局部性原理有什么关系？</button>
              </div>
            )}
          </aside>
        ) : null}
      </div>

      <footer className="lesson-actions">
        <button onClick={() => setExplanationMode("simple")} type="button">
          <RefreshCw size={16} /> 换一种解释
        </button>
        <button onClick={() => setExplanationMode("example")} type="button">
          <Lightbulb size={16} /> 看一个例子
        </button>
        <button className="primary" onClick={() => setCheckOpen(true)} type="button">
          开始检查 <ChevronRight size={17} />
        </button>
      </footer>
    </div>
  );
}
