import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";

import { queryKeys } from "../lib/queryKeys";
import { fetchSourceDetail, type SourceDetail } from "../services/documentApi";
import {
  fetchReaderBlocks,
  fetchReaderMeta,
  normalizeReaderDocument,
} from "../services/resourceApi";
import {
  buildMinimalPdfReaderDoc,
  isSourceDetailPdf,
} from "../components/document-reader/resourceReaderUtils";
import type { ReaderFetchStage } from "../components/document-reader/readerLoadingUtils";
import type { PdfBlock, PdfReaderDocument } from "../services/resourceTypes";
import { isResourceReady } from "../services/resourceTypes";

async function loadReaderMeta(resourceId: string): Promise<PdfReaderDocument> {
  try {
    return await fetchReaderMeta(resourceId);
  } catch {
    const detail = await fetchSourceDetail(resourceId);
    if (detail.version.processingStatus !== "completed") {
      throw new Error("资料尚未完成解析，解析完成后可预览。");
    }
    if (isSourceDetailPdf(detail)) {
      return buildMinimalPdfReaderDoc(resourceId, detail);
    }
    throw new Error("无法加载阅读器元数据。");
  }
}

const READER_META_STALE_MS = 5 * 60_000;
const READER_BLOCKS_STALE_MS = 2 * 60_000;
const READER_BLOCKS_GC_MS = 60_000;

export function useResourceReaderMeta(resourceId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.reader.meta(resourceId ?? ""),
    queryFn: () => loadReaderMeta(resourceId!),
    enabled: Boolean(resourceId),
    staleTime: READER_META_STALE_MS,
  });
}

export function useResourceReaderBlocks(
  resourceId: string | undefined,
  pages: number[],
  enabled = true,
) {
  const sortedPages = useMemo(
    () => [...new Set(pages.filter((page) => page > 0))].sort((a, b) => a - b),
    [pages],
  );

  return useQuery({
    queryKey: queryKeys.reader.blocks(resourceId ?? "", sortedPages),
    queryFn: () => fetchReaderBlocks(resourceId!, sortedPages),
    enabled: Boolean(resourceId) && enabled && sortedPages.length > 0,
    staleTime: READER_BLOCKS_STALE_MS,
    gcTime: READER_BLOCKS_GC_MS,
  });
}

export function useResourceReaderDocument(resourceId: string | undefined) {
  const metaQuery = useResourceReaderMeta(resourceId);
  const initialPages = useMemo(() => {
    const total = metaQuery.data?.pages.length ?? 0;
    return total > 0 ? [1] : [];
  }, [metaQuery.data?.pages.length]);

  const blocksQuery = useResourceReaderBlocks(
    resourceId,
    initialPages,
    Boolean(metaQuery.data),
  );

  const readerDoc = useMemo((): PdfReaderDocument | null => {
    if (!metaQuery.data) return null;
    return {
      ...metaQuery.data,
      blocks: blocksQuery.data ?? [],
    };
  }, [metaQuery.data, blocksQuery.data]);

  const fetchStage: ReaderFetchStage = metaQuery.isLoading
    ? "meta"
    : blocksQuery.isLoading && !blocksQuery.data
      ? "blocks"
      : "ready";

  return {
    readerDoc,
    loading: metaQuery.isLoading || (Boolean(metaQuery.data) && blocksQuery.isLoading && !blocksQuery.data),
    fetchStage,
    error: metaQuery.error instanceof Error
      ? metaQuery.error.message
      : blocksQuery.error instanceof Error
        ? blocksQuery.error.message
        : "",
    isReady: readerDoc !== null && isResourceReady(readerDoc.resource.processing_status),
  };
}

export function usePrefetchReaderBlocks(resourceId: string | undefined) {
  const queryClient = useQueryClient();
  return useCallback(
    (pages: number[]) => {
      if (!resourceId || pages.length === 0) return;
      const sorted = [...new Set(pages.filter((page) => page > 0))].sort((a, b) => a - b);
      queryClient.prefetchQuery({
        queryKey: queryKeys.reader.blocks(resourceId, sorted),
        queryFn: () => fetchReaderBlocks(resourceId, sorted),
        staleTime: READER_BLOCKS_STALE_MS,
        gcTime: READER_BLOCKS_GC_MS,
      });
    },
    [queryClient, resourceId],
  );
}

const DEFAULT_OVERLAY_PAGE_RADIUS = 3;

export function mergeReaderBlocks(
  existing: PdfBlock[],
  incoming: PdfBlock[],
  centerPage?: number,
  pageRadius = DEFAULT_OVERLAY_PAGE_RADIUS,
): PdfBlock[] {
  const map = new Map(existing.map((block) => [block.idx, block]));
  for (const block of incoming) {
    map.set(block.idx, block);
  }

  let merged = [...map.values()];
  if (centerPage !== undefined && centerPage > 0) {
    const minPage = Math.max(1, centerPage - pageRadius);
    const maxPage = centerPage + pageRadius;
    merged = merged.filter((block) => block.page >= minPage && block.page <= maxPage);
  }

  return merged.sort((a, b) => a.page - b.page || a.idx.localeCompare(b.idx));
}

/** 关闭阅读 tab 时释放 blocks 分页缓存，meta 仍保留以便快速重开。 */
export function removeReaderBlocksCache(queryClient: QueryClient, resourceId: string): void {
  queryClient.removeQueries({
    queryKey: ["reader", resourceId, "blocks"],
    exact: false,
  });
}

export function useNonPdfSourceDetail(resourceId: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.reader.sourceDetail(resourceId ?? ""),
    queryFn: () => fetchSourceDetail(resourceId!),
    enabled: Boolean(resourceId) && enabled,
    staleTime: 5 * 60_000,
    select: (detail: SourceDetail) => detail,
  });
}

export { normalizeReaderDocument };
