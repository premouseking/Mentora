import { apiClient } from "./client";

const API = "/api/assessment/sessions";
const JOBS_API = "/api/assessment/generation-jobs";

/** 同步 fast path 通常 30-90 秒；异步或大题量需更长 */
export const QUIZ_GENERATION_TIMEOUT_MS = 300_000;
export const QUIZ_JOB_POLL_INTERVAL_MS = 2_000;
export const TASK_QUIZ_DEFAULT_COUNT = 5;

export interface QuizSourceLink {
  evidence_id: string;
  source_version_id: string;
  title: string;
  page_number: number;
  snippet: string;
}

export interface QuizOption {
  label: string;
  text: string;
}

export interface QuizItem {
  attempt_id: string;
  item_id: string;
  position: number;
  question_type: "single_choice";
  question_text: string;
  options: QuizOption[];
  correct_answer: string;
  explanation: string;
  difficulty: number;
  source_links: QuizSourceLink[];
  user_answer: string;
  is_correct: boolean;
}

export interface QuizSession {
  session_id: string;
  course_session_id: string;
  status: "created" | "in_progress" | "completed";
  total_items: number;
  correct_count: number;
  score_pct: number;
  items: QuizItem[];
  reused?: boolean;
}

export interface QuizGenerationJob {
  job_id: string;
  status: "pending" | "running" | "succeeded" | "failed";
  progress: string;
  progress_pct: number;
  error?: string | null;
  error_code?: string | null;
  session_id?: string | null;
  session?: QuizSession;
}

export type QuizGenerationMode = "fast" | "agent";

export async function generateQuizSession(input: {
  sourceVersionIds?: string[];
  sourceEvidenceIds?: string[];
  taskId?: string;
  count?: number;
  difficulty?: string;
  courseSessionId?: string;
  mode?: QuizGenerationMode;
  async?: boolean;
  forceRegenerate?: boolean;
}): Promise<QuizSession | QuizGenerationJob> {
  return apiClient.post<QuizSession | QuizGenerationJob>(
    `${API}/generate/`,
    {
      source_version_ids: input.sourceVersionIds ?? [],
      source_evidence_ids: input.sourceEvidenceIds ?? [],
      task_id: input.taskId,
      count: input.count ?? TASK_QUIZ_DEFAULT_COUNT,
      difficulty: input.difficulty ?? "综合",
      course_session_id: input.courseSessionId,
      mode: input.mode ?? "fast",
      async: input.async ?? false,
      force_regenerate: input.forceRegenerate ?? false,
    },
    { timeoutMs: QUIZ_GENERATION_TIMEOUT_MS },
  );
}

export async function fetchQuizGenerationJob(jobId: string): Promise<QuizGenerationJob> {
  return apiClient.get<QuizGenerationJob>(`${JOBS_API}/${encodeURIComponent(jobId)}/`);
}

export async function pollQuizGenerationJob(
  jobId: string,
  opts?: { intervalMs?: number; signal?: AbortSignal },
): Promise<QuizSession> {
  const intervalMs = opts?.intervalMs ?? QUIZ_JOB_POLL_INTERVAL_MS;
  while (true) {
    if (opts?.signal?.aborted) {
      throw new Error("请求已取消");
    }
    const job = await fetchQuizGenerationJob(jobId);
    if (job.status === "failed") {
      throw new Error(job.error || "出题任务失败");
    }
    if (job.status === "succeeded" && job.session) {
      return job.session;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
}

export async function findReusableQuizSession(input: {
  courseSessionId: string;
  taskId?: string;
  sourceVersionIds?: string[];
  sourceEvidenceIds?: string[];
  count?: number;
  difficulty?: string;
}): Promise<QuizSession | null> {
  const params = new URLSearchParams();
  params.set("course_session_id", input.courseSessionId);
  if (input.taskId) params.set("task_id", input.taskId);
  if (input.count != null) params.set("count", String(input.count));
  if (input.difficulty) params.set("difficulty", input.difficulty);
  if (input.sourceVersionIds?.length) {
    params.set("source_version_ids", input.sourceVersionIds.join(","));
  }
  if (input.sourceEvidenceIds?.length) {
    params.set("source_evidence_ids", input.sourceEvidenceIds.join(","));
  }
  const data = await apiClient.get<{ session: QuizSession | null }>(
    `${API}/reuse/?${params.toString()}`,
  );
  return data.session;
}

export async function submitQuizAnswer(input: {
  sessionId: string;
  itemId: string;
  userAnswer: string;
  durationSeconds?: number;
}): Promise<{ attempt_id: string; is_correct: boolean; score: number }> {
  return apiClient.post<{ attempt_id: string; is_correct: boolean; score: number }>(
    `${API}/${encodeURIComponent(input.sessionId)}/attempts/`,
    {
      item_id: input.itemId,
      user_answer: input.userAnswer,
      duration_seconds: input.durationSeconds,
    },
  );
}

export async function completeQuizSession(sessionId: string): Promise<QuizSession> {
  return apiClient.post<QuizSession>(`${API}/${encodeURIComponent(sessionId)}/complete/`);
}

export async function fetchQuizSession(sessionId: string): Promise<QuizSession> {
  return apiClient.get<QuizSession>(`${API}/${encodeURIComponent(sessionId)}/`);
}

export function isQuizGenerationJob(
  value: QuizSession | QuizGenerationJob,
): value is QuizGenerationJob {
  return "job_id" in value && !("items" in value);
}
