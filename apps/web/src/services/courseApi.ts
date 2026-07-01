/**
 * 建课流程与课程运行时 API 服务层。
 *
 * - creation：/api/courses/sessions/*（建课期，session_id）
 * - runtime：/api/courses/{course_id}/*（学习期）
 *
 * @module services/courseApi
 */

import { apiClient, ApiError } from "./client";

const SESSION_BASE = "/api/courses/sessions";
const COURSE_BASE = "/api/courses";

/* ── 类型 ── */

export { ApiError };

export interface SessionResponse {
  id: string;
  goal: string;
  title: string;
  status: string;
}

export interface SessionDetail extends SessionResponse {
  level: string;
  pace: string;
  time_budget: string;
  school: string;
  deadline: string | null;
  inquiry_history: InquiryEntry[];
  created_at: string;
  updated_at: string;
}

export interface InquiryEntry {
  question: string;
  answer: string;
}

export interface InquiryQuestion {
  text: string;
  type: "single_choice" | "multi_choice" | "free_text";
  options: string[];
  guidance: string;
}

export interface InquiryResponse {
  ready: boolean;
  questions?: InquiryQuestion[];
  summary?: string;
}

export interface PlanPhaseDraft {
  name: string;
  goal: string;
  share: number;
  tasks: string[];
}

export interface PlanResponse {
  title: string;
  phases: PlanPhaseDraft[];
  revision_id: string;
}

export interface CourseSessionListItem {
  id: string;
  course_id: string | null;
  session_id: string;
  goal: string;
  title: string;
  status: string;
  level: string;
  pace: string;
  time_budget: string;
  school: string;
  deadline: string | null;
  current_phase: string | null;
  next_task: string | null;
  created_at: string;
  updated_at: string;
  last_studied_at: string | null;
}

/* ── Session CRUD（建课期）── */

export async function listCourseSessions(
  signal?: AbortSignal,
): Promise<CourseSessionListItem[]> {
  return apiClient.get<CourseSessionListItem[]>(`${SESSION_BASE}/`, { signal });
}

export async function createCourseSession(
  goal: string,
  signal?: AbortSignal,
): Promise<SessionResponse> {
  return apiClient.post<SessionResponse>(`${SESSION_BASE}/`, { goal }, { signal });
}

export async function getCourseSession(
  id: string,
  signal?: AbortSignal,
): Promise<SessionDetail> {
  return apiClient.get<SessionDetail>(`${SESSION_BASE}/${encodeURIComponent(id)}/`, { signal });
}

export async function updateCourseSession(
  id: string,
  data: {
    goal?: string;
    level?: string;
    pace?: string;
    time_budget?: string;
    school?: string;
    deadline?: string | null;
    last_studied_at?: string;
  },
  signal?: AbortSignal,
): Promise<{ status: string }> {
  return apiClient.patch<{ status: string }>(
    `${SESSION_BASE}/${encodeURIComponent(id)}/update/`,
    data,
    { signal },
  );
}

/* ── Inquiry 追问 ── */

export async function inquiryNext(
  id: string,
  answer?: string,
  signal?: AbortSignal,
): Promise<InquiryResponse> {
  const body = answer ? { answer } : {};
  return apiClient.post<InquiryResponse>(`${SESSION_BASE}/${encodeURIComponent(id)}/inquiry/`, body, {
    signal,
    timeoutMs: 30_000,
  });
}

/* ── Plan 方案生成（建课期 session）── */

export async function generatePlan(
  sessionId: string,
  signal?: AbortSignal,
): Promise<PlanResponse> {
  return apiClient.post<PlanResponse>(
    `${SESSION_BASE}/${encodeURIComponent(sessionId)}/plan/`,
    undefined,
    { signal, timeoutMs: 90_000 },
  );
}

export async function getSessionActivePlan(
  sessionId: string,
  signal?: AbortSignal,
): Promise<ActivePlan> {
  return apiClient.get<ActivePlan>(
    `${SESSION_BASE}/${encodeURIComponent(sessionId)}/plan/`,
    { signal },
  );
}

/* ── Active plan 类型 ── */

export interface PlanTask {
  id: string;
  task_type: string;
  delivery_mode: string;
  estimated_minutes: number;
  required: boolean;
}

export interface PlanUnit {
  id: string;
  title?: string;
  position: number;
  topic_id: string | null;
  target_depth: string;
  estimated_minutes: number;
  prerequisite_unit_ids: string[];
  priority: number;
  tasks: PlanTask[];
}

export interface PlanPhase {
  id: string;
  position: number;
  title: string;
  objective: string;
  estimated_minutes: number;
  units: PlanUnit[];
}

export interface ActivePlan {
  plan_id: string;
  revision_id: string;
  status: string;
  feasibility_status: string;
  profile_revision_id: string;
  phases: PlanPhase[];
}

/** 学习期：按 course_id 查询活跃方案 */
export async function getActivePlan(
  courseId: string,
  signal?: AbortSignal,
): Promise<ActivePlan> {
  return apiClient.get<ActivePlan>(
    `${COURSE_BASE}/${encodeURIComponent(courseId)}/plan/`,
    { signal },
  );
}

/** 学习期：更新最近学习时间 */
export async function updateCourseActivity(
  courseId: string,
  lastStudiedAt: string,
  signal?: AbortSignal,
): Promise<{ status: string }> {
  return apiClient.patch<{ status: string }>(
    `${COURSE_BASE}/${encodeURIComponent(courseId)}/activity/`,
    { last_studied_at: lastStudiedAt },
    { signal },
  );
}

/* ── 删除 ── */

export async function deleteCourseSession(sessionId: string): Promise<void> {
  await apiClient.delete(`${SESSION_BASE}/${encodeURIComponent(sessionId)}/delete/`);
}

/* ── 开始学习 ── */

export async function startCourse(
  sessionId: string,
): Promise<{ status: string; revision_id: string; course_id: string }> {
  return apiClient.post<{ status: string; revision_id: string; course_id: string }>(
    `${SESSION_BASE}/${encodeURIComponent(sessionId)}/start/`,
  );
}
