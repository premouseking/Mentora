/** 建课流程浏览器侧 session 存储键（与 SetupPages / ConfirmPlanPage 共用） */

const SESSION_ID_KEY = "mentora-session-id";
const GOAL_KEY = "mentora-course-goal";
const STARTED_KEY = "mentora-course-started";

export function getStoredCourseSessionId(): string | null {
  return sessionStorage.getItem(SESSION_ID_KEY);
}

export function setStoredCourseSessionId(id: string): void {
  sessionStorage.setItem(SESSION_ID_KEY, id);
}

export function setStoredCourseGoal(goal: string): void {
  sessionStorage.setItem(GOAL_KEY, goal);
}

export function getStoredCourseGoal(): string | null {
  return sessionStorage.getItem(GOAL_KEY);
}

/** 开始新建课程前调用，避免复用上一次的 session / 方案状态 */
export function resetCourseCreationStorage(): void {
  sessionStorage.removeItem(SESSION_ID_KEY);
  sessionStorage.removeItem(GOAL_KEY);
  sessionStorage.removeItem(STARTED_KEY);
}

export function markCourseStarted(): void {
  sessionStorage.setItem(STARTED_KEY, "true");
}

/** 建课完成后跳回列表页时读取并清除刷新标记 */
export function consumeCourseStartedFlag(): boolean {
  const started = sessionStorage.getItem(STARTED_KEY);
  if (!started) return false;
  sessionStorage.removeItem(STARTED_KEY);
  return true;
}
