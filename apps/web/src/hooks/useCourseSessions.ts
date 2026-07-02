import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "../lib/queryKeys";
import { listCourseSessions } from "../services/courseApi";

export function useCourseSessions(enabled = true) {
  return useQuery({
    queryKey: queryKeys.courses.sessions({ limit: 200 }),
    queryFn: ({ signal }) => listCourseSessions(signal, { limit: 200 }),
    enabled,
    placeholderData: (prev) => prev,
  });
}
