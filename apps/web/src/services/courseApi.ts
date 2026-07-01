/**
 * 建课流程 API 服务层。
 *
 * 封装 /api/courses/sessions/ 下全部端点。
 *
 * @module services/courseApi
 */

import { apiClient, ApiError, type CoverageGap } from "./client";

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
  profile_supplement: Record<string, string>;
  inquiry_history: InquiryEntry[];
  source_version_ids?: string[];
  sources?: SessionSourceItem[];
  created_at: string;
  updated_at: string;
}

export interface SessionSourceItem {
  sourceVersionId: string;
  displayTitle: string;
  processingStatus?: string;
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

export interface GeneratedPlanPhase {
  name: string;
  goal: string;
  share: number;
  units?: unknown[];
  tasks?: string[];
}

export interface PlanResponse {
  title: string;
  phases: GeneratedPlanPhase[];
  revision_id: string;
  coverage_gaps?: CoverageGap[];
}

export type { CoverageGap };

export interface CourseSessionListItem {
  id: string;
  course_id: string | null;
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

export interface CourseSessionUpdatePayload {
  goal?: string;
  level?: string;
  pace?: string;
  time_budget?: string;
  school?: string;
  deadline?: string | null;
  last_studied_at?: string;
  profile_supplement?: Record<string, string>;
  inquiry_history?: InquiryEntry[];
}

export interface CourseDetail {
  course_id: string;
  session_id: string;
  goal: string;
  level: string;
  pace: string;
  school: string;
  status: string;
  plan_revision_id: string | null;
  source_version_ids: string[] | null;
  created_at: string;
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
  data: CourseSessionUpdatePayload,
  signal?: AbortSignal,
): Promise<{ status: string }> {
  return apiClient.patch<{ status: string }>(`${BASE}/${encodeURIComponent(id)}/update/`, data, { signal });
}

export interface CoveragePreview {
  sufficient: boolean;
  gaps: CoverageGap[];
  sources: Array<{ sourceVersionId: string; displayTitle: string }>;
}

export async function previewSourceCoverage(
  id: string,
  sourceVersionIds: string[],
  signal?: AbortSignal,
): Promise<CoveragePreview> {
  return apiClient.post<CoveragePreview>(
    `${BASE}/${encodeURIComponent(id)}/sources/coverage-preview/`,
    { source_version_ids: sourceVersionIds },
    { signal },
  );
}

export async function fetchSessionSources(
  id: string,
  signal?: AbortSignal,
): Promise<{ items: SessionSourceItem[]; count: number }> {
  return apiClient.get<{ items: SessionSourceItem[]; count: number }>(
    `${BASE}/${encodeURIComponent(id)}/sources/`,
    { signal },
  );
}

export async function bindSessionSources(
  id: string,
  sourceVersionIds: string[],
  signal?: AbortSignal,
): Promise<{ status: string; count: number }> {
  return apiClient.post<{ status: string; count: number }>(
    `${BASE}/${encodeURIComponent(id)}/sources/`,
    { source_version_ids: sourceVersionIds },
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
  return apiClient.post<InquiryResponse>(`${BASE}/${encodeURIComponent(id)}/inquiry/`, body, {
    signal,
    timeoutMs: 90_000,
  });
}

/* ── Plan 方案生成 ── */

/** 学习方案生成可能含大量资料上下文，需与 LLM_STRUCTURED_TIMEOUT 对齐 */
export const PLAN_GENERATION_TIMEOUT_MS = 300_000;

export async function generatePlan(
  id: string,
  options?: {
    allow_partial_plan?: boolean;
    signal?: AbortSignal;
  },
): Promise<PlanResponse> {
  const { allow_partial_plan, signal } = options ?? {};
  return apiClient.post<PlanResponse>(
    `${BASE}/${encodeURIComponent(id)}/plan/`,
    allow_partial_plan ? { allow_partial_plan: true } : {},
    {
      signal,
      timeoutMs: PLAN_GENERATION_TIMEOUT_MS,
    },
  );
}

/* ── Active plan 方案查询 ── */

export type PlanTaskType = "lecture" | "exercise" | "project" | "review";
export type PlanDeliveryMode = "text" | "interactive" | "video" | "self_paced" | "live" | "hybrid";

export interface PlanTask {
  id: string;
  title: string;
  task_type: PlanTaskType | string;
  delivery_mode: PlanDeliveryMode | string;
  estimated_minutes: number;
  required: boolean;
  materials?: { id: string; title: string }[];
  knowledge_point?: string;
}

export interface PlanUnit {
  id: string;
  title: string;
  position: number;
  topic_id: string | null;
  target_depth: string;
  estimated_minutes: number;
  prerequisite_unit_ids: string[];
  priority: number;
  tasks: PlanTask[];
}

export interface ActivePlanPhase {
  id: string;
  position: number;
  title: string;
  objective: string;
  estimated_minutes: number;
  units: PlanUnit[];
}

export type PlanPhase = ActivePlanPhase;

export interface ActivePlan {
  plan_id: string;
  revision_id: string;
  status: string;
  feasibility_status: string;
  profile_revision_id: string;
  phases: ActivePlanPhase[];
}

export async function getActivePlan(
  id: string,
  signal?: AbortSignal,
): Promise<ActivePlan> {
  return apiClient.get<ActivePlan>(`${BASE}/${encodeURIComponent(id)}/plan/`, { signal });
}

export async function getCourseDetail(
  id: string,
  signal?: AbortSignal,
): Promise<CourseDetail> {
  return apiClient.get<CourseDetail>(`/api/courses/${encodeURIComponent(id)}/`, { signal });
}

/* ── 删除 ── */

export async function deleteCourseSession(id: string): Promise<void> {
  await apiClient.delete(`${BASE}/${encodeURIComponent(id)}/delete/`);
}

/* ── 开始学习 ── */

export async function startCourse(id: string): Promise<{ status: string; revision_id: string; course_id: string; session_id: string }> {
  return apiClient.post<{ status: string; revision_id: string; course_id: string; session_id: string }>(`${BASE}/${encodeURIComponent(id)}/start/`);
}
