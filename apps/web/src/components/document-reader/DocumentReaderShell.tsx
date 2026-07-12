import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { BundleRaw } from "../../services/documentApi";
import { ParsedDocumentRenderer } from "./ParsedDocumentRenderer";
import { ReaderLoadingProgress } from "./ReaderLoadingProgress";
import { ReaderToolbar } from "./ReaderToolbar";
import { ReaderToc } from "./ReaderToc";
import {
  clampPageNumber,
  extractTocItems,
  getNextPageNumber,
  getPageNumbers,
  getPreviousPageNumber,
  pageAnchorId,
  resolveActiveTocId,
  resolveVisiblePageNumber,
} from "./readerUtils";
import type { EvidenceHighlight, ReaderTocItem } from "./types";

export function DocumentReaderShell({
  title,
  bundle,
  loading,
  error,
  evidenceHighlight,
  onClearEvidenceHighlight,
  sourceVersionId,
}: {
  title: string;
  bundle: BundleRaw | null;
  loading: boolean;
  error: string;
  evidenceHighlight?: EvidenceHighlight | null;
  onClearEvidenceHighlight?: () => void;
  sourceVersionId?: string | null;
}) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [activeTocId, setActiveTocId] = useState<string | null>(null);

  const pageNumbers = useMemo(
    () => (bundle ? getPageNumbers(bundle) : []),
    [bundle],
  );
  const tocItems = useMemo(
    () => (bundle ? extractTocItems(bundle) : []),
    [bundle],
  );

  const scrollToPage = useCallback((pageNumber: number) => {
    const clamped = clampPageNumber(pageNumber, pageNumbers);
    const el = document.getElementById(pageAnchorId(clamped));
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
    setCurrentPage(clamped);
  }, [pageNumbers]);

  const scrollToTocItem = useCallback((item: ReaderTocItem) => {
    const el = document.getElementById(item.id);
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
    setActiveTocId(item.id);
    setCurrentPage(item.pageNumber);
  }, []);

  useEffect(() => {
    if (!bundle || pageNumbers.length === 0) return;
    if (evidenceHighlight?.pageNumber) {
      scrollToPage(evidenceHighlight.pageNumber);
      return;
    }
    setCurrentPage(pageNumbers[0]);
  }, [bundle?.id, evidenceHighlight?.evidenceId, evidenceHighlight?.pageNumber, pageNumbers, scrollToPage]);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container || !bundle) return;

    let rafId: number | null = null;
    const handleScroll = () => {
      if (rafId !== null) return;
      rafId = window.requestAnimationFrame(() => {
        rafId = null;
        const scrollTop = container.scrollTop;
        setCurrentPage(resolveVisiblePageNumber(pageNumbers, container));
        setActiveTocId(resolveActiveTocId(tocItems, container));
      });
    };

    container.addEventListener("scroll", handleScroll, { passive: true });
    handleScroll();

    const resizeObserver = new ResizeObserver(handleScroll);
    resizeObserver.observe(container);

    return () => {
      container.removeEventListener("scroll", handleScroll);
      resizeObserver.disconnect();
      if (rafId !== null) window.cancelAnimationFrame(rafId);
    };
  }, [bundle, pageNumbers, tocItems]);

  if (loading) {
    return (
      <div className="document-reader-shell reader-loading-shell">
        <ReaderLoadingProgress
          progress={62}
          label="加载文档内容…"
          indeterminate
        />
      </div>
    );
  }
  if (error) {
    return <p className="cw-preview-text reader-shell-message">{error}</p>;
  }
  if (!bundle) {
    return <p className="cw-preview-text reader-shell-message">无法加载文档内容。</p>;
  }

  const totalPages = pageNumbers.length;
  const previousPage = getPreviousPageNumber(pageNumbers, currentPage);
  const nextPage = getNextPageNumber(pageNumbers, currentPage);

  return (
    <div className="document-reader-shell">
      <ReaderToolbar
        title={title}
        currentPage={currentPage}
        totalPages={totalPages}
        hasEvidenceHighlight={Boolean(evidenceHighlight)}
        onPreviousPage={() => previousPage !== null && scrollToPage(previousPage)}
        onNextPage={() => nextPage !== null && scrollToPage(nextPage)}
        onJumpToPage={scrollToPage}
        onClearHighlight={() => onClearEvidenceHighlight?.()}
      />

      <div className="document-reader-body">
        <ReaderToc
          items={tocItems}
          activeId={activeTocId}
          onItemClick={scrollToTocItem}
        />

        <div className="document-reader-scroll" ref={scrollRef}>
          <ParsedDocumentRenderer
            bundle={bundle}
            evidenceHighlight={evidenceHighlight}
            activePageNumber={currentPage}
            sourceVersionId={sourceVersionId}
          />
        </div>
      </div>
    </div>
  );
}
