import { useMemo, useState } from "react";
import { Check, CircleHelp } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { SetupShell } from "../components/AppShell";

export function DescribeGoalPage() {
  const navigate = useNavigate();
  const [goal, setGoal] = useState("");
  const canContinue = goal.trim().length >= 4;

  function submitGoal(event: React.FormEvent) {
    event.preventDefault();
    if (!canContinue) return;
    sessionStorage.setItem("mentora-course-goal", goal.trim());
    navigate("/courses/new/clarify");
  }

  return (
    <SetupShell current={1}>
      <form className="goal-form" onSubmit={submitGoal}>
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
        <div className="setup-footer">
          <span className="autosave-state">内容会自动保存</span>
          <button className="button primary" disabled={!canContinue} type="submit">
            下一步
          </button>
        </div>
      </form>
    </SetupShell>
  );
}

const levelOptions = [
  { id: "beginner", title: "完全新手", description: "几乎没有接触过" },
  { id: "basic", title: "了解基础", description: "知道一些概念和术语" },
  { id: "studied", title: "学过一遍", description: "需要梳理和巩固" },
  { id: "uncertain", title: "不太确定", description: "可以先由系统诊断" },
];

export function ClarifyPage() {
  const storedGoal = sessionStorage.getItem("mentora-course-goal");
  const goal = storedGoal || "两周后完成计算机组成原理考试复习";
  const [level, setLevel] = useState("basic");
  const selectedLevel = useMemo(
    () => levelOptions.find((option) => option.id === level) ?? levelOptions[1],
    [level],
  );

  return (
    <SetupShell current={2}>
      <div className="clarify-panel">
        <div className="ai-context">
          <span className="ai-dot" />
          <div>
            <strong>Mentora AI</strong>
            <p>为了制定合适的阶段方案，我还需要确认 1 个关键信息。</p>
          </div>
        </div>

        <section className="question-block">
          <p className="question-index">当前问题</p>
          <h1>你目前对「计算机组成原理」的知识水平是？</h1>
          <div className="choice-grid">
            {levelOptions.map((option) => (
              <button
                aria-pressed={level === option.id}
                className={level === option.id ? "choice selected" : "choice"}
                key={option.id}
                onClick={() => setLevel(option.id)}
                type="button"
              >
                <strong>{option.title}</strong>
                <span>{option.description}</span>
                <i>{level === option.id ? <Check size={14} /> : null}</i>
              </button>
            ))}
          </div>
        </section>

        <section className="known-summary">
          <div className="summary-title">
            <div>
              <strong>已了解</strong>
              <span>可以随时返回修改</span>
            </div>
            <button type="button">编辑</button>
          </div>
          <dl>
            <div>
              <dt>目标</dt>
              <dd>{goal}</dd>
            </div>
            <div>
              <dt>基础</dt>
              <dd>{selectedLevel.title}</dd>
            </div>
          </dl>
        </section>

        <div className="clarify-footer">
          <button className="text-button" type="button">
            <CircleHelp size={16} />
            我还想补充说明
          </button>
          <button className="button primary" type="button">
            下一步：添加资料
          </button>
        </div>
      </div>
    </SetupShell>
  );
}
