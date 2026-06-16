import { useMemo, useState } from "react";
import {
  Award,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  FileText,
  Flag,
  Layers,
  Pause,
  Play,
  Search,
  Target,
  Upload,
  X,
} from "lucide-react";

import { AppShell } from "../components/AppShell";
import {
  formatDateLabel,
  groupByDate,
  historyEntries,
  typeLabels,
  type HistoryEntry,
  type HistoryEventType,
} from "../data/history";
import { courses } from "../data/courses";

/* ── icon by event type ────────────────────────────── */

const typeIcons: Record<HistoryEventType, typeof Check> = {
  task_completed: Check,
  task_started: Play,
  check_passed: Target,
  check_failed: X,
  stage_changed: Layers,
  plan_adjusted: FileText,
  source_added: Upload,
  source_updated: FileText,
  quiz_attempted: BookOpen,
  skill_mastered: Award,
  course_started: Flag,
  course_paused: Pause,
};

const typeColors: Record<HistoryEventType, string> = {
  task_completed: "var(--green-700)",
  task_started: "var(--blue)",
  check_passed: "var(--green-700)",
  check_failed: "#ba3b35",
  stage_changed: "#7253a7",
  plan_adjusted: "#c75a2b",
  source_added: "var(--blue)",
  source_updated: "#7253a7",
  quiz_attempted: "#ad7519",
  skill_mastered: "#0b776c",
  course_started: "var(--green-700)",
  course_paused: "#8e9893",
};

/* ── main page ─────────────────────────────────────── */

export function HistoryPage() {
  const [courseFilter, setCourseFilter] = useState<string>("all");
  const [typeFilter, setTypeFilter] = useState<HistoryEventType | "all">("all");
  const [search, setSearch] = useState("");
  const [courseMenuOpen, setCourseMenuOpen] = useState(false);
  const [typeMenuOpen, setTypeMenuOpen] = useState(false);

  /* filters */
  const filtered = useMemo(() => {
    let entries = historyEntries;
    if (courseFilter !== "all")
      entries = entries.filter((e) => e.courseId === courseFilter);
    if (typeFilter !== "all")
      entries = entries.filter((e) => e.type === typeFilter);
    if (search.trim()) {
      const q = search.toLowerCase();
      entries = entries.filter(
        (e) =>
          e.title.toLowerCase().includes(q) ||
          e.courseName.toLowerCase().includes(q) ||
          (e.detail && e.detail.toLowerCase().includes(q)),
      );
    }
    return entries;
  }, [courseFilter, typeFilter, search]);

  const dateGroups = useMemo(() => groupByDate(filtered), [filtered]);
  const dateKeys = Array.from(dateGroups.keys());

  /* collapse state — all expanded by default */
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  function toggleDate(date: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(date)) next.delete(date);
      else next.add(date);
      return next;
    });
  }

  return (
    <AppShell>
      <div className="history-page">
        <header className="page-header">
          <div>
            <h1>学习记录</h1>
            <p>按时间回顾任务学习、检查结果、阶段变化与方案调整。学习记录不承担日程管理。</p>
          </div>
          <div className="page-actions">
            <div className="search-field">
              <Search size={16} />
              <input
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索事件或课程…"
                type="text"
                value={search}
              />
              {search && (
                <button
                  className="search-clear"
                  onClick={() => setSearch("")}
                  type="button"
                  aria-label="清除搜索"
                >
                  <X size={14} />
                </button>
              )}
            </div>
          </div>
        </header>

        {/* filters */}
        <div className="history-filters">
          <div className="filter-dropdown">
            <button
              className="filter-trigger"
              onClick={() => {
                setCourseMenuOpen(!courseMenuOpen);
                setTypeMenuOpen(false);
              }}
              type="button"
            >
              <BookOpen size={14} />
              {courseFilter === "all"
                ? "全部课程"
                : courses.find((c) => c.id === courseFilter)?.name ?? courseFilter}
              <ChevronDown size={13} />
            </button>
            {courseMenuOpen && (
              <div className="filter-menu">
                <button
                  className={courseFilter === "all" ? "selected" : ""}
                  onClick={() => { setCourseFilter("all"); setCourseMenuOpen(false); }}
                  type="button"
                >
                  全部课程
                  {courseFilter === "all" && <Check size={14} />}
                </button>
                {courses.map((c) => (
                  <button
                    className={courseFilter === c.id ? "selected" : ""}
                    key={c.id}
                    onClick={() => { setCourseFilter(c.id); setCourseMenuOpen(false); }}
                    type="button"
                  >
                    {c.name}
                    {courseFilter === c.id && <Check size={14} />}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="filter-dropdown">
            <button
              className="filter-trigger"
              onClick={() => {
                setTypeMenuOpen(!typeMenuOpen);
                setCourseMenuOpen(false);
              }}
              type="button"
            >
              <Layers size={14} />
              {typeFilter === "all" ? "全部类型" : typeLabels[typeFilter]}
              <ChevronDown size={13} />
            </button>
            {typeMenuOpen && (
              <div className="filter-menu">
                <button
                  className={typeFilter === "all" ? "selected" : ""}
                  onClick={() => { setTypeFilter("all"); setTypeMenuOpen(false); }}
                  type="button"
                >
                  全部类型
                  {typeFilter === "all" && <Check size={14} />}
                </button>
                {(Object.entries(typeLabels) as [HistoryEventType, string][]).map(([key, label]) => (
                  <button
                    className={typeFilter === key ? "selected" : ""}
                    key={key}
                    onClick={() => { setTypeFilter(key); setTypeMenuOpen(false); }}
                    type="button"
                  >
                    {label}
                    {typeFilter === key && <Check size={14} />}
                  </button>
                ))}
              </div>
            )}
          </div>

          {filtered.length < historyEntries.length && (
            <span className="filter-count">
              显示 {filtered.length} / {historyEntries.length} 条
            </span>
          )}
        </div>

        {/* timeline */}
        {dateKeys.length === 0 ? (
          <div className="history-empty">
            <Search size={28} />
            <strong>没有匹配的学习记录</strong>
            <span>尝试调整筛选条件</span>
          </div>
        ) : (
          <div className="history-timeline">
            {dateKeys.map((date) => {
              const entries = dateGroups.get(date)!;
              const isCollapsed = collapsed.has(date);
              return (
                <div className="history-day-group" key={date}>
                  <button
                    className="history-day-header"
                    onClick={() => toggleDate(date)}
                    type="button"
                  >
                    <span className="history-day-toggle">
                      {isCollapsed ? <ChevronRight size={15} /> : <ChevronDown size={15} />}
                    </span>
                    <strong>{formatDateLabel(date)}</strong>
                    <span className="history-day-date">{date}</span>
                    <span className="history-day-count">{entries.length} 条记录</span>
                  </button>

                  {!isCollapsed && (
                    <div className="history-day-entries">
                      {entries.map((entry) => (
                        <HistoryRow entry={entry} key={entry.id} />
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}

/* ── single history row ────────────────────────────── */

function HistoryRow({ entry }: { entry: HistoryEntry }) {
  const Icon = typeIcons[entry.type];
  const color = typeColors[entry.type];
  const label = typeLabels[entry.type];

  return (
    <div className="history-row">
      {/* timeline dot + line */}
      <div className="history-timeline-node">
        <span className="history-dot" style={{ borderColor: color, color }}>
          <Icon size={12} />
        </span>
      </div>

      {/* content */}
      <div className="history-row-body">
        <div className="history-row-head">
          <span className="history-time">
            <Clock3 size={10} />
            {entry.time}
          </span>
          <span
            className="history-type-tag"
            style={{ color, background: `${color}14`, borderColor: `${color}30` }}
          >
            {label}
          </span>
          <span className={`history-course-pill course-${entry.courseColor}`}>
            {entry.courseName}
          </span>
        </div>

        <strong className="history-row-title">{entry.title}</strong>

        {entry.detail && (
          <p className="history-row-detail">{entry.detail}</p>
        )}

        {entry.result && (
          <span className="history-row-result">{entry.result}</span>
        )}
      </div>
    </div>
  );
}
