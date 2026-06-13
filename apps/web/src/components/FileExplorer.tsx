import { useState, useRef } from "react";
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
} from "lucide-react";
import type { FileNode } from "../data/files";
import type { AiExplanation } from "../data/aiExplanations";

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

export function FileExplorer({
  files,
  aiItems,
  selectedFileId,
  selectedAiId,
  onSelectFile,
  onSelectAi,
  aiDetached,
  onDetachAi,
}: {
  files: FileNode[];
  aiItems: AiExplanation[];
  selectedFileId: string | null;
  selectedAiId: string | null;
  onSelectFile: (id: string) => void;
  onSelectAi: (id: string) => void;
  aiDetached: boolean;
  onDetachAi: () => void;
}) {
  const [topHeight, setTopHeight] = useState(280);
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const onMoveRef = useRef<((e: MouseEvent) => void) | null>(null);

  onMoveRef.current = (e: MouseEvent) => {
    if (!containerRef.current) return;
    e.preventDefault();
    const rect = containerRef.current.getBoundingClientRect();
    const h = 36;
    const newH = e.clientY - rect.top - h;
    const max = rect.height - h - 10 - 120;
    setTopHeight(Math.max(100, Math.min(max, newH)));
  };

  const onMoveHandler = (e: MouseEvent) => {
    if (!draggingRef.current) return;
    onMoveRef.current?.(e);
  };
  const onUpHandler = () => {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", onMoveHandler);
    document.removeEventListener("mouseup", onUpHandler);
  };

  return (
    <aside className="file-explorer" ref={containerRef}>
      <div className="fe-header"><span>课程文件</span></div>

      <div className="fe-section" style={{ flex: aiDetached ? 1 : undefined, height: aiDetached ? "auto" : topHeight }}>
        <div className="fe-section-title"><span>资源管理器</span></div>
        <div className="fe-section-content">
          {files.map((node) => (
            <TreeNode
              key={node.id}
              node={node}
              selectedId={selectedFileId}
              onSelect={onSelectFile}
            />
          ))}
        </div>
      </div>

      {!aiDetached && (
        <>
          <div
            className="fe-resize-handle"
            onMouseDown={() => {
              draggingRef.current = true;
              document.body.style.cursor = "row-resize";
              document.body.style.userSelect = "none";
              document.addEventListener("mousemove", onMoveHandler);
              document.addEventListener("mouseup", onUpHandler);
            }}
          />
          <div className="fe-section" style={{ flex: 1 }}>
            <div className="fe-section-title ai">
              <BrainCircuit size={12} />
              <span>AI 讲解</span>
              <button className="fe-ai-popout" onClick={onDetachAi} title="移到右侧">
                <PanelRightClose size={14} />
              </button>
            </div>
            <div className="fe-section-content">
              {aiItems.map((item) => (
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
              ))}
            </div>
          </div>
        </>
      )}
    </aside>
  );
}
