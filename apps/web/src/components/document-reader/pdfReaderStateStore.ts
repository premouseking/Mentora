/**
 * pdf.js 阅读器局部状态（非全局 store）。
 */
import { useCallback, useReducer } from "react";

import type { PdfBlock } from "../../services/resourceTypes";

export interface ActiveBlockRef {
  blockIdx: string;
  page: number;
}

export interface FlashRect {
  page: number;
  bbox: [number, number, number, number];
}

export interface PdfReaderState {
  scale: number;
  currentPage: number;
  totalPages: number;
  loading: boolean;
  searchQuery: string;
  searchOpen: boolean;
  activeBlock: ActiveBlockRef | null;
  selectedText: string;
  flashRects: FlashRect[];
}

type PdfReaderAction =
  | { type: "set_scale"; scale: number }
  | { type: "set_current_page"; page: number }
  | { type: "set_total_pages"; total: number }
  | { type: "set_loading"; loading: boolean }
  | { type: "set_search_query"; query: string }
  | { type: "toggle_search"; open?: boolean }
  | { type: "set_active_block"; block: ActiveBlockRef | null }
  | { type: "set_selected_text"; text: string }
  | { type: "set_flash_rects"; rects: FlashRect[] };

const initialState: PdfReaderState = {
  scale: 1,
  currentPage: 1,
  totalPages: 1,
  loading: true,
  searchQuery: "",
  searchOpen: false,
  activeBlock: null,
  selectedText: "",
  flashRects: [],
};

function reducer(state: PdfReaderState, action: PdfReaderAction): PdfReaderState {
  switch (action.type) {
    case "set_scale":
      return { ...state, scale: action.scale };
    case "set_current_page":
      return { ...state, currentPage: action.page };
    case "set_total_pages":
      return { ...state, totalPages: action.total };
    case "set_loading":
      return { ...state, loading: action.loading };
    case "set_search_query":
      return { ...state, searchQuery: action.query };
    case "toggle_search":
      return { ...state, searchOpen: action.open ?? !state.searchOpen };
    case "set_active_block":
      return { ...state, activeBlock: action.block };
    case "set_selected_text":
      return { ...state, selectedText: action.text };
    case "set_flash_rects":
      return { ...state, flashRects: action.rects };
    default:
      return state;
  }
}

export function usePdfReaderState(initialTotalPages = 1) {
  const [state, dispatch] = useReducer(reducer, {
    ...initialState,
    totalPages: initialTotalPages,
  });

  const setScale = useCallback((scale: number) => {
    dispatch({ type: "set_scale", scale });
  }, []);

  const setCurrentPage = useCallback((page: number) => {
    dispatch({ type: "set_current_page", page });
  }, []);

  const setTotalPages = useCallback((total: number) => {
    dispatch({ type: "set_total_pages", total });
  }, []);

  const setLoading = useCallback((loading: boolean) => {
    dispatch({ type: "set_loading", loading });
  }, []);

  const setSearchQuery = useCallback((query: string) => {
    dispatch({ type: "set_search_query", query });
  }, []);

  const toggleSearch = useCallback((open?: boolean) => {
    dispatch({ type: "toggle_search", open });
  }, []);

  const setActiveBlock = useCallback((block: ActiveBlockRef | null) => {
    dispatch({ type: "set_active_block", block });
  }, []);

  const setSelectedText = useCallback((text: string) => {
    dispatch({ type: "set_selected_text", text });
  }, []);

  const setFlashRects = useCallback((rects: FlashRect[]) => {
    dispatch({ type: "set_flash_rects", rects });
  }, []);

  return {
    state,
    setScale,
    setCurrentPage,
    setTotalPages,
    setLoading,
    setSearchQuery,
    toggleSearch,
    setActiveBlock,
    setSelectedText,
    setFlashRects,
  };
}

/** 按 z-index 优先级排序块，便于 hit-test。 */
export function sortBlocksForHitTest(blocks: PdfBlock[]): PdfBlock[] {
  const priority: Record<string, number> = {
    heading: 1,
    paragraph: 2,
    list_item: 2,
    formula: 3,
    table: 4,
    image: 5,
  };
  return [...blocks].sort((a, b) => (priority[a.type] ?? 6) - (priority[b.type] ?? 6));
}

export function blocksByPage(blocks: PdfBlock[]): Map<number, PdfBlock[]> {
  const map = new Map<number, PdfBlock[]>();
  for (const block of blocks) {
    const list = map.get(block.page) ?? [];
    list.push(block);
    map.set(block.page, list);
  }
  return map;
}

export function pageSizeMap(
  pages: Array<{ page: number; width: number | null; height: number | null }>,
): Map<number, [number, number]> {
  const map = new Map<number, [number, number]>();
  for (const p of pages) {
    if (p.width && p.height) map.set(p.page, [p.width, p.height]);
  }
  return map;
}
