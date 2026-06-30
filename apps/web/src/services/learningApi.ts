/**
 * 学习任务 API 服务层。
 *
 * @module services/learningApi
 */

import { apiClient } from "./client";

/* ── 内容块类型 ── */

export type ContentBlock =
  | HeadingBlock
  | ParagraphBlock
  | CitationBlock
  | DiagramBlock
  | CalloutBlock
  | QuizBlock;

export interface HeadingBlock {
  type: "heading";
  id: string;
  label: string;
  level: 2 | 3;
}

export interface ParagraphBlock {
  type: "paragraph";
  id: string;
  text: string;
  modes?: {
    simple?: string;
    example?: string;
    standard: string;
  };
}

export interface CitationBlock {
  type: "citation";
  id: string;
  source_title: string;
  chapter: string;
  page_number: number;
  evidence_id: string;
}

export interface DiagramBlock {
  type: "diagram";
  id: string;
  label: string;
  diagram_type: string;
  data: Record<string, unknown>;
}

export interface CalloutBlock {
  type: "callout";
  id: string;
  variant: "tip" | "warning" | "info";
  text: string;
}

export interface QuizBlock {
  type: "quiz";
  id: string;
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
  next_step_link?: string;
}

export interface TaskSource {
  evidence_id: string;
  title: string;
  page_number: number;
  snippet_preview: string;
}

/* ── 任务详情 ── */

export interface LearningTaskDetail {
  task_id: string;
  title: string;
  task_type: string;
  unit_title: string;
  phase_title: string;
  position: number;
  estimated_minutes: number;
  content_blocks: ContentBlock[];
  sources: TaskSource[];
}

/* ── 学习历史事件 ── */

export interface HistoryEvent {
  id: string;
  event_type: string;
  task_id: string | null;
  task_title: string;
  course_id: string | null;
  course_title: string;
  description: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

/* ── API ── */

export async function fetchTask(taskId: string): Promise<LearningTaskDetail> {
  return apiClient.get<LearningTaskDetail>(`/api/learning/tasks/${encodeURIComponent(taskId)}/`);
}

export async function fetchHistory(limit = 50): Promise<{ items: HistoryEvent[] }> {
  return apiClient.get<{ items: HistoryEvent[] }>(`/api/history/?limit=${limit}`);
}

/* ── 错题 & 讲解 ── */

export interface MistakeItem {
  item_id: string;
  title: string;
  topic: string;
  difficulty: string;
  wrong_count: number;
  last_wrong: string;
  question: string;
  options: string[];
  correct_answer: string;
  explanation: string;
  error_reason: string;
  knowledge_points: string[];
  source_links: { title: string; location: string; excerpt: string }[];
}

export interface ExplanationItem {
  id: string;
  title: string;
  topic: string;
  type: string;
  created_at: string;
}

export async function fetchMistakes(courseId: string): Promise<{ items: MistakeItem[] }> {
  return apiClient.get<{ items: MistakeItem[] }>(
    `/api/learning/mistakes/?course_id=${encodeURIComponent(courseId)}`,
  );
}

export async function fetchExplanations(courseId: string): Promise<{ items: ExplanationItem[] }> {
  return apiClient.get<{ items: ExplanationItem[] }>(
    `/api/learning/explanations/?course_id=${encodeURIComponent(courseId)}`,
  );
}
