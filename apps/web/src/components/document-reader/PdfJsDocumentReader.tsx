/**
 * pdf.js 原文 PDF 阅读器（PdfShow-like core）。
 *
 * 约定：blocks 仅负责 overlay；版式由 pdf.js 渲染。
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Minus, Plus, Search } from "lucide-react";
import "pdfjs-dist/web/pdf_viewer.css";

import type { PdfReaderDocument } from "../../services/resourceTypes";
import {
  mergeReaderBlocks,
  usePrefetchReaderBlocks,
  useResourceReaderBlocks,
} from "../../hooks/useResourceReaderQuery";
import {
  evictPdfBytesCache,
  loadPdfDocumentFromUrls,
  loadPdfJsViewer,
  PdfLoadAbortedError,
  pdfjsLib,
  workerSrcReady,
} from "./loadPdfJsViewer";
import type { PdfLoadProgress } from "./loadPdfJsViewer";
import { mapByteProgress } from "./readerLoadingUtils";
import { ReaderLoadingProgress } from "./ReaderLoadingProgress";
import { schedulePdfViewerUpdate } from "./schedulePdfViewerUpdate";
import { useLayoutReady } from "./useLayoutReady";
import { PdfHighlightLayer } from "./PdfHighlightLayer";
import { PdfReaderSidebar } from "./PdfReaderSidebar";
import { PdfTextSearch } from "./PdfTextSearch";
import { buildReaderPageWindow, READER_PAGE_WINDOW_RADIUS } from "./readerPageWindow";
import { readReaderPrefs, writeReaderPrefs } from "./readerPrefsStorage";
import { logReaderPerf } from "./readerPerf";
import { resolveEvidenceFlashRects } from "./resourceReaderUtils";
import { ReaderSelectionToolbar } from "./ReaderSelectionToolbar";
import { ReaderToolbar } from "./ReaderToolbar";
import { pageSizeMap, usePdfReaderState, type FlashRect } from "./pdfReaderStateStore";
import type { OutlineItem } from "./pdfReaderUtils";
import type { EvidenceHighlight } from "./types";

interface PdfJsDocumentReaderProps {
  title: string;
  pdfUrl: string;
  pdfFallbackUrl?: string;
  readerDoc: PdfReaderDocument;
  resourceId?: string;
  evidenceHighlight?: EvidenceHighlight | null;
  onClearEvidenceHighlight?: () => void;
  onLoadError?: (message: string) => void;
  /** tab 激活或容器可见时递增，触发 pdf.js 重新 layout。 */
  layoutRefreshKey?: number;
}

export function PdfJsDocumentReader({
  title,
  pdfUrl,
  pdfFallbackUrl,
  readerDoc,
  resourceId,
  evidenceHighlight,
  onClearEvidenceHighlight,
  onLoadError,
  layoutRefreshKey = 0,
}: PdfJsDocumentReaderProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const scrollWrapRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<HTMLDivElement | null>(null);
  const eventBusRef = useRef<InstanceType<Awaited<ReturnType<typeof loadPdfJsViewer>>["EventBus"]> | null>(null);
  const pdfViewerRef = useRef<InstanceType<Awaited<ReturnType<typeof loadPdfJsViewer>>["PDFViewer"]> | null>(null);
  const pdfDocumentRef = useRef<Awaited<ReturnType<typeof loadPdfDocumentFromUrls>> | null>(null);
  const layoutUpdateRafRef = useRef<number | null>(null);
  const flashTimeoutRef = useRef<number | null>(null);
  const loadStartedAtRef = useRef<number>(performance.now());
  const savedPrefs = useMemo(() => readReaderPrefs(resourceId), [resourceId]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(savedPrefs.sidebarCollapsed ?? false);
  const [viewerReady, setViewerReady] = useState(false);
  const [loadProgress, setLoadProgress] = useState({
    progress: 68,
    label: "准备阅读器…",
    indeterminate: true,
  });

  const layoutReady = useLayoutReady(scrollWrapRef);
  const onLoadErrorRef = useRef(onLoadError);
  const loadProgressRafRef = useRef<number | null>(null);
  const pendingProgressRef = useRef<{
    progress: number;
    label: string;
    indeterminate: boolean;
  } | null>(null);

  useEffect(() => {
    onLoadErrorRef.current = onLoadError;
  }, [onLoadError]);

  const initialTotal = readerDoc.pages.length || readerDoc.resource.pages || 1;
  const {
    state,
    setScale,
    setCurrentPage,
    setTotalPages,
    setLoading,
    setSearchQuery,
    toggleSearch,
    setActiveBlock,
    setFlashRects,
  } = usePdfReaderState(initialTotal);

  const showFlashRects = useCallback((rects: FlashRect[]) => {
    if (flashTimeoutRef.current !== null) {
      window.clearTimeout(flashTimeoutRef.current);
      flashTimeoutRef.current = null;
    }
    setFlashRects(rects);
    if (rects.length === 0) return;
    flashTimeoutRef.current = window.setTimeout(() => {
      setFlashRects([]);
      flashTimeoutRef.current = null;
    }, 2400);
  }, [setFlashRects]);

  const pageSizes = useMemo(() => pageSizeMap(readerDoc.pages), [readerDoc.pages]);

  const pagesToLoad = useMemo(() => {
    const base = buildReaderPageWindow(state.currentPage, state.totalPages, READER_PAGE_WINDOW_RADIUS);
    if (!evidenceHighlight?.pageNumber) return base;
    const evidenceWindow = buildReaderPageWindow(
      evidenceHighlight.pageNumber,
      state.totalPages,
      READER_PAGE_WINDOW_RADIUS,
    );
    return [...new Set([...base, ...evidenceWindow])].sort((a, b) => a - b);
  }, [evidenceHighlight?.pageNumber, state.currentPage, state.totalPages]);

  const prefetchBlocks = usePrefetchReaderBlocks(resourceId);

  const {
    data: pagedBlocks = [],
    isFetched: blocksFetched,
    isLoading: blocksLoading,
  } = useResourceReaderBlocks(
    resourceId,
    pagesToLoad,
    Boolean(resourceId),
  );

  const evidencePageBlocksLoaded = useMemo(() => {
    if (!evidenceHighlight?.pageNumber) return true;
    const targetPage = evidenceHighlight.pageNumber;
    if (!pagesToLoad.includes(targetPage)) return true;
    if (blocksFetched) return true;
    return !blocksLoading && pagedBlocks.length > 0;
  }, [
    blocksFetched,
    blocksLoading,
    evidenceHighlight?.pageNumber,
    pagedBlocks.length,
    pagesToLoad,
  ]);

  const overlayDoc = useMemo(
    () => ({
      ...readerDoc,
      blocks: mergeReaderBlocks(
        readerDoc.blocks,
        pagedBlocks,
        state.currentPage,
        READER_PAGE_WINDOW_RADIUS,
      ),
    }),
    [readerDoc, pagedBlocks, state.currentPage],
  );

  useEffect(() => {
    writeReaderPrefs(resourceId, {
      page: state.currentPage,
      scale: state.scale,
      sidebarCollapsed,
    });
  }, [resourceId, sidebarCollapsed, state.currentPage, state.scale]);

  useEffect(() => {
    if (!resourceId || !viewerReady) return;
    const nextCenter = state.currentPage + 1;
    if (nextCenter > state.totalPages) return;

    const prefetchPages = buildReaderPageWindow(nextCenter, state.totalPages, READER_PAGE_WINDOW_RADIUS);
    const idleId = window.requestIdleCallback?.(
      () => prefetchBlocks(prefetchPages),
      { timeout: 1500 },
    );
    return () => {
      if (idleId !== undefined) window.cancelIdleCallback(idleId);
    };
  }, [prefetchBlocks, resourceId, state.currentPage, state.totalPages, viewerReady]);

  const refreshPdfLayout = useCallback(() => {
    pdfViewerRef.current?.update();
  }, []);

  const scheduleLayoutRefresh = useCallback(() => {
    if (layoutUpdateRafRef.current !== null) return;
    layoutUpdateRafRef.current = window.requestAnimationFrame(() => {
      layoutUpdateRafRef.current = null;
      refreshPdfLayout();
    });
  }, [refreshPdfLayout]);

  const outlineItems = useMemo(
    () => readerDoc.outline.map(outlineToSidebarItem),
    [readerDoc.outline],
  );

  const applyLoadProgress = useCallback((progress: PdfLoadProgress) => {
    const next = progress.phase === "download"
      ? {
          progress: mapByteProgress(progress.loaded, progress.total, 72, 90),
          label: "下载 PDF 文件…",
          indeterminate: false,
        }
      : {
          progress: mapByteProgress(progress.loaded, progress.total, 90, 98),
          label: "解析 PDF…",
          indeterminate: !progress.total,
        };

    pendingProgressRef.current = next;
    if (loadProgressRafRef.current !== null) return;

    loadProgressRafRef.current = window.requestAnimationFrame(() => {
      loadProgressRafRef.current = null;
      if (pendingProgressRef.current) {
        setLoadProgress(pendingProgressRef.current);
        pendingProgressRef.current = null;
      }
    });
  }, []);

  const subscribeEvent = useCallback(
    (eventName: "pagerendered" | "scalechanging", handler: (evt: unknown) => void) => {
      const bus = eventBusRef.current;
      if (!bus) return () => {};
      bus.on(eventName, handler);
      return () => bus.off(eventName, handler);
    },
    [],
  );

  const goToPage = useCallback((pageNumber: number) => {
    const viewer = pdfViewerRef.current;
    if (!viewer) return;
    const clamped = Math.max(1, Math.min(pageNumber, viewer.pagesCount || state.totalPages));
    viewer.currentPageNumber = clamped;
    setCurrentPage(clamped);
  }, [setCurrentPage, state.totalPages]);

  const scrollToFlashRects = useCallback((rects: FlashRect[]) => {
    if (rects.length === 0) return;
    goToPage(rects[0].page);
    showFlashRects(rects);
  }, [goToPage, showFlashRects]);

  const applyScale = useCallback((nextScale: number) => {
    const viewer = pdfViewerRef.current;
    const bus = eventBusRef.current;
    if (!viewer || !bus) return;
    const clamped = Math.max(0.5, Math.min(nextScale, 3));
    viewer.currentScaleValue = String(clamped);
    setScale(clamped);
    bus.dispatch("scalechanging", { scale: clamped });
  }, [setScale]);

  useEffect(() => {
    if (!layoutReady) {
      setLoadProgress({ progress: 66, label: "准备阅读器布局…", indeterminate: true });
      return;
    }

    const container = containerRef.current;
    const viewerElement = viewerRef.current;
    if (!container || !viewerElement) return;

    let cancelled = false;
    const abortController = new AbortController();
    const candidateUrls = [pdfUrl, pdfFallbackUrl].filter(
      (url, index, list): url is string => Boolean(url) && list.indexOf(url) === index,
    );
    let cancelScheduledLayout: (() => void) | null = null;
    let pdfDocument: Awaited<ReturnType<typeof loadPdfDocumentFromUrls>> | null = null;
    let pdfViewer: InstanceType<Awaited<ReturnType<typeof loadPdfJsViewer>>["PDFViewer"]> | null = null;
    let eventBus: InstanceType<Awaited<ReturnType<typeof loadPdfJsViewer>>["EventBus"]> | null = null;
    let linkService: InstanceType<Awaited<ReturnType<typeof loadPdfJsViewer>>["PDFLinkService"]> | null = null;

    const onPageChanging = (evt: { pageNumber: number }) => {
      setCurrentPage(evt.pageNumber);
    };
    const onScaleChanging = (evt: { scale: number }) => {
      setScale(evt.scale);
    };

    async function init() {
      try {
        setLoadProgress({ progress: 70, label: "加载渲染引擎…", indeterminate: true });
        await workerSrcReady;
        const pdfjsViewer = await loadPdfJsViewer();
        if (cancelled || !viewerElement || !container) return;

        setLoadProgress({ progress: 74, label: "初始化 PDF 视图…", indeterminate: true });

        viewerElement.innerHTML = "";
        eventBus = new pdfjsViewer.EventBus();
        eventBusRef.current = eventBus;
        linkService = new pdfjsViewer.PDFLinkService({ eventBus });
        const findController = new pdfjsViewer.PDFFindController({ eventBus, linkService });
        pdfViewer = new pdfjsViewer.PDFViewer({
          container,
          viewer: viewerElement,
          eventBus,
          linkService,
          findController,
          textLayerMode: 2,
          annotationEditorMode: pdfjsLib.AnnotationEditorType.DISABLE,
        });
        pdfViewerRef.current = pdfViewer;
        linkService.setViewer(pdfViewer);

        eventBus.on("pagechanging", onPageChanging);
        eventBus.on("scalechanging", onScaleChanging);

        setLoadProgress({ progress: 72, label: "下载 PDF 文件…", indeterminate: true });
        pdfDocument = await loadPdfDocumentFromUrls(
          candidateUrls,
          applyLoadProgress,
          abortController.signal,
        );
        if (cancelled) return;

        pdfDocumentRef.current = pdfDocument;
        setLoadProgress({ progress: 99, label: "渲染页面…", indeterminate: false });
        pdfViewer.setDocument(pdfDocument);
        linkService.setDocument(pdfDocument, null);
        setTotalPages(pdfDocument.numPages);

        const prefs = readReaderPrefs(resourceId);
        const savedScale = prefs.scale;
        if (savedScale && savedScale >= 0.5 && savedScale <= 3) {
          pdfViewer.currentScaleValue = String(savedScale);
          setScale(savedScale);
        }

        const savedPage = prefs.page;
        const initialPage = savedPage && savedPage >= 1 && savedPage <= pdfDocument.numPages
          ? savedPage
          : 1;
        if (initialPage > 1) {
          pdfViewer.currentPageNumber = initialPage;
          setCurrentPage(initialPage);
        }

        refreshPdfLayout();
        cancelScheduledLayout = schedulePdfViewerUpdate(refreshPdfLayout);
        setLoading(false);
        setViewerReady(true);
        logReaderPerf("pdf_ready", {
          resourceId,
          elapsedMs: Math.round(performance.now() - loadStartedAtRef.current),
          totalPages: pdfDocument.numPages,
        });
      } catch (initError) {
        if (cancelled || initError instanceof PdfLoadAbortedError) return;
        const message = initError instanceof Error ? initError.message : "PDF 加载失败";
        onLoadErrorRef.current?.(message);
        if (!onLoadErrorRef.current) {
          console.error(initError);
        }
        setLoading(false);
      }
    }

    init();
    return () => {
      cancelled = true;
      abortController.abort();
      cancelScheduledLayout?.();
      if (loadProgressRafRef.current !== null) {
        window.cancelAnimationFrame(loadProgressRafRef.current);
        loadProgressRafRef.current = null;
      }
      if (layoutUpdateRafRef.current !== null) {
        window.cancelAnimationFrame(layoutUpdateRafRef.current);
        layoutUpdateRafRef.current = null;
      }

      eventBus?.off("pagechanging", onPageChanging);
      eventBus?.off("scalechanging", onScaleChanging);

      try {
        (pdfViewer as { setDocument: (doc: unknown) => void }).setDocument(null);
      } catch {
        // pdf.js 部分版本 setDocument(null) 可能抛错，忽略
      }
      pdfDocumentRef.current = null;
      void pdfDocument?.destroy();

      if (viewerElement) {
        viewerElement.innerHTML = "";
      }

      evictPdfBytesCache(candidateUrls);
      pdfViewerRef.current = null;
      eventBusRef.current = null;
      setViewerReady(false);
    };
  }, [
    applyLoadProgress,
    layoutReady,
    pdfFallbackUrl,
    pdfUrl,
    refreshPdfLayout,
    resourceId,
    setCurrentPage,
    setLoading,
    setScale,
    setTotalPages,
  ]);

  useEffect(() => {
    if (!viewerReady) return;
    const wrap = scrollWrapRef.current;
    if (!wrap) return;

    scheduleLayoutRefresh();
    const observer = new ResizeObserver(() => scheduleLayoutRefresh());
    observer.observe(wrap);
    window.addEventListener("resize", scheduleLayoutRefresh);
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", scheduleLayoutRefresh);
    };
  }, [scheduleLayoutRefresh, viewerReady]);

  useEffect(() => {
    if (!viewerReady) return;
    scheduleLayoutRefresh();
  }, [layoutRefreshKey, scheduleLayoutRefresh, state.scale, viewerReady]);

  useEffect(() => {
    if (!evidenceHighlight?.pageNumber || !viewerReady) return;
    const rects = resolveEvidenceFlashRects(evidenceHighlight, overlayDoc.blocks, {
      pageBlocksLoaded: evidencePageBlocksLoaded,
    });
    if (rects.length > 0) {
      scrollToFlashRects(rects);
      return;
    }
    goToPage(evidenceHighlight.pageNumber);
  }, [
    evidenceHighlight,
    evidencePageBlocksLoaded,
    goToPage,
    overlayDoc.blocks,
    scrollToFlashRects,
    viewerReady,
  ]);

  useEffect(() => () => {
    if (flashTimeoutRef.current !== null) {
      window.clearTimeout(flashTimeoutRef.current);
    }
  }, []);

  return (
    <div className="document-reader-shell pdf-js-document-reader">
      <ReaderToolbar
        title={title}
        currentPage={state.currentPage}
        totalPages={state.totalPages}
        hasEvidenceHighlight={Boolean(evidenceHighlight)}
        onPreviousPage={() => goToPage(state.currentPage - 1)}
        onNextPage={() => goToPage(state.currentPage + 1)}
        onJumpToPage={goToPage}
        onClearHighlight={() => onClearEvidenceHighlight?.()}
      />

      <div className="pdf-reader-toolbar-extra">
        <div className="pdf-reader-scale-controls">
          <button type="button" aria-label="缩小" onClick={() => applyScale(state.scale - 0.1)}>
            <Minus size={14} />
          </button>
          <span>{Math.round(state.scale * 100)}%</span>
          <button type="button" aria-label="放大" onClick={() => applyScale(state.scale + 0.1)}>
            <Plus size={14} />
          </button>
        </div>
        <button
          type="button"
          className={`pdf-reader-search-toggle${state.searchOpen ? " is-active" : ""}`}
          onClick={() => toggleSearch()}
        >
          <Search size={14} />
          搜索
        </button>
      </div>

      <PdfTextSearch
        open={state.searchOpen}
        query={state.searchQuery}
        onQueryChange={setSearchQuery}
        onClose={() => toggleSearch(false)}
        eventBus={eventBusRef.current}
      />

      <div className={`document-reader-body${sidebarCollapsed ? " sidebar-collapsed" : ""}`}>
        <PdfReaderSidebar
          collapsed={sidebarCollapsed}
          currentPage={state.currentPage}
          outlineItems={outlineItems}
          onGoToPage={goToPage}
          onToggleCollapsed={() => setSidebarCollapsed((value) => !value)}
        />

        <div className="document-reader-scroll pdf-viewer-scroll-wrap" ref={scrollWrapRef}>
          {state.loading ? (
            <ReaderLoadingProgress
              progress={loadProgress.progress}
              label={loadProgress.label}
              indeterminate={loadProgress.indeterminate}
            />
          ) : null}
          <div className="pdf-viewer-container" ref={containerRef}>
            <div className="pdfViewer" ref={viewerRef} />
          </div>
        </div>
      </div>

      {!state.loading && viewerReady && (
        <PdfHighlightLayer
          blocks={overlayDoc.blocks}
          pageSizes={pageSizes}
          viewerElement={viewerRef.current}
          activeBlock={state.activeBlock}
          flashRects={state.flashRects}
          onBlockHover={setActiveBlock}
          onBlockClick={setActiveBlock}
          onEvent={subscribeEvent}
        />
      )}
      <ReaderSelectionToolbar containerRef={containerRef} />
    </div>
  );
}

function outlineToSidebarItem(item: PdfReaderDocument["outline"][number]): OutlineItem {
  const children = item.children?.map(outlineToSidebarItem) ?? [];
  return {
    id: item.id,
    title: item.title,
    pageNumber: item.page,
    level: item.level,
    children,
  };
}
