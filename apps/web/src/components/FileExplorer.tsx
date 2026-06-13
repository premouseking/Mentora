import { useState, useRef, useEffect, useCallback } from "react";
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
  // null = use flex; number[] = explicit pixel heights after resize
  const [heights, setHeights] = useState<number[] | null>(null);

  // Reset heights to flex mode when visible sections change
  useEffect(() => {
    setHeights(null);
    initialHeightsRef.current = null;
  }, [detachedSections.size]);

  /* ── Resize by dragging between sections ── */
  const dragIdx = useRef<number | null>(null);
  const onMoveRef = useRef<((e: MouseEvent) => void) | null>(null);

  const onMoveHandler = useCallback((e: MouseEvent) => {
    if (dragIdx.current === null || !containerRef.current) return;
    e.preventDefault();

    const idx = dragIdx.current;
    const containerRect = containerRef.current.getBoundingClientRect();
    const handleH = 6;
    const count = visibleSections.length;
    // heights are full section heights (including 26px titles), so just subtract handles
    const totalH = containerRect.height - (count - 1) * handleH;
    const y = e.clientY - containerRect.top;

    // Use ref for initial heights (sync, avoids async setHeights race)
    const base = initialHeightsRef.current ?? visibleSections.map(() => Math.floor(totalH / count));

    const next = [...base];
    let acc = 0;
    for (let i = 0; i < count; i++) {
      if (i === idx) {
        const minOthers = (count - idx - 1) * 80 + (count - idx - 1) * handleH;
        const rawH = y - acc;
        next[i] = Math.max(80, Math.min(totalH - minOthers - (acc - (acc > 0 ? handleH * (i) : 0)), rawH));
        // simpler: clamp within bounds
        next[i] = Math.max(80, Math.min(totalH - (count - 1) * 80, rawH));
      }
      acc += next[i];
      if (i < count - 1) acc += handleH;
    }
    // Last section gets the remainder
    const sumOthers = next.slice(0, -1).reduce((a, b) => a + b, 0) + (count - 1) * handleH;
    next[count - 1] = Math.max(80, totalH - sumOthers + (count - 1) * handleH);

    setHeights(next);
    initialHeightsRef.current = next;
  }, [visibleSections]);

  onMoveRef.current = onMoveHandler;

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
      {visibleSections.map((section, i) => (
        <div key={section.key}>
          {i > 0 && (
            <div
              className="fe-resize-handle"
              onMouseDown={() => {
                // Capture current heights synchronously into ref (avoids async race)
                if (containerRef.current) {
                  const els = containerRef.current.querySelectorAll<HTMLElement>(".fe-section");
                  const currentHeights = Array.from(els).map((el) => el.getBoundingClientRect().height);
                  if (currentHeights.length === visibleSections.length) {
                    initialHeightsRef.current = currentHeights;
                    setHeights(currentHeights);
                  }
                }
                dragIdx.current = i - 1;
                document.body.style.cursor = "row-resize";
                document.body.style.userSelect = "none";
                document.addEventListener("mousemove", onMoveHandler);
                document.addEventListener("mouseup", onUpHandler);
              }}
            />
          )}
          <div
            className="fe-section"
            style={heights ? { flex: "0 0 auto", height: heights[i] } : { flex: 1 }}
          >
            <div className={`fe-section-title${i > 0 ? " sub" : ""}`}>
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
            <div className="fe-section-content">
              {renderSectionContent(section)}
            </div>
          </div>
        </div>
      ))}
    </aside>
  );
}
