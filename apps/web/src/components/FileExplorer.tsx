import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  ChevronDown,
  ChevronRight,
  File,
  Folder,
  FolderOpen,
  BrainCircuit,
  BookOpen,
  Lightbulb,
  PenLine,
  AlertTriangle,
  PanelRightClose,
  XCircle,
} from "lucide-react";
import type { FileNode } from "../data/files";
import type { AiExplanation } from "../data/aiExplanations";
import type { MistakeItem } from "../data/mistakes";

export type SectionKey = "file" | "ai" | "mistakes";

const ICON_SIZE = 14;

function FileIcon({ ext }: { ext?: string }) {
  if (ext === ".quiz" || ext === ".check") return <span className="fe-icon quiz">?</span>;
  if (ext === ".lab") return <span className="fe-icon lab">⚗</span>;
  if (ext === ".html") return <span className="fe-icon html">◇</span>;
  return <File size={ICON_SIZE} />;
}

function TreeNode({
  node,
  selectedId,
  onSelect,
  depth = 0,
}: {
  node: FileNode;
  selectedId: string | null;
  onSelect: (id: string) => void;
  depth?: number;
}) {
  const [open, setOpen] = useState(depth < 1);

  if (node.type === "folder") {
    return (
      <div className="fe-node">
        <button
          className={`fe-row${selectedId === node.id ? " selected" : ""}`}
          style={{ paddingLeft: 8 + depth * 16 }}
          onClick={() => {
            setOpen((v) => !v);
            onSelect(node.id);
          }}
        >
          <span className="fe-chevron">
            {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
          </span>
          {open ? <FolderOpen size={ICON_SIZE} /> : <Folder size={ICON_SIZE} />}
          <span className="fe-name">{node.name}</span>
        </button>
        {open &&
          node.children?.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              selectedId={selectedId}
              onSelect={onSelect}
              depth={depth + 1}
            />
          ))}
      </div>
    );
  }

  return (
    <button
      className={`fe-row${selectedId === node.id ? " selected" : ""}`}
      style={{ paddingLeft: 28 + depth * 16 }}
      onClick={() => onSelect(node.id)}
    >
      <FileIcon ext={node.extension} />
      <span className="fe-name">{node.name}</span>
    </button>
  );
}

function AiTypeIcon({ type }: { type: AiExplanation["type"] }) {
  if (type === "解题思路") return <Lightbulb size={ICON_SIZE} className="fe-ai-icon solve" />;
  if (type === "知识点讲解") return <BookOpen size={ICON_SIZE} className="fe-ai-icon explain" />;
  if (type === "错题分析") return <AlertTriangle size={ICON_SIZE} className="fe-ai-icon mistake" />;
  if (type === "公式推导") return <PenLine size={ICON_SIZE} className="fe-ai-icon formula" />;
  return <BrainCircuit size={ICON_SIZE} />;
}

function MistakeDiffBadge({ difficulty }: { difficulty: MistakeItem["difficulty"] }) {
  const colors: Record<string, string> = { 简单: "#4dab7a", 中等: "#e6a817", 困难: "#e05555" };
  return (
    <span className="fe-mistake-badge" style={{ color: colors[difficulty], borderColor: colors[difficulty] }}>
      {difficulty}
    </span>
  );
}

type SectionInfo = {
  key: SectionKey;
  title: string;
  icon: React.ReactNode;
};

const SECTIONS: SectionInfo[] = [
  { key: "file", title: "课程文件", icon: <Folder size={12} /> },
  { key: "ai", title: "AI 讲解", icon: <BrainCircuit size={12} /> },
  { key: "mistakes", title: "错题集", icon: <XCircle size={12} /> },
];

export function FileExplorer({
  files,
  aiItems,
  mistakeItems,
  selectedFileId,
  selectedAiId,
  selectedMistakeId,
  onSelectFile,
  onSelectAi,
  onSelectMistake,
  detachedSections,
  onToggleDetach,
}: {
  files: FileNode[];
  aiItems: AiExplanation[];
  mistakeItems: MistakeItem[];
  selectedFileId: string | null;
  selectedAiId: string | null;
  selectedMistakeId: string | null;
  onSelectFile: (id: string) => void;
  onSelectAi: (id: string) => void;
  onSelectMistake: (id: string) => void;
  detachedSections: Set<SectionKey>;
  onToggleDetach: (section: SectionKey) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const initialHeightsRef = useRef<number[] | null>(null);

  const visibleSections = SECTIONS.filter((s) => !detachedSections.has(s.key));
  // null = flex mode; number[] = fraction per section (always sums to 1)
  const [heights, setHeights] = useState<number[] | null>(null);

  /* ── Collapse / expand ── */
  const [collapsedSections, setCollapsedSections] = useState<Set<SectionKey>>(new Set());

  const toggleCollapse = useCallback((key: SectionKey) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  // Sort: expanded sections first (original order), collapsed sections last (original order)
  const sortedSections = visibleSections
    .map((s, i) => ({ section: s, originalIndex: i }))
    .sort((a, b) => {
      const aCollapsed = collapsedSections.has(a.section.key);
      const bCollapsed = collapsedSections.has(b.section.key);
      if (aCollapsed === bCollapsed) return a.originalIndex - b.originalIndex;
      return aCollapsed ? 1 : -1;
    })
    .map(({ section }) => section);

  // Reset heights to flex mode when sections or collapse state change
  useEffect(() => {
    setHeights(null);
    initialHeightsRef.current = null;
  }, [detachedSections.size, collapsedSections.size]);

  // Split sections into expanded and collapsed groups
  const expandedSections = sortedSections.filter((s) => !collapsedSections.has(s.key));
  const collapsedList = sortedSections.filter((s) => collapsedSections.has(s.key));

  /* ── Resize by dragging between sections ── */
  const dragIdx = useRef<number | null>(null);
  const dragStartY = useRef(0);
  const dragStartRatios = useRef<number[]>([]);
  const dragAreaHeight = useRef(0);

  const onMoveHandler = useCallback((e: MouseEvent) => {
    if (dragIdx.current === null || dragAreaHeight.current <= 0) return;
    e.preventDefault();
    const idx = dragIdx.current;
    const base = dragStartRatios.current;
    const dy = (e.clientY - dragStartY.current) / dragAreaHeight.current;
    const minRatio = 80 / dragAreaHeight.current;
    const next = [...base];
    // Only adjust the two adjacent sections — they cancel each other out
    const newAbove = base[idx] + dy;
    const newBelow = base[idx + 1] - dy;
    if (newAbove < minRatio) {
      next[idx] = minRatio;
      next[idx + 1] = base[idx] + base[idx + 1] - minRatio;
    } else if (newBelow < minRatio) {
      next[idx] = base[idx] + base[idx + 1] - minRatio;
      next[idx + 1] = minRatio;
    } else {
      next[idx] = newAbove;
      next[idx + 1] = newBelow;
    }
    setHeights(next);
  }, []);

  const onUpHandler = useCallback(() => {
    dragIdx.current = null;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", onMoveHandler);
    document.removeEventListener("mouseup", onUpHandler);
  }, [onMoveHandler]);

  const renderSectionContent = (section: SectionInfo) => {
    switch (section.key) {
      case "file":
        return files.map((node) => (
          <TreeNode key={node.id} node={node} selectedId={selectedFileId} onSelect={onSelectFile} />
        ));
      case "ai":
        return aiItems.map((item) => (
          <button
            key={item.id}
            className={`fe-row${selectedAiId === item.id ? " selected" : ""}`}
            style={{ paddingLeft: 8 }}
            onClick={() => onSelectAi(item.id)}
          >
            <AiTypeIcon type={item.type} />
            <div className="fe-ai-info">
              <span className="fe-ai-title">{item.title}</span>
              <span className="fe-ai-topic">{item.topic}</span>
            </div>
          </button>
        ));
      case "mistakes":
        return mistakeItems.map((item) => (
          <button
            key={item.id}
            className={`fe-row${selectedMistakeId === item.id ? " selected" : ""}`}
            style={{ paddingLeft: 8 }}
            onClick={() => onSelectMistake(item.id)}
          >
            <AlertTriangle size={ICON_SIZE} className="fe-ai-icon mistake" />
            <div className="fe-ai-info">
              <span className="fe-ai-title">{item.title}</span>
              <div className="fe-mistake-meta">
                <MistakeDiffBadge difficulty={item.difficulty} />
                <span className="fe-mistake-count">错 {item.wrongCount} 次</span>
              </div>
            </div>
          </button>
        ));
    }
  };

  return (
    <aside className="file-explorer" ref={containerRef}>
      {/* Expanded section area — resize handles + sections are direct children */}
      {expandedSections.length > 0 && (
        <div className="fe-expanded-area">
          {expandedSections.map((section, i) => {
            const style = heights
              ? { flex: `0 0 ${(heights[i] * 100).toFixed(2)}%` }
              : { flex: 1, minHeight: 80 };
            return (
            <React.Fragment key={section.key}>
                {i > 0 && (
                <div
                  className="fe-resize-handle"
                  onMouseDown={(e) => {
                    const area = containerRef.current?.querySelector<HTMLElement>(".fe-expanded-area");
                    if (!area) return;
                    const areaH = area.getBoundingClientRect().height;
                    if (areaH <= 0) return;
                    const els = area.querySelectorAll<HTMLElement>(":scope > .fe-section");
                    const pixelHeights = Array.from(els).map((el) => el.getBoundingClientRect().height);
                    if (pixelHeights.length < 2) return;
                    // Convert to ratios (sum = 1)
                    const total = pixelHeights.reduce((a, b) => a + b, 0);
                    const ratios = pixelHeights.map((h) => h / total);
                    dragStartRatios.current = ratios;
                    dragStartY.current = e.clientY;
                    dragAreaHeight.current = areaH;
                    setHeights(ratios);
                    dragIdx.current = i - 1;
                    document.body.style.cursor = "row-resize";
                    document.body.style.userSelect = "none";
                    document.addEventListener("mousemove", onMoveHandler);
                    document.addEventListener("mouseup", onUpHandler);
                  }}
                />
              )}
              <div className="fe-section" style={style}>
                <div className={`fe-section-title${i > 0 ? " sub" : ""}`}>
                  <button className="fe-collapse-toggle" onClick={() => toggleCollapse(section.key)} title="收起">
                    <ChevronDown size={12} />
                  </button>
                  {section.icon}
                  <span>{section.title}</span>
                  <button className="fe-ai-popout" onClick={() => onToggleDetach(section.key)} title="移到右侧">
                    <PanelRightClose size={14} />
                  </button>
                </div>
                <div className="fe-section-content">
                  {renderSectionContent(section)}
                </div>
              </div>
            </React.Fragment>
            );
          })}
        </div>
      )}

      {/* Collapsed section area — fixed height, pinned to bottom */}
      {collapsedList.length > 0 && (
        <div className="fe-collapsed-area">
          {collapsedList.map((section) => (
            <div key={section.key} className="fe-section collapsed" style={{ flex: "0 0 auto", height: 26 }}>
                <div className="fe-section-title collapsed-title">
                  <button
                    className="fe-collapse-toggle"
                    onClick={() => toggleCollapse(section.key)}
                    title="展开"
                  >
                    <ChevronRight size={12} />
                  </button>
                  {section.icon}
                  <span>{section.title}</span>
                  <button
                    className="fe-ai-popout"
                    onClick={() => onToggleDetach(section.key)}
                    title="移到右侧"
                  >
                    <PanelRightClose size={14} />
                  </button>
                </div>
              </div>
          ))}
        </div>
      )}
    </aside>
  );
}
