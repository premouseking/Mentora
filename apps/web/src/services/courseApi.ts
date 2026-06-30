/**
 * 建课流程 API 服务层。
 *
 * 封装 /api/courses/sessions/ 下全部端点。
 *
 * @module services/courseApi
 */

import { apiClient, ApiError } from "./client";

const BASE = "/api/courses/sessions";

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

export interface PlanPhase {
  name: string;
  goal: string;
  share: number;
  tasks: string[];
}

export interface PlanResponse {
  title: string;
  phases: PlanPhase[];
  revision_id: string;
}

export interface CourseSessionListItem {
  id: string;
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

/* ── Session CRUD ── */

export async function listCourseSessions(
  signal?: AbortSignal,
): Promise<CourseSessionListItem[]> {
  return apiClient.get<CourseSessionListItem[]>(`${BASE}/`, { signal });
}

export async function createCourseSession(
  goal: string,
  signal?: AbortSignal,
): Promise<SessionResponse> {
  return apiClient.post<SessionResponse>(`${BASE}/`, { goal }, { signal });
}

export async function getCourseSession(
  id: string,
  signal?: AbortSignal,
): Promise<SessionDetail> {
  return apiClient.get<SessionDetail>(`${BASE}/${encodeURIComponent(id)}/`, { signal });
}

export async function updateCourseSession(
  id: string,
  data: { level?: string; pace?: string; time_budget?: string; school?: string; deadline?: string | null; last_studied_at?: string },
  signal?: AbortSignal,
): Promise<{ status: string }> {
  return apiClient.patch<{ status: string }>(`${BASE}/${encodeURIComponent(id)}/update/`, data, { signal });
}

/* ── Inquiry 追问 ── */

export async function inquiryNext(
  id: string,
  answer?: string,
  signal?: AbortSignal,
): Promise<InquiryResponse> {
  const body = answer ? { answer } : {};
  return apiClient.post<InquiryResponse>(`${BASE}/${encodeURIComponent(id)}/inquiry/`, body, {
    signal,
    timeoutMs: 30_000,
  });
}

/* ── Plan 方案生成 ── */

export async function generatePlan(
  id: string,
  signal?: AbortSignal,
): Promise<PlanResponse> {
  return apiClient.post<PlanResponse>(`${BASE}/${encodeURIComponent(id)}/plan/`, undefined, {
    signal,
    timeoutMs: 90_000,
  });
}

/* ── Active plan 方案查询 ── */

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

export async function getActivePlan(
  id: string,
  signal?: AbortSignal,
): Promise<ActivePlan> {
  return apiClient.get<ActivePlan>(`${BASE}/${encodeURIComponent(id)}/plan/`, { signal });
}

/* ── 删除 ── */

export async function deleteCourseSession(id: string): Promise<void> {
  await apiClient.delete(`${BASE}/${encodeURIComponent(id)}/delete/`);
}

/* ── 开始学习 ── */

export async function startCourse(id: string): Promise<{ status: string; revision_id: string }> {
  return apiClient.post<{ status: string; revision_id: string }>(`${BASE}/${encodeURIComponent(id)}/start/`);
}
