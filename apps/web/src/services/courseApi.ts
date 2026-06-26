/**
 * 建课流程 API 服务层。
 *
 * 封装 /api/courses/sessions/ 下全部端点：
 * - create / get / update（步骤 1-2）
 * - inquiry（步骤 4 追问循环）
 * - plan（步骤 5 方案生成）
 *
 * 约定：
 * - 所有函数接受 AbortSignal 用于组件卸载时取消请求
 * - 超时默认 60s（plan 生成可能较慢）
 * - 错误统一抛出 { status, message } 结构
 *
 * @module services/courseApi
 */

const BASE = "/api/courses/sessions";
const DEFAULT_TIMEOUT_MS = 60_000;

/* ── 类型 ── */

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

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

/* ── 内部 ── */

async function request<T>(
  url: string,
  options: RequestInit & { timeoutMs?: number } = {},
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal: externalSignal, ...fetchOpts } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  // 组合外部 signal
  const signal = externalSignal
    ? combineSignals(externalSignal, controller.signal)
    : controller.signal;

  try {
    const resp = await fetch(url, {
      ...fetchOpts,
      signal,
      headers: {
        "Content-Type": "application/json",
        ...fetchOpts.headers,
      },
    });

    const data = await resp.json().catch(() => ({}));

    if (!resp.ok) {
      throw new ApiError(
        resp.status,
        data.error || data.detail || `请求失败 (${resp.status})`,
      );
    }

    return data as T;
  } catch (err: unknown) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError(0, "请求已取消或超时");
    }
    throw new ApiError(0, err instanceof Error ? err.message : "网络错误");
  } finally {
    clearTimeout(timeoutId);
  }
}

function combineSignals(s1: AbortSignal, s2: AbortSignal): AbortSignal {
  if (s1.aborted || s2.aborted) return AbortSignal.abort("已取消");
  const c = new AbortController();
  s1.addEventListener("abort", () => c.abort(s1.reason));
  s2.addEventListener("abort", () => c.abort(s2.reason));
  return c.signal;
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
  return request<CourseSessionListItem[]>(`${BASE}/`, { signal });
}

export async function createCourseSession(
  goal: string,
  signal?: AbortSignal,
): Promise<SessionResponse> {
  return request<SessionResponse>(`${BASE}/`, {
    method: "POST",
    body: JSON.stringify({ goal }),
    signal,
  });
}

export async function getCourseSession(
  id: string,
  signal?: AbortSignal,
): Promise<SessionDetail> {
  return request<SessionDetail>(`${BASE}/${encodeURIComponent(id)}/`, { signal });
}

export async function updateCourseSession(
  id: string,
  data: { level?: string; pace?: string; time_budget?: string; school?: string; deadline?: string | null; last_studied_at?: string },
  signal?: AbortSignal,
): Promise<{ status: string }> {
  return request<{ status: string }>(`${BASE}/${encodeURIComponent(id)}/update/`, {
    method: "PATCH",
    body: JSON.stringify(data),
    signal,
  });
}

/* ── Inquiry 追问 ── */

export async function inquiryNext(
  id: string,
  answer?: string,
  signal?: AbortSignal,
): Promise<InquiryResponse> {
  const body = answer ? { answer } : {};
  return request<InquiryResponse>(`${BASE}/${encodeURIComponent(id)}/inquiry/`, {
    method: "POST",
    body: JSON.stringify(body),
    signal,
    timeoutMs: 30_000, // 追问单次 30s 超时
  });
}

/* ── Plan 方案生成 ── */

export async function generatePlan(
  id: string,
  signal?: AbortSignal,
): Promise<PlanResponse> {
  return request<PlanResponse>(`${BASE}/${encodeURIComponent(id)}/plan/`, {
    method: "POST",
    signal,
    timeoutMs: 90_000, // 方案生成 90s 超时
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
  return request<ActivePlan>(`${BASE}/${encodeURIComponent(id)}/plan/`, { signal });
}

/* ── 删除 ── */

export async function deleteCourseSession(id: string): Promise<void> {
  await fetch(`${BASE}/${encodeURIComponent(id)}/delete/`, { method: "DELETE" });
}

/* ── 开始学习 ── */

export async function startCourse(id: string): Promise<{ status: string; revision_id: string }> {
  return request(`${BASE}/${encodeURIComponent(id)}/start/`, {
    method: "POST",
  });
}
