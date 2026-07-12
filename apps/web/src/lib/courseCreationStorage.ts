/** 建课流程 sessionStorage 键，避免跨课程复用旧会话。 */
export const COURSE_SESSION_ID_KEY = "mentora-session-id";
export const COURSE_GOAL_KEY = "mentora-course-goal";

export function clearCourseCreationStorage(): void {
  sessionStorage.removeItem(COURSE_SESSION_ID_KEY);
  sessionStorage.removeItem(COURSE_GOAL_KEY);
}

export function readStoredCourseGoal(): string {
  return sessionStorage.getItem(COURSE_GOAL_KEY)?.trim() ?? "";
}

/** 学习目标变化时必须新建 session，避免旧追问/资料作用域污染新课程。 */
export function shouldCreateFreshCourseSession(
  existingSessionId: string | null | undefined,
  storedGoal: string,
  nextGoal: string,
): boolean {
  if (!existingSessionId) return true;
  const previous = storedGoal.trim();
  const next = nextGoal.trim();
  if (!previous) return false;
  return previous !== next;
}
