/**
 * pdf.js 全文搜索控件（经 EventBus 驱动 PDFFindController）。
 */
import { Search, X } from "lucide-react";
import { useEffect, useRef } from "react";

interface PdfFindEventBus {
  dispatch: (eventName: string, data: Record<string, unknown>) => void;
}

interface PdfTextSearchProps {
  open: boolean;
  query: string;
  onQueryChange: (query: string) => void;
  onClose: () => void;
  eventBus: PdfFindEventBus | null;
}

export function PdfTextSearch({
  open,
  query,
  onQueryChange,
  onClose,
  eventBus,
}: PdfTextSearchProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!eventBus || !open) return;
    eventBus.dispatch("find", {
      type: "",
      query,
      caseSensitive: false,
      highlightAll: true,
      findPrevious: false,
    });
  }, [eventBus, open, query]);

  if (!open) return null;

  function findNext() {
    eventBus?.dispatch("findagain", {
      type: "",
      query,
      caseSensitive: false,
      highlightAll: true,
      findPrevious: false,
    });
  }

  function findPrevious() {
    eventBus?.dispatch("findagain", {
      type: "",
      query,
      caseSensitive: false,
      highlightAll: true,
      findPrevious: true,
    });
  }

  return (
    <div className="pdf-text-search">
      <Search size={14} />
      <input
        ref={inputRef}
        type="search"
        placeholder="搜索 PDF 正文…"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && e.shiftKey) findPrevious();
          else if (e.key === "Enter") findNext();
          if (e.key === "Escape") onClose();
        }}
      />
      <button type="button" className="pdf-text-search-btn" onClick={findPrevious}>
        上一个
      </button>
      <button type="button" className="pdf-text-search-btn" onClick={findNext}>
        下一个
      </button>
      <button type="button" className="pdf-text-search-close" onClick={onClose} aria-label="关闭搜索">
        <X size={14} />
      </button>
    </div>
  );
}
