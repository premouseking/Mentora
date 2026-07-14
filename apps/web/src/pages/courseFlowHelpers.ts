import type { CourseSessionUpdatePayload, InquiryEntry } from "../services/courseApi";

export interface ProfileItemLike {
  key: string;
  title: string;
  value: string;
}

export interface PhaseLike {
  id: string;
  title: string;
  objective: string;
}

const PROFILE_FIELD_MAP = {
  goal: "goal",
  level: "level",
  pace: "pace",
  timeBudget: "time_budget",
  deadline: "deadline",
  school: "school",
} as const;

export function profileItemsToSessionUpdate(items: ProfileItemLike[]): CourseSessionUpdatePayload {
  const data: CourseSessionUpdatePayload = {};
  for (const item of items) {
    const field = PROFILE_FIELD_MAP[item.key as keyof typeof PROFILE_FIELD_MAP];
    if (!field) continue;
    const value = item.value.trim();
    switch (field) {
      case "goal":
        data.goal = value;
        break;
      case "level":
        data.level = value;
        break;
      case "pace":
        data.pace = value;
        break;
      case "time_budget":
        data.time_budget = value;
        break;
      case "deadline":
        data.deadline = value || null;
        break;
      case "school":
        data.school = value;
        break;
    }
  }

  const inquiryItems = items.filter((item) => item.key.startsWith("inquiry_"));
  if (inquiryItems.length > 0) {
    data.inquiry_history = inquiryItems.map((item) => ({
      question: item.title,
      answer: item.value.trim(),
    } satisfies InquiryEntry));
  }

  return data;
}

export function describePlanPhaseChanges(original: PhaseLike[], edited: PhaseLike[]): string {
  const parts: string[] = [];
  const originalIds = original.map((p) => p.id);
  const editedIds = edited.map((p) => p.id);

  if (editedIds.join("|") !== originalIds.join("|")) {
    parts.push(`阶段顺序调整为：${edited.map((p) => p.title).join("、")}`);
  }

  const originalIdSet = new Set(originalIds);
  const additions = edited.filter((p) => !originalIdSet.has(p.id));
  if (additions.length > 0) {
    parts.push(`新增阶段：${additions.map((p) => `${p.title}（${p.objective}）`).join("、")}`);
  }

  return parts.length > 0 ? `${parts.join("；")}。` : "";
}

export function buildAdjustmentSupplement(
  adjustmentText: string,
  planAdjustmentSummary: string,
): Record<string, string> {
  const supplement: Record<string, string> = {};
  const text = adjustmentText.trim();
  const summary = planAdjustmentSummary.trim();
  if (text) supplement["用户调整要求"] = text;
  if (summary) supplement["计划结构调整"] = summary;
  return supplement;
}

export function resolvePlanSessionId(routeId: string, course: { session_id: string } | null): string {
  return course?.session_id || routeId;
}

/* ── 学习计划任务展示 ── */

export interface TaskLike {
  task_type: string;
  title?: string;
  knowledge_point?: string;
  delivery_mode?: string;
}

/** 任务短卡上显示的类型文案 */
export const TASK_CARD_LABEL: Record<string, string> = {
  lecture: "知识点学习",
  exercise: "练习",
  review: "复习",
  project: "专题突破",
};

export function getTaskCardLabel(taskType: string): string {
  return TASK_CARD_LABEL[taskType] ?? taskType;
}

/** 同一章节内若存在重复任务类型，短卡追加序号以便区分 */
export function getTaskCardLabelForUnit(tasks: TaskLike[], task: TaskLike, index: number): string {
  const base = getTaskCardLabel(task.task_type);
  const sameTypeCount = tasks.filter((t) => t.task_type === task.task_type).length;
  if (sameTypeCount <= 1) return base;
  const sameTypeIndex = tasks.slice(0, index + 1).filter((t) => t.task_type === task.task_type).length;
  if (sameTypeIndex === 1) return base;
  return `${base} ${sameTypeIndex}`;
}

/** 详情区展示的完整任务标题 */
export function getTaskDetailTitle(task: TaskLike, index: number): string {
  const title = task.title?.trim();
  if (title) return title;
  const knowledgePoint = task.knowledge_point?.trim();
  if (task.task_type === "lecture" || task.task_type === "project") {
    return knowledgePoint || `${getTaskCardLabel(task.task_type)} ${index + 1}`;
  }
  return `${getTaskCardLabel(task.task_type)} ${index + 1}`;
}

/** 详情区「任务类型」字段 */
export function getTaskTypeDetailLabel(taskType: string): string {
  return getTaskCardLabel(taskType);
}

const DELIVERY_MODE_LABEL: Record<string, string> = {
  text: "文本学习",
  interactive: "互动练习",
  video: "视频",
  self_paced: "自学",
  live: "直播",
  hybrid: "混合",
};

export function getTaskDeliveryLabel(taskType: string, deliveryMode?: string): string {
  if (taskType === "exercise") return "完成练习";
  if (taskType === "lecture") return "自主确认";
  if (deliveryMode && DELIVERY_MODE_LABEL[deliveryMode]) {
    return DELIVERY_MODE_LABEL[deliveryMode];
  }
  return deliveryMode ?? "—";
}

export function summarizeUnitTasks(tasks: TaskLike[], estimatedMinutes?: number): string {
  const typeSet = [...new Set(tasks.map((t) => getTaskCardLabel(t.task_type)))];
  const typesText = typeSet.length > 0 ? typeSet.join("、") : "无";
  const minutesPart =
    estimatedMinutes !== undefined && estimatedMinutes > 0
      ? `，预计用时 ${estimatedMinutes >= 60 ? `${Math.round((estimatedMinutes / 60) * 10) / 10} 小时` : `${estimatedMinutes} 分钟`}`
      : "";
  return `本章节包含 ${tasks.length} 个学习任务，涵盖${typesText}等类型${minutesPart}。`;
}

export function buildTaskDetailSummary(
  task: TaskLike,
  unitTitle: string,
  index: number,
  estimatedMinutes: number,
): string {
  const title = getTaskDetailTitle(task, index);
  const chapter = unitTitle || "本章节";
  if (task.task_type === "exercise") {
    return `通过完成练习巩固「${chapter}」的相关内容，预计用时 ${estimatedMinutes} 分钟。`;
  }
  if (task.task_type === "lecture") {
    return `学习「${title}」，理解其在「${chapter}」中的应用，预计用时 ${estimatedMinutes} 分钟。`;
  }
  if (task.task_type === "review") {
    return `复盘「${chapter}」中的关键内容，预计用时 ${estimatedMinutes} 分钟。`;
  }
  return `通过专题实践完成「${title}」，预计用时 ${estimatedMinutes} 分钟。`;
}

export type TaskLearningMode = "content" | "exercise";

/** 按 task_type 决定学习模式：练习走刷题，其余走内容学习页。 */
export function resolveTaskLearningMode(taskType: string): TaskLearningMode {
  return taskType === "exercise" ? "exercise" : "content";
}

/** 任务「开始学习」入口路径（模板 ID 与物化任务 ID 均可）。 */
export function resolveTaskStartPath(courseId: string, taskId: string): string {
  return `/courses/${encodeURIComponent(courseId)}/tasks/${encodeURIComponent(taskId)}`;
}

/** 从任务参考资料跳转到课程工作区并定位 EvidenceUnit。 */
export function buildWorkspaceEvidencePath(
  courseId: string,
  sourceVersionId: string,
  evidenceId: string,
): string {
  const params = new URLSearchParams({ sourceVersionId, evidenceId });
  return `/courses/${encodeURIComponent(courseId)}?${params.toString()}`;
}
