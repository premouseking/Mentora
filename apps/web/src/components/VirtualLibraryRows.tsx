import { useMemo, useRef, useState, type ReactNode } from "react";

const ROW_HEIGHT = 62;
const OVERSCAN = 8;

/** 轻量窗口化列表，避免大资源库一次性渲染全部 DOM。 */
export function VirtualLibraryRows<T>({
  items,
  renderRow,
}: {
  items: T[];
  renderRow: (item: T, index: number) => ReactNode;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(640);

  const { start, end, offsetY, totalHeight } = useMemo(() => {
    const startIndex = Math.max(0, Math.floor(scrollTop / ROW_HEIGHT) - OVERSCAN);
    const visibleCount = Math.ceil(viewportHeight / ROW_HEIGHT) + OVERSCAN * 2;
    const endIndex = Math.min(items.length, startIndex + visibleCount);
    return {
      start: startIndex,
      end: endIndex,
      offsetY: startIndex * ROW_HEIGHT,
      totalHeight: items.length * ROW_HEIGHT,
    };
  }, [items.length, scrollTop, viewportHeight]);

  if (items.length <= 40) {
    return <>{items.map((item, index) => renderRow(item, index))}</>;
  }

  return (
    <div
      ref={(node) => {
        containerRef.current = node;
        if (node) setViewportHeight(node.clientHeight || 640);
      }}
      onScroll={(event) => setScrollTop(event.currentTarget.scrollTop)}
      className="library-virtual-scroll"
    >
      <div style={{ height: totalHeight, position: "relative" }}>
        <div style={{ transform: `translateY(${offsetY}px)` }}>
          {items.slice(start, end).map((item, index) => renderRow(item, start + index))}
        </div>
      </div>
    </div>
  );
}
