import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "../lib/queryKeys";
import { fetchHistory } from "../services/learningApi";
import { useCourseSessions } from "./useCourseSessions";

export function useHistoryData() {
  const historyQuery = useQuery({
    queryKey: queryKeys.history.events,
    queryFn: async () => (await fetchHistory()).items,
    staleTime: 60_000,
  });

  const sessionsQuery = useCourseSessions();

  return {
    events: historyQuery.data ?? [],
    sessions: sessionsQuery.data ?? [],
    isLoading: (historyQuery.isLoading && !historyQuery.data)
      || (sessionsQuery.isLoading && !sessionsQuery.data),
    isFetching: historyQuery.isFetching || sessionsQuery.isFetching,
  };
}
