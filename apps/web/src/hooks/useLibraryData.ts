import { useQuery } from "@tanstack/react-query";

import { queryKeys } from "../lib/queryKeys";
import {
  fetchFolders,
  fetchSources,
  fetchTags,
  type FolderItem,
} from "../services/documentApi";
import type { LibraryItem } from "../data/library";
import { sourceToLibraryItem } from "./libraryMapping";

/** 首屏分页大小；全量过滤仍基于已加载页，后续可接无限滚动。 */
export const LIBRARY_PAGE_SIZE = 200;

export interface LibraryData {
  items: LibraryItem[];
  folders: FolderItem[];
  tags: string[];
  /** 资料版本 ID → Source ID，供删除/移动等 mutation 使用。 */
  sourceIdByItemId: Record<string, string>;
}

function mapSourcesToLibraryItems(sources: Awaited<ReturnType<typeof fetchSources>>) {
  const sourceIdByItemId: Record<string, string> = {};
  const items = sources.map((source) => {
    const item = sourceToLibraryItem(source);
    sourceIdByItemId[item.id] = source.id;
    return item;
  });
  return { items, sourceIdByItemId };
}

async function fetchLibraryCore(): Promise<Omit<LibraryData, "tags">> {
  const [sources, folders] = await Promise.all([
    fetchSources(undefined, { limit: LIBRARY_PAGE_SIZE }),
    fetchFolders(),
  ]);
  const { items, sourceIdByItemId } = mapSourcesToLibraryItems(sources);
  return { items, folders, sourceIdByItemId };
}

export function useLibraryData() {
  const coreQuery = useQuery({
    queryKey: queryKeys.library.all({ limit: LIBRARY_PAGE_SIZE }),
    queryFn: () => fetchLibraryCore(),
    staleTime: 120_000,
    placeholderData: (prev) => prev,
  });

  const tagsQuery = useQuery({
    queryKey: queryKeys.library.tags(),
    queryFn: fetchTags,
    staleTime: 300_000,
    placeholderData: (prev) => prev,
  });

  const data: LibraryData | undefined = coreQuery.data
    ? {
        ...coreQuery.data,
        tags: tagsQuery.data ?? [],
      }
    : undefined;

  return {
    data,
    isLoading: coreQuery.isLoading && coreQuery.data === undefined,
    isFetching: coreQuery.isFetching || tagsQuery.isFetching,
    error: coreQuery.error ?? tagsQuery.error ?? null,
  };
}
