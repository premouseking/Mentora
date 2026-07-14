/** React Query 缓存键，避免各页面硬编码字符串。 */
export const queryKeys = {
  library: {
    all: (params?: { limit?: number; offset?: number }) =>
      ["library", params ?? {}] as const,
    tags: () => ["library", "tags"] as const,
    sources: (params?: Record<string, string | number | undefined>) =>
      ["library", "sources", params ?? {}] as const,
  },
  courses: {
    sessions: (params?: { limit?: number; offset?: number }) =>
      ["courses", "sessions", params ?? {}] as const,
  },
  history: {
    events: ["history", "events"] as const,
  },
  task: {
    detail: (taskId: string) => ["task", taskId, "detail"] as const,
  },
  reader: {
    meta: (resourceId: string) => ["reader", resourceId, "meta"] as const,
    blocks: (resourceId: string, pages: number[]) =>
      ["reader", resourceId, "blocks", pages.join(",")] as const,
    sourceDetail: (resourceId: string) => ["reader", resourceId, "source-detail"] as const,
  },
  course: {
    detail: (courseId: string) => ["course", courseId, "detail"] as const,
    plan: (sessionId: string) => ["course", sessionId, "plan"] as const,
    sources: (courseId: string) => ["course", courseId, "sources"] as const,
    explanations: (courseId: string) => ["course", courseId, "explanations"] as const,
    mistakes: (courseId: string) => ["course", courseId, "mistakes"] as const,
    phases: (courseId: string) => ["course", courseId, "phases"] as const,
  },
};
