export type HistoryEventType =
  | "task_completed"    // 完成学习任务
  | "task_started"      // 开始学习任务
  | "check_passed"      // 通过检查点
  | "check_failed"      // 检查未通过
  | "stage_changed"     // 阶段切换
  | "plan_adjusted"     // 方案调整
  | "source_added"      // 新增课程资料
  | "source_updated"    // 资料版本更新
  | "quiz_attempted"    // 尝试测验
  | "skill_mastered"    // 技能掌握
  | "course_started"    // 开始课程
  | "course_paused";    // 暂停课程

export interface HistoryEntry {
  id: string;
  type: HistoryEventType;
  date: string;          // "2026-06-13"
  time: string;          // "14:30"
  courseId: string;
  courseName: string;
  courseColor: "teal" | "blue" | "violet";
  title: string;
  detail?: string;
  result?: string;       // "8/10" or "通过" or "阶段2 → 阶段3"
  taskId?: string;
  phaseId?: string;
}

export const historyEntries: HistoryEntry[] = [
  {
    id: "h-1",
    type: "check_passed",
    date: "2026-06-13",
    time: "16:45",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "通过即时检查：直接映射中主存块的位置",
    detail: "首次回答正确，掌握度更新。",
    result: "通过",
    taskId: "cache-mapping",
  },
  {
    id: "h-2",
    type: "task_completed",
    date: "2026-06-13",
    time: "16:30",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "完成任务：Cache 映射方式与命中率",
    detail: "学习时长约 18 分钟，完成即时检查。",
    result: "已完成",
    taskId: "cache-mapping",
  },
  {
    id: "h-3",
    type: "task_started",
    date: "2026-06-13",
    time: "16:10",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "开始任务：Cache 映射方式与命中率",
    detail: "当前阶段：重点突破（第 2 阶段）。",
    taskId: "cache-mapping",
  },
  {
    id: "h-4",
    type: "plan_adjusted",
    date: "2026-06-13",
    time: "10:20",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "方案调整：加强「重点突破」阶段",
    detail: "从「标准」调整为「深入」，新增 2 个扩展任务。",
    result: "标准 → 深入",
  },
  {
    id: "h-5",
    type: "quiz_attempted",
    date: "2026-06-13",
    time: "09:00",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "完成阶段检查：基础梳理小测",
    detail: "覆盖计算机系统概述、数据表示与运算、浮点数运算。",
    result: "8/10",
    phaseId: "foundation",
  },
  {
    id: "h-6",
    type: "stage_changed",
    date: "2026-06-12",
    time: "20:30",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "阶段切换：基础梳理 → 重点突破",
    detail: "已完成 4 个核心任务，阶段检查 8/10 分。系统建议继续推进。",
    result: "阶段1 → 阶段2",
  },
  {
    id: "h-7",
    type: "source_added",
    date: "2026-06-12",
    time: "15:00",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "新增课程资料：2024考研真题-组成原理.pdf",
    detail: "用途标记为「练习与题目」，已加入课程知识作用域。",
  },
  {
    id: "h-8",
    type: "task_completed",
    date: "2026-06-12",
    time: "14:20",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "完成任务：Cache 基本概念与局部性原理",
    detail: "学习时长约 15 分钟。",
    result: "已完成",
    taskId: "cache-locality",
  },
  {
    id: "h-9",
    type: "skill_mastered",
    date: "2026-06-12",
    time: "11:00",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "掌握主题：计算机系统层次结构",
    detail: "通过多维证据确认掌握，置信度 92%。",
    result: "已掌握",
  },
  {
    id: "h-10",
    type: "course_started",
    date: "2026-06-11",
    time: "18:00",
    courseId: "machine-learning",
    courseName: "机器学习基础",
    courseColor: "blue",
    title: "开始课程：机器学习基础",
    detail: "学习目标：系统掌握机器学习核心算法。当前处于第 1 阶段「基础梳理」。",
  },
  {
    id: "h-11",
    type: "course_started",
    date: "2026-06-10",
    time: "20:00",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "开始课程：计算机组成原理",
    detail: "已确认学习需求与阶段方案，正式开始学习。",
  },
  {
    id: "h-12",
    type: "plan_adjusted",
    date: "2026-06-10",
    time: "19:30",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "确认学习方案",
    detail: "4 阶段方案已确认：基础梳理 → 重点突破 → 综合应用 → 检验巩固。",
  },
  {
    id: "h-13",
    type: "source_added",
    date: "2026-06-10",
    time: "16:00",
    courseId: "machine-learning",
    courseName: "机器学习基础",
    courseColor: "blue",
    title: "新增课程资料：机器学习-西瓜书-周志华.pdf",
    detail: "用途标记为「教材」，已加入课程知识作用域。",
  },
  {
    id: "h-14",
    type: "quiz_attempted",
    date: "2026-06-09",
    time: "15:30",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "完成诊断测试",
    detail: "初始诊断，评估当前基础水平。",
    result: "65/100",
  },
  {
    id: "h-15",
    type: "source_updated",
    date: "2026-06-08",
    time: "10:00",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "资料版本更新：CSAPP 第6章 存储器层次结构.pdf",
    detail: "检测到扫描质量更好的版本，v1 → v2。解析状态：已可使用。",
    result: "v1 → v2",
  },
  {
    id: "h-16",
    type: "course_paused",
    date: "2026-06-07",
    time: "12:00",
    courseId: "machine-learning",
    courseName: "机器学习基础",
    courseColor: "blue",
    title: "暂停课程：机器学习基础",
    detail: "用户主动暂停。已完成阶段1部分内容，进度保留。",
  },
  {
    id: "h-17",
    type: "check_failed",
    date: "2026-06-06",
    time: "17:00",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "检查未通过：浮点数运算",
    detail: "建议回顾 IEEE 754 标准相关内容后重试。",
    result: "未通过",
  },
  {
    id: "h-18",
    type: "task_completed",
    date: "2026-06-05",
    time: "14:30",
    courseId: "computer-architecture",
    courseName: "计算机组成原理",
    courseColor: "teal",
    title: "完成任务：数据的表示与运算",
    detail: "学习时长约 22 分钟。",
    result: "已完成",
  },
];

export const typeLabels: Record<HistoryEventType, string> = {
  task_completed: "完成任务",
  task_started: "开始任务",
  check_passed: "检查通过",
  check_failed: "检查未通过",
  stage_changed: "阶段切换",
  plan_adjusted: "方案调整",
  source_added: "新增资料",
  source_updated: "资料更新",
  quiz_attempted: "完成测验",
  skill_mastered: "技能掌握",
  course_started: "开始课程",
  course_paused: "暂停课程",
};

/** Group entries by date for timeline rendering */
export function groupByDate(entries: HistoryEntry[]): Map<string, HistoryEntry[]> {
  const map = new Map<string, HistoryEntry[]>();
  for (const e of entries) {
    const list = map.get(e.date) ?? [];
    list.push(e);
    map.set(e.date, list);
  }
  return map;
}

/** Format date label */
export function formatDateLabel(dateStr: string): string {
  const today = "2026-06-13"; // mock "today"
  if (dateStr === today) return "今天";
  const yesterday = "2026-06-12";
  if (dateStr === yesterday) return "昨天";
  // return M月D日
  const [, m, d] = dateStr.split("-");
  return `${parseInt(m, 10)}月${parseInt(d, 10)}日`;
}
