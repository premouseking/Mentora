import {
  ArrowRight,
  BookOpen,
  Clock,
  Layers,
  MapPin,
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

const colorClasses: Record<string, string> = {
  teal: "course-card-teal",
  blue: "course-card-blue",
  violet: "course-card-violet",
};

function CourseList() {
  return (
    <div className="course-list">
      {courses.map((course) => (
        <Link
          className={`course-card ${colorClasses[course.color] ?? ""}`}
          key={course.id}
          to={`/courses/${course.id}`}
        >
          <span className={`course-card-icon ${course.color}`}>
            {course.icon}
          </span>
          <h2 className="course-card-name">{course.name}</h2>
          <div className="course-card-meta">
            {course.progress > 0 && (
              <span className="course-card-progress">
                <span
                  className="course-card-progress-bar"
                  style={{ width: `${course.progress}%` }}
                />
              </span>
            )}
            <span
              className={`course-card-status${course.status === "待确认" ? " waiting" : ""}`}
            >
              {course.status}
            </span>
          </div>

          <div className="course-card-detail">
            <div className="course-card-phase">
              <Layers size={12} />
              <span>{course.phase}</span>
              <span className="course-card-phase-detail">
                · {course.phaseDetail}
              </span>
            </div>
            <div className="course-card-next">
              <MapPin size={12} />
              <span>{course.nextTask}</span>
            </div>
            <span className="course-card-estimate">
              <Clock size={11} />
              {course.estimate}
            </span>
            <ArrowRight size={15} className="course-card-arrow" />
          </div>
        </Link>
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
      {isEmpty ? <EmptyCourses /> : <CourseList />}
    </AppShell>
  );
}
