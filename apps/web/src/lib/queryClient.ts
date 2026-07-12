import { QueryClient } from "@tanstack/react-query";

/** 全局 React Query 客户端：切页复用缓存，减少重复请求。 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      gcTime: 10 * 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});
