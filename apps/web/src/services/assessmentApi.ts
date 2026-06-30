import { apiClient, ApiError } from "./client";

const API = "/api/assessment/sessions";

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
}

export async function generateQuizSession(input: {
  sourceVersionIds: string[];
  count?: number;
  difficulty?: string;
  courseSessionId?: string;
}): Promise<QuizSession> {
  return apiClient.post<QuizSession>(`${API}/generate/`, {
    source_version_ids: input.sourceVersionIds,
    count: input.count ?? 10,
    difficulty: input.difficulty ?? "综合",
    course_session_id: input.courseSessionId,
  });
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
