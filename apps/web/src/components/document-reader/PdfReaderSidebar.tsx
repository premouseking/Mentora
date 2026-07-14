import { ChevronLeft, ChevronRight, ListTree } from "lucide-react";

import type { OutlineItem } from "./pdfReaderUtils";

interface PdfReaderSidebarProps {
  outlineItems: OutlineItem[];
  currentPage: number;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onGoToPage: (pageNumber: number) => void;
}

/** PDF 阅读器侧栏：仅目录，支持收起以扩大阅读区。 */
export function PdfReaderSidebar({
  outlineItems,
  currentPage,
  collapsed,
  onToggleCollapsed,
  onGoToPage,
}: PdfReaderSidebarProps) {
  if (collapsed) {
    return (
      <aside className="pdf-reader-sidebar is-collapsed">
        <button
          className="pdf-reader-sidebar-toggle"
          onClick={onToggleCollapsed}
          type="button"
          aria-label="展开目录"
          title="展开目录"
        >
          <ChevronRight size={16} />
        </button>
        <button
          className="pdf-reader-sidebar-icon"
          onClick={onToggleCollapsed}
          type="button"
          aria-label="目录"
          title="目录"
        >
          <ListTree size={16} />
        </button>
      </aside>
    );
  }

  return (
    <aside className="pdf-reader-sidebar">
      <div className="pdf-reader-sidebar-header">
        <span className="pdf-reader-sidebar-title">目录</span>
        <button
          className="pdf-reader-sidebar-toggle"
          onClick={onToggleCollapsed}
          type="button"
          aria-label="收起目录"
          title="收起目录"
        >
          <ChevronLeft size={16} />
        </button>
      </div>

      {outlineItems.length > 0 ? (
        <ul className="pdf-reader-outline-list">
          {outlineItems.map((item) => (
            <li key={item.id} style={{ paddingLeft: `${(item.level - 1) * 12}px` }}>
              <button
                className={item.pageNumber === currentPage ? "is-active" : ""}
                onClick={() => onGoToPage(item.pageNumber)}
                type="button"
              >
                {item.title}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="reader-toc-empty">暂无目录</p>
      )}
    </aside>
  );
}
