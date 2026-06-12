import {
  BookOpen,
  FileText,
  MoreHorizontal,
  Plus,
  Search,
  Sparkles,
} from "lucide-react";
import { Link, useLocation } from "react-router-dom";

import { AppShell } from "../components/AppShell";
import { courses } from "../data/courses";

function CourseHeader() {
  return (
    <header className="page-header">
      <div>
        <h1>课程</h1>
        <p>从当前阶段继续，或开始一门新的学习课程。</p>
      </div>
      <div className="page-actions">
        <label className="search-field">
          <Search size={17} />
          <input aria-label="搜索课程" placeholder="搜索课程" />
        </label>
        <Link className="button primary compact" to="/courses/new">
          <Plus size={17} />
          创建课程
        </Link>
      </div>
    </header>
  );
}

function EmptyCourses() {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <BookOpen size={42} strokeWidth={1.45} />
      </div>
      <h2>还没有课程</h2>
      <p>描述你想完成的学习目标，Mentora 会帮你整理需求并规划阶段路径。</p>
      <Link className="button primary" to="/courses/new">
        <Plus size={17} />
        创建第一门课程
      </Link>
      <div className="empty-note">
        <Sparkles size={17} />
        <span>不需要先准备资料，也可以从一段自然语言开始。</span>
      </div>
    </div>
  );
}

function CourseTable() {
  return (
    <div className="course-table">
      <div className="course-table-head" aria-hidden="true">
        <span>课程</span>
        <span>当前阶段</span>
        <span>下一步推荐</span>
        <span>状态</span>
        <span>阶段进度</span>
        <span />
      </div>
      {courses.map((course) => (
        <article className="course-row" key={course.id}>
          <div className="course-identity">
            <span className={`course-icon ${course.color}`}>{course.icon}</span>
            <div>
              <h2>{course.name}</h2>
              <p>{course.updatedAt}</p>
            </div>
          </div>
          <div className="cell-copy">
            <strong>{course.phase}</strong>
            <span>{course.phaseDetail}</span>
          </div>
          <div className="next-recommendation">
            <FileText size={17} />
            <div>
              <strong>{course.nextTask}</strong>
              <span>{course.estimate}</span>
            </div>
          </div>
          <span className={`status-tag ${course.status === "待确认" ? "waiting" : ""}`}>
            {course.status}
          </span>
          <div className="progress-cell">
            <strong>{course.progress}%</strong>
            <span className="progress-line">
              <i style={{ width: `${Math.max(course.progress, 4)}%` }} />
            </span>
          </div>
          <button className="icon-button" type="button" aria-label={`${course.name}更多操作`}>
            <MoreHorizontal size={19} />
          </button>
        </article>
      ))}
    </div>
  );
}

export function CoursesPage() {
  const location = useLocation();
  const isEmpty = new URLSearchParams(location.search).get("state") === "empty";

  return (
    <AppShell>
      <CourseHeader />
      {isEmpty ? <EmptyCourses /> : <CourseTable />}
    </AppShell>
  );
}
