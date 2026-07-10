/**
 * 课程 Agent API：会话列表、历史与 SSE 流式对话。
 *
 * @module services/courseAgentApi
 */

import { apiClient } from "./client";
import { postJsonStream } from "./streamClient";
import { consumeAssistantStream, type ChatStreamEvent } from "../features/assistant/assistantStream";

export interface CourseAgentCitation {
  content?: string;
  content_preview: string;
  page_number?: number | null;
  source_title?: string;
}

export interface CourseAgentMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: CourseAgentCitation[];
  metadata?: Record<string, unknown>;
  created_at?: string | null;
}

export interface CourseAgentSessionSummary {
  id: string;
  course_id: string;
  course_session_id: string;
  title: string;
  status: string;
  message_count: number;
  last_message_preview?: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CourseAgentSessionDetail extends CourseAgentSessionSummary {
  messages: CourseAgentMessage[];
}

export type CourseAgentStreamEvent =
  | ChatStreamEvent
  | {
      type: "session_created";
      session_id: string;
      title?: string;
      course_id?: string;
    };

export interface StreamCourseAgentMessageParams {
  courseId: string;
  message: string;
  agentSessionId?: string | null;
  currentTaskId?: string | null;
  currentSourceVersionId?: string | null;
  mentions?: Array<{
    id: string;
    type: string;
    label: string;
    source?: string;
  }>;
  signal?: AbortSignal;
  onEvent?: (event: CourseAgentStreamEvent) => void;
}

export async function listCourseAgentSessions(
  courseId: string,
  signal?: AbortSignal,
): Promise<CourseAgentSessionSummary[]> {
  const data = await apiClient.get<{ items: CourseAgentSessionSummary[] }>(
    `/api/courses/${encodeURIComponent(courseId)}/agent-sessions/`,
    { signal },
  );
  return data.items ?? [];
}

export async function getCourseAgentSession(
  courseId: string,
  sessionId: string,
  signal?: AbortSignal,
): Promise<CourseAgentSessionDetail> {
  return apiClient.get<CourseAgentSessionDetail>(
    `/api/courses/${encodeURIComponent(courseId)}/agent-sessions/${encodeURIComponent(sessionId)}/`,
    { signal },
  );
}

export async function streamCourseAgentMessage({
  courseId,
  message,
  agentSessionId,
  currentTaskId,
  currentSourceVersionId,
  mentions,
  signal,
  onEvent,
}: StreamCourseAgentMessageParams): Promise<void> {
  const body = await postJsonStream(
    `/api/courses/${encodeURIComponent(courseId)}/agent-sessions/stream/`,
    {
      message,
      agent_session_id: agentSessionId ?? undefined,
      current_task_id: currentTaskId ?? undefined,
      current_source_version_id: currentSourceVersionId ?? undefined,
      mentions: mentions ?? [],
    },
    { signal },
  );

  await consumeAssistantStream(body, (event) => {
    onEvent?.(event as CourseAgentStreamEvent);
  });
}
