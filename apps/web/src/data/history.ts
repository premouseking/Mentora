/**
 * 学习记录 — Todo 任务数据模型
 * 全局仅两种状态：todo（未完成） / done（已完成）
 */

export type TaskStatus = "todo" | "done";

export interface Task {
  id: number;
  date: string; // 计划/完成日期，格式为 YYYY-MM-DD
  time: string; // 计划/完成时间，如 "16:45"
  status: TaskStatus;
  title: string;
  course: string;
  courseId: string;
  desc: string;
  /** 学习时长（分钟），用于日汇总；系统记录可写入 */
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

export const initialTasks: Task[] = [
  // —— 今天 · 待完成 ——
  {
    id: 1,
    date: TODAY_DATE_KEY,
    time: "19:00",
    status: "todo",
    title: "复习 Cache 映射方式与命中率",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "计划学习约 20 分钟，重点回顾直接映射与组相联。",
    durationMinutes: 20,
  },
  {
    id: 2,
    date: TODAY_DATE_KEY,
    time: "20:30",
    status: "todo",
    title: "线性回归为什么有效",
    course: "机器学习基础",
    courseId: "machine-learning",
    desc: "阶段 1 下一任务，预计 22 分钟。",
    durationMinutes: 22,
  },
  {
    id: 3,
    date: TODAY_DATE_KEY,
    time: "21:00",
    status: "todo",
    title: "整理本周错题笔记",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "将浮点数运算相关错题归档到资源库。",
  },
  // —— 今天 · 已完成（含系统自动记录） ——
  {
    id: 4,
    date: TODAY_DATE_KEY,
    time: "16:45",
    status: "done",
    title: "通过即时检查：直接映射中主存块的位置",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "首次回答正确，掌握度已更新。",
    durationMinutes: 8,
  },
  {
    id: 5,
    date: TODAY_DATE_KEY,
    time: "16:30",
    status: "done",
    title: "Cache 映射方式与命中率",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "学习时长约 18 分钟，完成即时检查。",
    durationMinutes: 18,
  },
  {
    id: 6,
    date: TODAY_DATE_KEY,
    time: "10:20",
    status: "done",
    title: "方案调整：加强「重点突破」阶段",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "从「标准」调整为「深入」，新增 2 个扩展任务。",
  },
  {
    id: 7,
    date: TODAY_DATE_KEY,
    time: "09:00",
    status: "done",
    title: "完成阶段检查：基础梳理小测",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "覆盖计算机系统概述、数据表示与运算、浮点数运算。测验得分 8/10。",
    durationMinutes: 25,
  },
  // —— 昨天 ——
  {
    id: 8,
    date: offsetDateKey(TODAY_DATE_KEY, -1),
    time: "20:30",
    status: "done",
    title: "阶段切换：基础梳理 → 重点突破",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "已完成 4 个核心任务，阶段检查 8/10 分，系统建议继续推进。",
  },
  {
    id: 9,
    date: offsetDateKey(TODAY_DATE_KEY, -1),
    time: "14:20",
    status: "done",
    title: "Cache 基本概念与局部性原理",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "学习时长约 15 分钟。",
    durationMinutes: 15,
  },
  {
    id: 10,
    date: offsetDateKey(TODAY_DATE_KEY, -1),
    time: "11:00",
    status: "done",
    title: "掌握主题：计算机系统层次结构",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "通过多维证据确认掌握，置信度 92%。",
  },
  // —— 本周其他日 ——
  {
    id: 11,
    date: offsetDateKey(TODAY_DATE_KEY, -2),
    time: "18:00",
    status: "done",
    title: "开始课程：机器学习基础",
    course: "机器学习基础",
    courseId: "machine-learning",
    desc: "学习目标：系统掌握机器学习核心算法，当前处于第 1 阶段。",
  },
  {
    id: 12,
    date: offsetDateKey(TODAY_DATE_KEY, -3),
    time: "20:00",
    status: "done",
    title: "开始课程：计算机组成原理",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "已确认学习需求与阶段方案，正式开始学习。",
  },
  {
    id: 13,
    date: offsetDateKey(TODAY_DATE_KEY, -3),
    time: "15:30",
    status: "done",
    title: "完成诊断测试",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "初始诊断评估当前基础水平，得分 65/100。",
    durationMinutes: 40,
  },
  {
    id: 14,
    date: offsetDateKey(TODAY_DATE_KEY, -4),
    time: "14:30",
    status: "done",
    title: "数据的表示与运算",
    course: "计算机组成原理",
    courseId: "computer-architecture",
    desc: "学习时长约 22 分钟。",
    durationMinutes: 22,
  },
  {
    id: 15,
    date: offsetDateKey(TODAY_DATE_KEY, -5),
    time: "16:00",
    status: "todo",
    title: "检查阶段安排",
    course: "数据结构与算法",
    courseId: "data-structures",
    desc: "AI 已生成 4 个学习阶段，待确认方案。",
  },
];

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

export function formatWeekdayLabel(dateKey: string, index: number): string {
  return WEEKDAY_LABELS[index];
}

/** 月历网格：含上月尾、下月头，固定 6 行 × 7 列 */
export function getMonthGrid(monthAnchor: string): { dateKey: string; inMonth: boolean }[] {
  const anchor = parseDateKey(monthAnchor);
  const year = anchor.getFullYear();
  const month = anchor.getMonth();
  const first = new Date(year, month, 1);
  const startDay = first.getDay();
  const mondayOffset = startDay === 0 ? -6 : 1 - startDay;
  const gridStart = new Date(year, month, 1 + mondayOffset);

  return Array.from({ length: 42 }, (_, i) => {
    const d = new Date(gridStart);
    d.setDate(gridStart.getDate() + i);
    return {
      dateKey: toDateKey(d),
      inMonth: d.getMonth() === month,
    };
  });
}

export function formatMonthTitle(dateKey: string): string {
  const d = parseDateKey(dateKey);
  return `${d.getFullYear()}年${d.getMonth() + 1}月`;
}

/** 当日完成任务数与总学习时长 */
export function summarizeDay(tasks: Task[]): { doneCount: number; totalMinutes: number } {
  const done = tasks.filter((t) => t.status === "done");
  const totalMinutes = done.reduce((sum, t) => sum + (t.durationMinutes ?? 0), 0);
  return { doneCount: done.length, totalMinutes };
}
