import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  Pencil,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";

import { AppShell } from "../components/AppShell";
import { listCourseSessions, type CourseSessionListItem } from "../services/courseApi";
import { fetchHistory, type HistoryEvent } from "../services/learningApi";
import {
  formatDateLabel,
  formatMonthTitle,
  formatWeekdayLabel,
  getMonthGrid,
  getWeekDates,
  summarizeDay,
  TODAY_DATE_KEY,
} from "../data/history";

/* ── 本地 Task 类型（与 history/Task 兼容）── */

type ViewMode = "day" | "week" | "month";
type ModalMode = "add" | "edit" | null;

interface Task {
  id: string | number;
  date: string;
  time: string;
  status: "todo" | "done";
  title: string;
  course: string;
  courseId: string;
  desc: string;
}

interface TaskFormState {
  title: string;
  courseId: string;
  date: string;
  time: string;
  desc: string;
}

function emptyForm(date: string, courseId: string): TaskFormState {
  return { title: "", courseId, date, time: "09:00", desc: "" };
}

/** HistoryEvent → Task 转换 */
function historyEventToTask(ev: HistoryEvent): Task {
  return {
    id: ev.id,
    date: ev.created_at?.slice(0, 10) ?? "",
    time: ev.created_at?.slice(11, 16) ?? "",
    status: "done",
    title: ev.task_title || ev.description || ev.event_type,
    course: ev.course_title || "",
    courseId: ev.course_id ?? "",
    desc: ev.description || "",
  };
}

/* ── 主页面 ───────────────────────────────────────── */

export function HistoryPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [courses, setCourses] = useState<CourseSessionListItem[]>([]);
  const [loading, setLoading] = useState(true);

  const [view, setView] = useState<ViewMode>("day");
  const [selectedDate, setSelectedDate] = useState(TODAY_DATE_KEY);
  const [courseFilter, setCourseFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [courseMenuOpen, setCourseMenuOpen] = useState(false);
  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [editingId, setEditingId] = useState<string | number | null>(null);
  const [form, setForm] = useState<TaskFormState>(emptyForm(TODAY_DATE_KEY, "all"));
  const [todoCollapsed, setTodoCollapsed] = useState(false);
  const [doneCollapsed, setDoneCollapsed] = useState(false);

  /* 从后端加载历史记录 */
  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchHistory(), listCourseSessions()])
      .then(([historyData, courseData]) => {
        if (cancelled) return;
        setCourses(courseData);
        setTasks(historyData.items.map(historyEventToTask));
      })
      .catch(() => {
        // 静默降级
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  /** 课程 + 搜索筛选（不按日期，供周/月视图使用） */
  const baseFiltered = useMemo(() => {
    let list = tasks;
    if (courseFilter !== "all") {
      list = list.filter((t) => t.courseId === courseFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (t) =>
          t.title.toLowerCase().includes(q) ||
          t.course.toLowerCase().includes(q) ||
          t.desc.toLowerCase().includes(q),
      );
    }
    return list;
  }, [tasks, courseFilter, search]);

  const dayTasks = useMemo(
    () => baseFiltered.filter((t) => t.date === selectedDate),
    [baseFiltered, selectedDate],
  );

  const todoTasks = dayTasks.filter((t) => t.status === "todo");
  const doneTasks = dayTasks.filter((t) => t.status === "done");
  const daySummary = summarizeDay(dayTasks as unknown as import("../data/history").Task[]);

  function toggleStatus(id: string | number) {
    setTasks((prev) =>
      prev.map((t) =>
        t.id === id
          ? { ...t, status: t.status === "todo" ? "done" : "todo" }
          : t,
      ),
    );
  }

  function deleteTask(id: string | number) {
    if (!window.confirm("确定删除这条任务吗？")) return;
    setTasks((prev) => prev.filter((t) => t.id !== id));
  }

  function openAddModal() {
    setForm(emptyForm(selectedDate, courses[0]?.id ?? "all"));
    setEditingId(null);
    setModalMode("add");
  }

  function openEditModal(task: Task) {
    setForm({
      title: task.title,
      courseId: task.courseId,
      date: task.date,
      time: task.time,
      desc: task.desc,
    });
    setEditingId(task.id);
    setModalMode("edit");
  }

  function closeModal() {
    setModalMode(null);
    setEditingId(null);
  }

  function submitForm() {
    if (!form.title.trim()) return;
    const course = courses.find((c) => c.id === form.courseId);
    const courseName = course?.title ?? form.courseId;

    if (modalMode === "add") {
      const nextId = Math.max(0, ...tasks.map((t) => typeof t.id === "number" ? t.id : 0)) + 1;
      setTasks((prev) => [
        ...prev,
        {
          id: nextId,
          date: form.date,
          time: form.time,
          status: "todo",
          title: form.title.trim(),
          course: courseName,
          courseId: form.courseId,
          desc: form.desc.trim(),
        },
      ]);
    } else if (modalMode === "edit" && editingId !== null) {
      setTasks((prev) =>
        prev.map((t) =>
          t.id === editingId
            ? {
                ...t,
                title: form.title.trim(),
                course: courseName,
                courseId: form.courseId,
                date: form.date,
                time: form.time,
                desc: form.desc.trim(),
              }
            : t,
        ),
      );
    }
    closeModal();
  }

  function goToDay(dateKey: string) {
    setSelectedDate(dateKey);
    setView("day");
  }

  const courseLabel =
    courseFilter === "all"
      ? "全部课程"
      : (courses.find((c) => c.id === courseFilter)?.title ?? courseFilter);

  return (
    <AppShell>
      <div className="history-page history-todo-page">
        {/* 顶部标题区 */}
        <header className="page-header">
          <div>
            <h1>学习记录</h1>
            <p>按时间回顾任务学习、检查结果、阶段变化与方案调整</p>
          </div>
          <div className="page-actions">
            <div className="search-field">
              <Search size={16} />
              <input
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索事件或课程..."
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

        {/* 筛选操作栏 */}
        <div className="history-toolbar">
          <div className="history-view-tabs">
            {(["day", "week", "month"] as ViewMode[]).map((v) => (
              <button
                className={view === v ? "active" : ""}
                key={v}
                onClick={() => setView(v)}
                type="button"
              >
                {v === "day" ? "日" : v === "week" ? "周" : "月"}
              </button>
            ))}
          </div>

          <div className="filter-dropdown">
            <button
              className="filter-trigger"
              onClick={() => setCourseMenuOpen(!courseMenuOpen)}
              type="button"
            >
              <BookOpen size={14} />
              {courseLabel}
              <ChevronDown size={13} />
            </button>
            {courseMenuOpen && (
              <div className="filter-menu">
                <button
                  className={courseFilter === "all" ? "selected" : ""}
                  onClick={() => {
                    setCourseFilter("all");
                    setCourseMenuOpen(false);
                  }}
                  type="button"
                >
                  全部课程
                  {courseFilter === "all" && <Check size={14} />}
                </button>
                {courses.map((c) => (
                  <button
                    className={courseFilter === c.id ? "selected" : ""}
                    key={c.id}
                    onClick={() => {
                      setCourseFilter(c.id);
                      setCourseMenuOpen(false);
                    }}
                    type="button"
                  >
                    {c.title}
                    {courseFilter === c.id && <Check size={14} />}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* 主内容区 */}
        {view === "day" && (
          <DayView
            dateLabel={formatDateLabel(selectedDate)}
            doneCollapsed={doneCollapsed}
            doneTasks={doneTasks}
            onDelete={deleteTask}
            onEdit={openEditModal}
            onToggleDoneCollapse={() => setDoneCollapsed((v) => !v)}
            onToggleStatus={toggleStatus}
            onToggleTodoCollapse={() => setTodoCollapsed((v) => !v)}
            selectedDate={selectedDate}
            summary={daySummary}
            todoCollapsed={todoCollapsed}
            todoTasks={todoTasks}
          />
        )}

        {view === "week" && (
          <WeekView
            onDayClick={goToDay}
            onToggleStatus={toggleStatus}
            selectedDate={selectedDate}
            tasks={baseFiltered}
          />
        )}

        {view === "month" && (
          <MonthView
            onDayClick={goToDay}
            selectedDate={selectedDate}
            tasks={baseFiltered}
          />
        )}

        {/* 新增悬浮按钮 */}
        <button
          className="history-fab"
          onClick={openAddModal}
          type="button"
          aria-label="新增任务"
        >
          <Plus size={22} />
        </button>

        {/* 新增/编辑弹窗 */}
        {modalMode && (
          <TaskModal
            form={form}
            mode={modalMode}
            courses={courses}
            onChange={setForm}
            onClose={closeModal}
            onSubmit={submitForm}
          />
        )}
      </div>
    </AppShell>
  );
}

/* ── 日视图 ───────────────────────────────────────── */

function DayView({
  dateLabel,
  selectedDate,
  todoTasks,
  doneTasks,
  todoCollapsed,
  doneCollapsed,
  onToggleTodoCollapse,
  onToggleDoneCollapse,
  onToggleStatus,
  onEdit,
  onDelete,
  summary,
}: {
  dateLabel: string;
  selectedDate: string;
  todoTasks: Task[];
  doneTasks: Task[];
  todoCollapsed: boolean;
  doneCollapsed: boolean;
  onToggleTodoCollapse: () => void;
  onToggleDoneCollapse: () => void;
  onToggleStatus: (id: string | number) => void;
  onEdit: (task: Task) => void;
  onDelete: (id: string | number) => void;
  summary: { doneCount: number; totalMinutes: number };
}) {
  const isEmpty = todoTasks.length === 0 && doneTasks.length === 0;

  return (
    <div className="history-day-view">
      <div className="history-day-title">
        <strong>{dateLabel}</strong>
        <span>{selectedDate}</span>
      </div>

      {isEmpty ? (
        <div className="history-empty">
          <Search size={28} />
          <strong>这一天没有任务</strong>
          <span>点击右下角 + 添加，或调整筛选条件</span>
        </div>
      ) : (
        <>
          <TaskGroup
            collapsed={todoCollapsed}
            count={todoTasks.length}
            label="待完成"
            onToggleCollapse={onToggleTodoCollapse}
            tasks={todoTasks}
            onDelete={onDelete}
            onEdit={onEdit}
            onToggleStatus={onToggleStatus}
          />
          <TaskGroup
            collapsed={doneCollapsed}
            count={doneTasks.length}
            done
            label="已完成"
            onToggleCollapse={onToggleDoneCollapse}
            tasks={doneTasks}
            onDelete={onDelete}
            onEdit={onEdit}
            onToggleStatus={onToggleStatus}
          />
        </>
      )}

      <footer className="history-day-summary">
        <span>完成任务 <strong>{summary.doneCount}</strong> 项</span>
        <span>总学习时长 <strong>{summary.totalMinutes}</strong> 分钟</span>
      </footer>
    </div>
  );
}

/* ── 任务分组（待完成 / 已完成） ─────────────────── */

function TaskGroup({
  label,
  count,
  tasks,
  collapsed,
  done,
  onToggleCollapse,
  onToggleStatus,
  onEdit,
  onDelete,
}: {
  label: string;
  count: number;
  tasks: Task[];
  collapsed: boolean;
  done?: boolean;
  onToggleCollapse: () => void;
  onToggleStatus: (id: string | number) => void;
  onEdit: (task: Task) => void;
  onDelete: (id: string | number) => void;
}) {
  if (count === 0) return null;

  return (
    <section className={`history-task-group${done ? " is-done-group" : ""}`}>
      <button className="history-group-header" onClick={onToggleCollapse} type="button">
        {collapsed ? <ChevronRight size={16} /> : <ChevronDown size={16} />}
        <span>{label}</span>
        <span className="history-group-count">{count}</span>
      </button>
      {!collapsed && (
        <ul className="history-task-list">
          {tasks.map((task) => (
            <TaskItem
              key={task.id}
              onDelete={onDelete}
              onEdit={onEdit}
              onToggleStatus={onToggleStatus}
              task={task}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

/* ── 单条任务 ───────────────────────────────────── */

function TaskItem({
  task,
  onToggleStatus,
  onEdit,
  onDelete,
}: {
  task: Task;
  onToggleStatus: (id: string | number) => void;
  onEdit: (task: Task) => void;
  onDelete: (id: string | number) => void;
}) {
  const isDone = task.status === "done";

  return (
    <li className={`history-task-item${isDone ? " is-done" : ""}`}>
      <div className="history-task-actions">
        <button onClick={() => onEdit(task)} type="button" aria-label="编辑">
          <Pencil size={13} />
        </button>
        <button onClick={() => onDelete(task.id)} type="button" aria-label="删除">
          <Trash2 size={13} />
        </button>
      </div>

      <div className="history-task-body">
        <div className="history-task-title-row">
          <strong className="history-task-title">{task.title}</strong>
          <span className="history-course-tag">{task.course}</span>
        </div>
        {task.desc && (
          <p className="history-task-desc">
            {task.time && <span className="history-task-time">{task.time}</span>}
            {task.desc}
          </p>
        )}
      </div>

      <StatusCircle
        done={isDone}
        onClick={() => onToggleStatus(task.id)}
      />
    </li>
  );
}

/* ── 状态圆形按钮 ─────────────────────────────────── */

function StatusCircle({ done, onClick }: { done: boolean; onClick: () => void }) {
  return (
    <button
      className={`history-status-circle${done ? " is-done" : ""}`}
      onClick={onClick}
      type="button"
      aria-label={done ? "标记为未完成" : "标记为已完成"}
    >
      {done && <Check size={14} strokeWidth={3} />}
    </button>
  );
}

/* ── 周视图 ───────────────────────────────────────── */

function WeekView({
  selectedDate,
  tasks,
  onDayClick,
  onToggleStatus,
}: {
  selectedDate: string;
  tasks: Task[];
  onDayClick: (dateKey: string) => void;
  onToggleStatus: (id: string | number) => void;
}) {
  const weekDates = getWeekDates(selectedDate);

  return (
    <div className="history-week-view">
      <div className="history-week-grid">
        {weekDates.map((dateKey, index) => {
          const dayTasks = tasks.filter((t) => t.date === dateKey);
          const doneCount = dayTasks.filter((t) => t.status === "done").length;
          const total = dayTasks.length;
          const pct = total === 0 ? 0 : Math.round((doneCount / total) * 100);
          const [, m, d] = dateKey.split("-");

          return (
            <div
              className={`history-week-col${dateKey === selectedDate ? " is-active" : ""}`}
              key={dateKey}
            >
              <button
                className="history-week-col-head"
                onClick={() => onDayClick(dateKey)}
                type="button"
              >
                <span>{formatWeekdayLabel(dateKey, index)}</span>
                <strong>{parseInt(m, 10)}/{parseInt(d, 10)}</strong>
              </button>
              <ul className="history-week-tasks">
                {dayTasks.map((task) => (
                  <li className="history-week-task" key={task.id}>
                    <span className="history-week-task-title">{task.title}</span>
                    <button
                      className={`history-status-dot${task.status === "done" ? " is-done" : ""}`}
                      onClick={() => onToggleStatus(task.id)}
                      type="button"
                      aria-label="切换状态"
                    />
                  </li>
                ))}
              </ul>
              <div className="history-week-progress">
                <div className="history-week-progress-bar" style={{ width: `${pct}%` }} />
              </div>
              <span className="history-week-progress-label">
                {total === 0 ? "无任务" : `${doneCount}/${total} 完成`}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── 月视图 ───────────────────────────────────────── */

function MonthView({
  selectedDate,
  tasks,
  onDayClick,
}: {
  selectedDate: string;
  tasks: Task[];
  onDayClick: (dateKey: string) => void;
}) {
  const grid = getMonthGrid(selectedDate);
  const weekdayHeaders = ["一", "二", "三", "四", "五", "六", "日"];

  return (
    <div className="history-month-view">
      <h2 className="history-month-title">{formatMonthTitle(selectedDate)}</h2>
      <div className="history-month-weekdays">
        {weekdayHeaders.map((w) => (
          <span key={w}>{w}</span>
        ))}
      </div>
      <div className="history-month-grid">
        {grid.map(({ dateKey, inMonth }) => {
          const dayTasks = tasks.filter((t) => t.date === dateKey);
          const total = dayTasks.length;
          const doneCount = dayTasks.filter((t) => t.status === "done").length;
          const rate = total === 0 ? 0 : doneCount / total;
          const [, , d] = dateKey.split("-");

          return (
            <button
              className={`history-month-cell${!inMonth ? " is-outside" : ""}${
                dateKey === selectedDate ? " is-selected" : ""
              }`}
              key={dateKey}
              onClick={() => onDayClick(dateKey)}
              style={{ "--completion": rate } as CSSProperties}
              type="button"
            >
              <span className="history-month-day">{parseInt(d, 10)}</span>
              {total > 0 && (
                <span className="history-month-dots" aria-hidden>
                  {Array.from({ length: Math.min(total, 4) }).map((_, i) => (
                    <span key={i} className="history-month-dot" />
                  ))}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/* ── 新增/编辑弹窗 ───────────────────────────────── */

function TaskModal({
  mode,
  form,
  courses,
  onChange,
  onClose,
  onSubmit,
}: {
  mode: "add" | "edit";
  form: TaskFormState;
  courses: { id: string; title: string }[];
  onChange: (f: TaskFormState) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <div className="history-modal-backdrop" onClick={onClose}>
      <div
        className="history-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="task-modal-title"
      >
        <header className="history-modal-header">
          <h3 id="task-modal-title">{mode === "add" ? "新增任务" : "编辑任务"}</h3>
          <button onClick={onClose} type="button" aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <div className="history-modal-body">
          <label>
            任务名称
            <input
              onChange={(e) => onChange({ ...form, title: e.target.value })}
              placeholder="输入任务名称"
              type="text"
              value={form.title}
            />
          </label>
          <label>
            所属课程
            <select
              onChange={(e) => onChange({ ...form, courseId: e.target.value })}
              value={form.courseId}
            >
              {courses.map((c) => (
                <option key={c.id} value={c.id}>{c.title}</option>
              ))}
            </select>
          </label>
          <div className="history-modal-row">
            <label>
              计划日期
              <input
                onChange={(e) => onChange({ ...form, date: e.target.value })}
                type="date"
                value={form.date}
              />
            </label>
            <label>
              计划时间
              <input
                onChange={(e) => onChange({ ...form, time: e.target.value })}
                type="time"
                value={form.time}
              />
            </label>
          </div>
          <label>
            备注说明
            <textarea
              onChange={(e) => onChange({ ...form, desc: e.target.value })}
              placeholder="学习时长、测验分数、备注等"
              rows={3}
              value={form.desc}
            />
          </label>
        </div>
        <footer className="history-modal-footer">
          <button className="history-modal-cancel" onClick={onClose} type="button">
            取消
          </button>
          <button className="history-modal-submit" onClick={onSubmit} type="button">
            保存
          </button>
        </footer>
      </div>
    </div>
  );
}
