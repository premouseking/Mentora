import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { ApiError } from "../services/client";
import { queryKeys } from "../lib/queryKeys";
import {
  getActivePlan,
  getCourseDetail,
  updateCourseSession,
  type ActivePlan,
} from "../services/courseApi";
import { fetchSources, sourcesToFileNodes } from "../services/documentApi";
import type { FileNode } from "../data/files";

export interface CourseWorkspaceCoreData {
  course: Awaited<ReturnType<typeof getCourseDetail>> | null;
  activePlan: ActivePlan | null;
  fileNodes: FileNode[];
  isInitialLoading: boolean;
  /** 学习计划后台加载中（不阻塞首屏） */
  isPlanLoading?: boolean;
}

export function useCourseWorkspaceCore(courseId: string | undefined): CourseWorkspaceCoreData {
  const [courseQuery, sourcesQuery] = useQueries({
    queries: [
      {
        queryKey: queryKeys.course.detail(courseId ?? ""),
        queryFn: async () => {
          try {
            return await getCourseDetail(courseId!);
          } catch (error) {
            if (error instanceof ApiError && error.status === 404) return null;
            throw error;
          }
        },
        enabled: Boolean(courseId),
        staleTime: 60_000,
      },
      {
        queryKey: queryKeys.course.sources(courseId ?? ""),
        queryFn: async () => sourcesToFileNodes(await fetchSources(courseId!)),
        enabled: Boolean(courseId),
        staleTime: 60_000,
      },
    ],
  });

  const course = courseQuery.data ?? null;
  const planSessionId = course?.session_id ?? null;

  const planQuery = useQuery({
    queryKey: queryKeys.course.plan(planSessionId ?? ""),
    queryFn: async () => {
      try {
        return await getActivePlan(planSessionId!);
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }
    },
    enabled: Boolean(planSessionId),
    staleTime: 120_000,
  });

  const touchSession = useMutation({
    mutationFn: (sessionId: string) =>
      updateCourseSession(sessionId, { last_studied_at: new Date().toISOString() }),
  });
  const touchedRef = useRef<string | null>(null);

  useEffect(() => {
    if (!planSessionId || touchedRef.current === planSessionId) return;
    touchedRef.current = planSessionId;
    const timer = window.setTimeout(() => {
      touchSession.mutate(planSessionId);
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [planSessionId, touchSession]);

  const queries = [courseQuery, sourcesQuery];
  const isInitialLoading = queries.some(
    (query) => query.isLoading && query.data === undefined,
  );

  return {
    course,
    activePlan: planQuery.data ?? null,
    fileNodes: sourcesQuery.data ?? [],
    isInitialLoading,
    isPlanLoading: planQuery.isLoading && planQuery.data === undefined,
  };
}
