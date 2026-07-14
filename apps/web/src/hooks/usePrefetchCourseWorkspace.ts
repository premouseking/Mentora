import { useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../services/client";
import { queryKeys } from "../lib/queryKeys";
import { getActivePlan, getCourseDetail } from "../services/courseApi";
import { fetchSources, sourcesToFileNodes } from "../services/documentApi";

/** 课程卡片 hover 时预取工作台核心数据。 */
export function usePrefetchCourseWorkspace() {
  const queryClient = useQueryClient();

  return (courseId: string, sessionId?: string | null) => {
    if (!courseId) return;

    queryClient.prefetchQuery({
      queryKey: queryKeys.course.detail(courseId),
      queryFn: () => getCourseDetail(courseId),
      staleTime: 60_000,
    });

    queryClient.prefetchQuery({
      queryKey: queryKeys.course.sources(courseId),
      queryFn: async () => sourcesToFileNodes(await fetchSources(courseId)),
      staleTime: 60_000,
    });

    // plan 端点只接受 session_id，不能用 course_id 回退
    if (sessionId) {
      queryClient.prefetchQuery({
        queryKey: queryKeys.course.plan(sessionId),
        queryFn: async () => {
          try {
            return await getActivePlan(sessionId);
          } catch (error) {
            if (error instanceof ApiError && error.status === 404) return null;
            throw error;
          }
        },
        staleTime: 60_000,
      });
    }
  };
}
