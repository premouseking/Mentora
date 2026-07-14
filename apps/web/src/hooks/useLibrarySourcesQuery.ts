import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "../lib/queryKeys";
import { fetchSources } from "../services/documentApi";

export function useLibrarySourcesQuery(enabled = true) {
  return useQuery({
    queryKey: queryKeys.library.sources({ scope: "setup", status: "active" }),
    queryFn: () => fetchSources(undefined, { limit: 200, status: "active" }),
    enabled,
    staleTime: 60_000,
  });
}
