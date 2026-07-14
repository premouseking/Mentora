import { ChevronLeft, ChevronRight, Highlighter, X } from "lucide-react";
import { useEffect, useState } from "react";

export function ReaderToolbar({
  title,
  currentPage,
  totalPages,
  hasEvidenceHighlight,
  onPreviousPage,
  onNextPage,
  onJumpToPage,
  onClearHighlight,
}: {
  title: string;
  currentPage: number;
  totalPages: number;
  hasEvidenceHighlight: boolean;
  onPreviousPage: () => void;
  onNextPage: () => void;
  onJumpToPage: (pageNumber: number) => void;
  onClearHighlight: () => void;
}) {
  const [pageInput, setPageInput] = useState(String(currentPage));

  useEffect(() => {
    setPageInput(String(currentPage));
  }, [currentPage]);

  function submitJump() {
    const parsed = Number.parseInt(pageInput, 10);
    if (Number.isNaN(parsed)) return;
    onJumpToPage(parsed);
  }

  return (
    <header className="reader-toolbar">
      <div className="reader-toolbar-title">
        <span className="reader-toolbar-kicker">资料阅读</span>
        <strong>{title}</strong>
      </div>

      <div className="reader-toolbar-controls">
        <button type="button" className="reader-toolbar-btn" onClick={onPreviousPage} aria-label="上一页">
          <ChevronLeft size={16} />
        </button>
        <span className="reader-toolbar-page-indicator">
          第 {currentPage} / {totalPages} 页
        </span>
        <button type="button" className="reader-toolbar-btn" onClick={onNextPage} aria-label="下一页">
          <ChevronRight size={16} />
        </button>

        <label className="reader-toolbar-jump">
          <span>跳转</span>
          <input
            type="number"
            min={1}
            max={totalPages}
            value={pageInput}
            onChange={(event) => setPageInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") submitJump();
            }}
          />
          <button type="button" onClick={submitJump}>前往</button>
        </label>

        {hasEvidenceHighlight && (
          <button type="button" className="reader-toolbar-clear" onClick={onClearHighlight}>
            <Highlighter size={14} />
            <span>清除高亮</span>
            <X size={12} />
          </button>
        )}
      </div>
    </header>
  );
}
