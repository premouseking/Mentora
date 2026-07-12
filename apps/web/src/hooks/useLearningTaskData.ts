import { useQueries } from "@tanstack/react-query";

import { queryKeys } from "../lib/queryKeys";
import { getCourseDetail } from "../services/courseApi";
import { fetchSources, sourcesToFileNodes } from "../services/documentApi";
import { fetchTask } from "../services/learningApi";

export function useLearningTaskData(courseId: string | undefined, taskId: string | undefined) {
  const [taskQuery, courseQuery, sourcesQuery] = useQueries({
    queries: [
      {
        queryKey: queryKeys.task.detail(taskId ?? ""),
        queryFn: () => fetchTask(taskId!),
        enabled: Boolean(taskId),
      },
      {
        queryKey: queryKeys.course.detail(courseId ?? ""),
        queryFn: () => getCourseDetail(courseId!),
        enabled: Boolean(courseId),
      },
      {
        queryKey: queryKeys.course.sources(courseId ?? ""),
        queryFn: async () => sourcesToFileNodes(await fetchSources(courseId!)),
        enabled: Boolean(courseId),
      },
    ],
  });

  const isInitialLoading = [taskQuery, courseQuery, sourcesQuery].some(
    (query) => query.isLoading && query.data === undefined,
  );

  return {
    task: taskQuery.data ?? null,
    courseSessionId: courseQuery.data?.session_id || courseId,
    fileNodes: sourcesQuery.data ?? [],
    isInitialLoading,
    error: taskQuery.error instanceof Error ? taskQuery.error.message : "",
  };
}
