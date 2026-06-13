import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  Circle,
  ClipboardCheck,
  FileText,
  Map,
  Play,
  Settings,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { coursePhases, focusTasks } from "../data/courses";

const courseTabs = ["课程主页", "学习方案", "课程资料", "知识地图", "测评记录"];

function TaskStateIcon({ state }: { state: string }) {
  if (state === "completed") return <Check size={14} />;
  if (state === "current") return <Play size={13} />;
  if (state === "checkpoint") return <ClipboardCheck size={14} />;
  return <Circle size={14} />;
}

export function CourseWorkspacePage() {
  const { courseId = "computer-architecture" } = useParams();
  const currentTask = focusTasks.find((task) => task.state === "current") ?? focusTasks[1];

  return (
    <AppShell>
      <div className="course-workspace">
        <header className="course-workspace-header">
          <div className="course-cover" aria-hidden="true">
            <span>计</span>
            <small>组成原理</small>
          </div>
          <div className="course-title-block">
            <div>
              <h1>计算机组成原理</h1>
              <span className="learning-status">学习中</span>
            </div>
            <p>学习目标：完成重点复习，掌握考试高频知识点。</p>
            <strong>当前阶段：重点突破（第 2 阶段）</strong>
          </div>
          <button className="button secondary course-settings" type="button">
            <Settings size={16} />
            课程设置
          </button>
        </header>

        <nav className="course-tabs" aria-label="课程功能">
          {courseTabs.map((tab, index) =>
            index === 0 ? (
              <Link className="active" key={tab} to={`/courses/${courseId}`}>
                {tab}
              </Link>
            ) : (
              <button key={tab} type="button">{tab}</button>
            ),
          )}
        </nav>

        <section className="workspace-section">
          <div className="workspace-section-heading">
            <h2>学习阶段</h2>
            <p>阶段是课程主结构，你可以按实际情况连续推进。</p>
          </div>
          <div className="workspace-phase-path">
            {coursePhases.map((phase, index) => (
              <div className="workspace-phase-item" key={phase.id}>
                <button className={phase.state} type="button">
                  <span>{phase.state === "completed" ? <Check size={14} /> : index + 1}</span>
                  <strong>{phase.name}</strong>
                  <small>约 {phase.share}%</small>
                </button>
                {index < coursePhases.length - 1 ? <ChevronRight size={20} /> : null}
              </div>
            ))}
          </div>
        </section>

        <section className="recommended-task">
          <div className="recommendation-icon">
            <BookOpen size={27} />
          </div>
          <div className="recommendation-copy">
            <span>接下来建议学习</span>
            <h2>{currentTask.name}</h2>
            <p>理解三种映射方式的原理与适用场景，掌握命中率的影响因素与基本计算。</p>
            <div>
              <span><FileText size={14} /> 新知识</span>
              <span>{currentTask.estimate}</span>
              <span><Map size={14} /> 知识点讲解 + 例题</span>
            </div>
          </div>
          <div className="recommendation-actions">
            <Link className="button primary" to={`/courses/${courseId}/tasks/${currentTask.id}`}>
              继续学习 <ArrowRight size={16} />
            </Link>
            <button type="button">查看任务详情</button>
          </div>
        </section>

        <section className="phase-task-section">
          <div className="workspace-section-heading">
            <h2>重点突破阶段任务</h2>
            <p>默认按推荐顺序，也可以选择其他已解锁任务。</p>
          </div>
          <div className="phase-task-list">
            {focusTasks.map((task) => {
              const content = (
                <>
                  <span className={`task-state-icon ${task.state}`}>
                    <TaskStateIcon state={task.state} />
                  </span>
                  <span className="task-index">{task.index}</span>
                  <strong>{task.name}</strong>
                  <span className={`task-kind ${task.type === "实践" ? "practice" : task.type === "检查点" ? "check" : ""}`}>
                    {task.type}
                  </span>
                  <span className="task-row-state">
                    {task.state === "completed"
                      ? "已完成"
                      : task.state === "current"
                        ? "当前任务"
                        : task.estimate}
                  </span>
                  <ChevronRight size={17} />
                </>
              );

              return task.state === "current" ? (
                <Link
                  className={`phase-task-row ${task.state}`}
                  key={task.id}
                  to={`/courses/${courseId}/tasks/${task.id}`}
                >
                  {content}
                </Link>
              ) : (
                <button className={`phase-task-row ${task.state}`} key={task.id} type="button">
                  {content}
                </button>
              );
            })}
          </div>
          <button className="view-all-tasks" type="button">
            查看本阶段全部任务（共 {focusTasks.length} 项）
            <ChevronRight size={16} />
          </button>
        </section>
      </div>
    </AppShell>
  );
}
