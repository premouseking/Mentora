/**
 * 学习记录 — 日期/视图工具函数。
 *
 * 历史数据由 /api/history/ 提供，本文件仅保留 UI 工具函数。
 *
 * @module data/history
 */

export type TaskStatus = "todo" | "done";

export interface Task {
  id: number;
  date: string;
  time: string;
  status: TaskStatus;
  title: string;
  course: string;
  courseId: string;
  desc: string;
  durationMinutes?: number;
}

/** 将 YYYY-MM-DD 解析为本地 Date */
export function parseDateKey(key: string): Date {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** 格式化为 YYYY-MM-DD */
export function toDateKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

export function offsetDateKey(anchorDate: string, offsetDays: number): string {
  const anchor = parseDateKey(anchorDate);
  anchor.setDate(anchor.getDate() + offsetDays);
  return toDateKey(anchor);
}

export const TODAY_DATE_KEY = toDateKey(new Date());

/** 日视图标题：今天 / 昨天 / M月D日 */
export function formatDateLabel(dateStr: string, today = TODAY_DATE_KEY): string {
  if (dateStr === today) return "今天";
  const todayDate = parseDateKey(today);
  const yesterday = toDateKey(
    new Date(todayDate.getFullYear(), todayDate.getMonth(), todayDate.getDate() - 1),
  );
  if (dateStr === yesterday) return "昨天";
  const [, m, d] = dateStr.split("-");
  return `${parseInt(m, 10)}月${parseInt(d, 10)}日`;
}

/** 获取某日所在周的周一至周日（周一为首列） */
export function getWeekDates(anchorDate: string): string[] {
  const date = parseDateKey(anchorDate);
  const day = date.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  const monday = new Date(date);
  monday.setDate(date.getDate() + mondayOffset);
  return Array.from({ length: 7 }, (_, i) => {
    const d = new Date(monday);
    d.setDate(monday.getDate() + i);
    return toDateKey(d);
  });
}

const WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export function formatWeekdayLabel(dateStr: string, dayIndex: number): string {
  return WEEKDAY_LABELS[dayIndex];
}

export function getRelativeDate(daysAhead: number): Date {
  const d = new Date();
  d.setDate(d.getDate() + daysAhead);
  return d;
}

/** 月视图网格 */
export function getMonthGrid(anchorDate: string): { dateKey: string; inMonth: boolean }[] {
  const anchor = parseDateKey(anchorDate);
  const year = anchor.getFullYear();
  const month = anchor.getMonth();

  const firstOfMonth = new Date(year, month, 1);
  const startDay = firstOfMonth.getDay();
  const mondayOffset = startDay === 0 ? -6 : 1 - startDay;

  const gridStart = new Date(year, month, 1);
  gridStart.setDate(gridStart.getDate() + mondayOffset);

  const cells: { dateKey: string; inMonth: boolean }[] = [];
  for (let i = 0; i < 42; i++) {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    cells.push({
      dateKey: toDateKey(d),
      inMonth: d.getMonth() === month,
    });
  }
  return cells;
}

export function formatMonthTitle(anchorDate: string): string {
  const [y, m] = anchorDate.split("-");
  return `${y}年${parseInt(m, 10)}月`;
}

/** 日汇总 */
export function summarizeDay(tasks: Task[]): { doneCount: number; totalMinutes: number } {
  const doneTasks = tasks.filter((t) => t.status === "done");
  const totalMinutes = doneTasks.reduce((sum, t) => sum + (t.durationMinutes ?? 0), 0);
  return { doneCount: doneTasks.length, totalMinutes };
}
