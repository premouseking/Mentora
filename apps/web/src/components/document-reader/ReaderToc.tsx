import { useEffect, useState } from "react";

import type { ReaderTocItem } from "./types";

export function ReaderToc({
  items,
  activeId,
  onItemClick,
}: {
  items: ReaderTocItem[];
  activeId: string | null;
  onItemClick: (item: ReaderTocItem) => void;
}) {
  const [internalActiveId, setInternalActiveId] = useState<string | null>(activeId);

  useEffect(() => {
    setInternalActiveId(activeId);
  }, [activeId]);

  if (items.length === 0) {
    return (
      <aside className="reader-toc" aria-label="目录">
        <div className="reader-toc-head">目录</div>
        <p className="reader-toc-empty">暂无标题目录</p>
      </aside>
    );
  }

  return (
    <aside className="reader-toc" aria-label="目录">
      <div className="reader-toc-head">目录</div>
      <nav className="reader-toc-list">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            className={[
              "reader-toc-item",
              `reader-toc-level-${item.level}`,
              internalActiveId === item.id ? "active" : "",
            ].filter(Boolean).join(" ")}
            onClick={() => {
              setInternalActiveId(item.id);
              onItemClick(item);
            }}
          >
            <span className="reader-toc-text">{item.text}</span>
            <span className="reader-toc-page">P{item.pageNumber}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}
