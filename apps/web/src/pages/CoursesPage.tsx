import {
  ArrowRight,
  BookOpen,
  Clock,
  FileWarning,
  Layers,
  Plus,
  Search,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { AppShell } from "../components/AppShell";
import { deleteCourseSession, type CourseSessionListItem } from "../services/courseApi";
import { useCourseSessions } from "../hooks/useCourseSessions";
import { usePrefetchCourseWorkspace } from "../hooks/usePrefetchCourseWorkspace";

/* ── 状态映射 ── */

const STATUS_LABEL: Record<string, string> = {
  collecting: "收集信息中",
  inquiring: "AI 追问中",
  generating_plan: "生成方案中",
  completed: "方案已生成",
  started: "学习中",
};

const STATUS_CLASS: Record<string, string> = {
  started: "",
  completed: "waiting",
};

const COLOR_KEYS = ["teal", "blue", "violet"] as const;

function pickColor(index: number): string {
  return COLOR_KEYS[index % COLOR_KEYS.length];
}

const colorClasses: Record<string, string> = {
  teal: "course-card-teal",
  blue: "course-card-blue",
  violet: "course-card-violet",
};

/* ── 组件 ── */

function CourseHeader({ hasCourses }: { hasCourses: boolean }) {
  const navigate = useNavigate();
  return (
    <header className="page-header">
      <div>
        <h1>课程</h1>
        <p>
          {hasCourses
            ? "从当前阶段继续，或开始一门新的学习课程。"
            : "描述你想完成的学习目标，Mentora 会帮你整理需求并规划阶段路径。"}
        </p>
      </div>
      <div className="page-actions">
        <label className="search-field">
          <Search size={17} />
          <input aria-label="搜索课程" placeholder="搜索课程" />
        </label>
        <button className="button primary compact" onClick={() => navigate("/courses/new")} type="button">
          <Plus size={17} />
          创建课程
        </button>
      </div>
    </header>
  );
}

function EmptyCourses() {
  const navigate = useNavigate();
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <BookOpen size={42} strokeWidth={1.45} />
      </div>
      <h2>还没有课程</h2>
      <p>描述你想完成的学习目标，Mentora 会帮你整理需求并规划阶段路径。</p>
      <button className="button primary" onClick={() => navigate("/courses/new")} type="button">
        <Plus size={17} />
        创建第一门课程
      </button>
      <div className="empty-note">
        <Sparkles size={17} />
        <span>不需要先准备资料，也可以从一段自然语言开始。</span>
      </div>
    </div>
  );
}

function courseDisplayName(title: string, goal: string): string {
  if (title) return title;
  // 回退：截断 goal
  const trimmed = goal.trim();
  if (trimmed.length <= 15) return trimmed;
  return trimmed.slice(0, 15) + "…";
}

function fmtDate(iso: string): string {
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "今天";
    if (diffDays === 1) return "昨天";
    return d.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
  } catch {
    return "";
  }
}

function fmtDeadline(deadline: string | null): string | null {
  if (!deadline) return null;
  try {
    const d = new Date(deadline);
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    const diffDays = Math.round((target.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
    if (diffDays < 0) return "已截止";
    if (diffDays === 0) return "今天截止";
    if (diffDays === 1) return "明天截止";
    return `还有 ${diffDays} 天`;
  } catch {
    return null;
  }
}

const TASK_TYPE_LABEL: Record<string, string> = {
  lecture: "讲解",
  exercise: "练习",
  project: "项目",
  review: "复习",
};

function courseCardHref(course: CourseSessionListItem): string {
  if (course.course_id) return `/courses/${course.course_id}`;
  // 尚未绑定 Course 实体时，回到建课流程而非工作台（避免 session ID 404）
  if (course.status === "completed") return "/courses/new/plan";
  return "/courses/new";
}

function CourseList({
  courses,
  onDelete,
}: {
  courses: CourseSessionListItem[];
  onDelete: (id: string) => void;
}) {
  const [confirmId, setConfirmId] = useState<string | null>(null);
  const prefetchCourse = usePrefetchCourseWorkspace();

  return (
    <div className="course-list">
      {courses.map((course, i) => {
        const color = pickColor(i);
        const statusLabel = STATUS_LABEL[course.status] ?? course.status;
        const statusClass = STATUS_CLASS[course.status] ?? "";
        const isStarted = course.status === "started";
        const isCompleted = course.status === "completed";

        const name = courseDisplayName(course.title, course.goal);
        const cardHref = courseCardHref(course);
        const workspaceId = course.course_id;

        return (
          <div className="course-card-wrapper" key={course.id}>
            <Link
              className={`course-card ${colorClasses[color] ?? ""}`}
              to={cardHref}
              onMouseEnter={() => {
                if (workspaceId) prefetchCourse(workspaceId, course.id);
              }}
              onFocus={() => {
                if (workspaceId) prefetchCourse(workspaceId, course.id);
              }}
            >
              <span className={`course-card-icon ${color}`}>
                {name.charAt(0)}
              </span>
              <h2 className="course-card-name">{name}</h2>
              <div className="course-card-meta">
                {(isStarted || isCompleted) && (
                  <span className="course-card-progress">
                    <span
                      className="course-card-progress-bar"
                      style={{ width: isCompleted ? "100%" : "0%" }}
                    />
                  </span>
                )}
                <span className={`course-card-status${statusClass ? ` ${statusClass}` : ""}`}>
                  {statusLabel}
                </span>
              </div>

              <div className="course-card-detail">
                <div className="course-card-phase">
                  <Layers size={12} />
                  <span>
                    {course.current_phase
                      ? `当前阶段：${course.current_phase}`
                      : course.school || "未填写学校"}
                  </span>
                </div>
                <div className="course-card-next">
                  <Clock size={12} />
                  <span>
                    {course.next_task
                      ? `下一个：${TASK_TYPE_LABEL[course.next_task] || course.next_task}`
                      : "准备开始学习"}
                  </span>
                </div>
                <span className="course-card-estimate">
                  {fmtDeadline(course.deadline)
                    ? `截止：${fmtDeadline(course.deadline)}　　创建：${fmtDate(course.created_at)}`
                    : `创建：${fmtDate(course.created_at)}`}
                  {course.last_studied_at && (
                    <>　　上次：{fmtDate(course.last_studied_at)}</>
                  )}
                </span>
                <ArrowRight size={15} className="course-card-arrow" />
              </div>
          </Link>

          {/* 删除 — 仅 hover 显示 */}
          <button
            className="course-card-delete"
            onClick={(e) => { e.preventDefault(); setConfirmId(course.id); }}
            title="删除课程"
            type="button"
          >
            <Trash2 size={14} />
          </button>

          {confirmId === course.id && (
            <div className="course-delete-confirm">
              <FileWarning size={15} />
              <span>确定删除该课程？</span>
              <button
                className="button primary danger small"
                onClick={(e) => {
                  e.preventDefault();
                  onDelete(course.id);
                  setConfirmId(null);
                }}
                type="button"
              >
                删除
              </button>
              <button
                className="button secondary small"
                onClick={(e) => { e.preventDefault(); setConfirmId(null); }}
                type="button"
              >
                <X size={13} />
              </button>
            </div>
          )}
        </div>
        );
      })}
    </div>
  );
}

export function CoursesPage() {
  const location = useLocation();
  const queryClient = useQueryClient();
  const urlParamEmpty = new URLSearchParams(location.search).get("state") === "empty";
  const { data: sessions = [], isLoading, error, refetch } = useCourseSessions(!urlParamEmpty);

  // 建课完成后跳回列表页时主动刷新
  useEffect(() => {
    const started = sessionStorage.getItem("mentora-course-started");
    if (!started) return;
    sessionStorage.removeItem("mentora-course-started");
    queryClient.invalidateQueries({ queryKey: ["courses", "sessions"] });
  }, [queryClient]);

  const displayCourses = sessions.filter((s) => s.status === "started" || s.status === "completed");
  const hasCourses = displayCourses.length > 0;
  const showLoading = isLoading && sessions.length === 0;
  const errorMessage = error instanceof Error ? error.message : error ? "获取课程列表失败" : "";

  const handleDelete = useCallback(async (id: string) => {
    try {
      await deleteCourseSession(id);
      queryClient.invalidateQueries({ queryKey: ["courses", "sessions"] });
    } catch {
      // 静默失败
    }
  }, [queryClient]);

  return (
    <AppShell>
      <CourseHeader hasCourses={hasCourses} />
      {showLoading && (
        <div className="empty-state">
          <p style={{ color: "var(--quiet)" }}>加载中…</p>
        </div>
      )}
      {errorMessage && (
        <div className="empty-state">
          <p className="error-text">{errorMessage}</p>
          <button className="button secondary" onClick={() => refetch()} type="button">
            重试
          </button>
        </div>
      )}
      {!showLoading && !errorMessage && !hasCourses && <EmptyCourses />}
      {hasCourses && (
        <CourseList
          courses={displayCourses}
          onDelete={handleDelete}
        />
      )}
    </AppShell>
  );
}
