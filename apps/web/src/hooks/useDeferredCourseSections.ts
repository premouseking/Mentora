import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "../lib/queryKeys";
import { fetchExplanations, fetchMistakes } from "../services/learningApi";

export function useCourseExplanations(courseId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.course.explanations(courseId ?? ""),
    queryFn: async () => (await fetchExplanations(courseId!)).items,
    enabled: Boolean(courseId) && enabled,
    staleTime: 60_000,
  });
}

export function useCourseMistakes(courseId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.course.mistakes(courseId ?? ""),
    queryFn: async () => (await fetchMistakes(courseId!)).items,
    enabled: Boolean(courseId) && enabled,
    staleTime: 60_000,
  });
}

export function useCoursePhases(courseId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.course.phases(courseId ?? ""),
    queryFn: async () => {
      const { fetchCoursePhases } = await import("../services/documentApi");
      return fetchCoursePhases(courseId!);
    },
    enabled: Boolean(courseId) && enabled,
    staleTime: 60_000,
  });
}
