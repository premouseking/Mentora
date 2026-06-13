import { useCallback, useEffect, useRef, useState } from "react";
import {
  MoveLeft,
  BrainCircuit,
  BookOpen,
  Lightbulb,
  PenLine,
  AlertTriangle,
} from "lucide-react";
import { AppShell } from "../components/AppShell";
import { FileExplorer } from "../components/FileExplorer";
import { QuizPanel } from "../components/QuizPanel";
import { courseFiles } from "../data/files";
import { aiExplanations } from "../data/aiExplanations";
import { sampleQuestion } from "../data/quiz";

const MIN_EXPLORER = 170;
const MAX_EXPLORER = 360;
const MIN_AI_PANEL = 150;
const MAX_AI_PANEL = 400;

const ICON_SIZE = 14;

function AiTypeIcon({ type }: { type: string }) {
  if (type === "解题思路") return <Lightbulb size={ICON_SIZE} className="fe-ai-icon solve" />;
  if (type === "知识点讲解") return <BookOpen size={ICON_SIZE} className="fe-ai-icon explain" />;
  if (type === "错题分析") return <AlertTriangle size={ICON_SIZE} className="fe-ai-icon mistake" />;
  if (type === "公式推导") return <PenLine size={ICON_SIZE} className="fe-ai-icon formula" />;
  return <BrainCircuit size={ICON_SIZE} />;
}

export function CourseWorkspacePage() {
  const [quizOpen, setQuizOpen] = useState(false);
  const [tabHeld, setTabHeld] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [selectedAi, setSelectedAi] = useState<string | null>(null);
  const [explorerWidth, setExplorerWidth] = useState(220);
  const [aiDetached, setAiDetached] = useState(false);
  const [aiPanelWidth, setAiPanelWidth] = useState(220);

  const l2Ref = useRef<HTMLDivElement>(null);

  /* ── File Preview ── */
  const selectedFileName =
    selectedFile &&
    (() => {
      for (const n of courseFiles)
        for (const fn of [n, ...(n.children ?? [])])
          if (fn.id === selectedFile && fn.type === "file") return fn.name;
      return selectedFile;
    })();

  /* ── Ai Preview ── */
  const selectedAiItem = selectedAi ? aiExplanations.find((a) => a.id === selectedAi) : null;

  /* ── Top trigger → open quiz ── */
  const handleTopClick = useCallback(() => setQuizOpen(true), []);

  /* ── Swipe up → close quiz ── */
  const swipeStart = useRef<{ y: number; moved: boolean; active: boolean }>({ y: 0, moved: false, active: false });
  const handleL2PointerDown = useCallback((e: React.PointerEvent) => {
    swipeStart.current = { y: e.clientY, moved: false, active: true };
  }, []);
  const handleL2PointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!quizOpen || !swipeStart.current.active) return;
      const dy = e.clientY - swipeStart.current.y;
      if (dy < -20) swipeStart.current.moved = true;
      if (swipeStart.current.moved && l2Ref.current) {
        l2Ref.current.style.transform = `translateY(${Math.min(0, dy)}px)`;
        l2Ref.current.style.opacity = String(Math.max(0.3, 1 - Math.abs(dy) / 300));
      }
    },
    [quizOpen],
  );
  const handleL2PointerUp = useCallback(
    (e: React.PointerEvent) => {
      if (!quizOpen || !swipeStart.current.active) return;
      swipeStart.current.active = false;
      const dy = e.clientY - swipeStart.current.y;
      if (l2Ref.current) {
        l2Ref.current.style.transform = "";
        l2Ref.current.style.opacity = "";
      }
      if (swipeStart.current.moved && dy < -60) setQuizOpen(false);
    },
    [quizOpen],
  );

  /* ── Tab peek ── */
  const tabTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === "Tab" && quizOpen) {
        e.preventDefault();
        setTabHeld(true);
        if (tabTimerRef.current) clearTimeout(tabTimerRef.current);
        tabTimerRef.current = setTimeout(() => setTabHeld(false), 2000);
      }
      if (e.key === "Escape" && quizOpen) setQuizOpen(false);
    };
    const up = (e: KeyboardEvent) => {
      if (e.key === "Tab") {
        if (tabTimerRef.current) clearTimeout(tabTimerRef.current);
        setTabHeld(false);
      }
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      if (tabTimerRef.current) clearTimeout(tabTimerRef.current);
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [quizOpen]);

  /* ── Resize file explorer ── */
  const explorerResizeRef = useRef(false);
  const explorerMoveRef = useRef<((e: MouseEvent) => void) | null>(null);
  explorerMoveRef.current = (e: MouseEvent) => {
    setExplorerWidth((w) => Math.min(MAX_EXPLORER, Math.max(MIN_EXPLORER, w + e.movementX)));
  };
  const onExplorerMove = useCallback((e: MouseEvent) => {
    if (!explorerResizeRef.current) return;
    explorerMoveRef.current?.(e);
  }, []);
  const onExplorerUp = useCallback(() => {
    if (!explorerResizeRef.current) return;
    explorerResizeRef.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", onExplorerMove);
    document.removeEventListener("mouseup", onExplorerUp);
  }, [onExplorerMove]);
  const startExplorerResize = useCallback(() => {
    explorerResizeRef.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onExplorerMove);
    document.addEventListener("mouseup", onExplorerUp);
  }, [onExplorerMove, onExplorerUp]);
  useEffect(
    () => () => {
      document.removeEventListener("mousemove", onExplorerMove);
      document.removeEventListener("mouseup", onExplorerUp);
    },
    [onExplorerMove, onExplorerUp],
  );

  /* ── Resize split pane inside cw-content ── */
  const splitActive = !!(selectedFileName && selectedAiItem);
  const [splitLeftW, setSplitLeftW] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const splitResizeRef = useRef(false);
  const splitMoveRef = useRef<((e: MouseEvent) => void) | null>(null);
  splitMoveRef.current = (e: MouseEvent) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const w = e.clientX - rect.left;
    const max = rect.width - 10 - 200;
    setSplitLeftW(Math.max(150, Math.min(max, w)));
  };
  const onSplitMove = useCallback((e: MouseEvent) => {
    if (!splitResizeRef.current) return;
    splitMoveRef.current?.(e);
  }, []);
  const onSplitUp = useCallback(() => {
    if (!splitResizeRef.current) return;
    splitResizeRef.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", onSplitMove);
    document.removeEventListener("mouseup", onSplitUp);
  }, [onSplitMove]);

  // init split width when both panes appear
  useEffect(() => {
    if (splitActive && containerRef.current) {
      const w = containerRef.current.getBoundingClientRect().width;
      setSplitLeftW(Math.floor(w * 0.55));
    }
  }, [splitActive]);

  /* ── Resize AI panel (when detached to right) ── */
  const aiResizeRef = useRef(false);
  const aiMoveRef = useRef<((e: MouseEvent) => void) | null>(null);
  aiMoveRef.current = (e: MouseEvent) => {
    setAiPanelWidth((w) => Math.min(MAX_AI_PANEL, Math.max(MIN_AI_PANEL, w - e.movementX)));
  };
  const onAiResizeMove = useCallback((e: MouseEvent) => {
    if (!aiResizeRef.current) return;
    aiMoveRef.current?.(e);
  }, []);
  const onAiResizeUp = useCallback(() => {
    if (!aiResizeRef.current) return;
    aiResizeRef.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", onAiResizeMove);
    document.removeEventListener("mouseup", onAiResizeUp);
  }, [onAiResizeMove]);
  const startAiResize = useCallback(() => {
    aiResizeRef.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onAiResizeMove);
    document.addEventListener("mouseup", onAiResizeUp);
  }, [onAiResizeMove, onAiResizeUp]);
  useEffect(() => () => {
    document.removeEventListener("mousemove", onAiResizeMove);
    document.removeEventListener("mouseup", onAiResizeUp);
  }, [onAiResizeMove, onAiResizeUp]);

  /* ── Render ── */
  const showFileOverlay = quizOpen && tabHeld;

  return (
    <AppShell>
      <div className="course-workspace-new">
        {/* File Explorer */}
        <div style={{ width: explorerWidth, flexShrink: 0 }}>
          <FileExplorer
            files={courseFiles}
            aiItems={aiExplanations}
            selectedFileId={selectedFile}
            selectedAiId={selectedAi}
            onSelectFile={setSelectedFile}
            onSelectAi={setSelectedAi}
            aiDetached={aiDetached}
            onDetachAi={() => setAiDetached(true)}
          />
        </div>

        <div className="resize-handle cw-resize" onMouseDown={startExplorerResize} role="separator" aria-orientation="vertical" tabIndex={-1} />

        {/* Content Area */}
        <div className="cw-content" ref={containerRef}>
          {!quizOpen && (
            <div className="cw-top-trigger" onClick={handleTopClick}>
              <div className="cw-top-trigger-bar" />
              <span className="cw-top-hint">点击进入刷题模式</span>
            </div>
          )}

          {!selectedFileName && !selectedAiItem ? (
            /* Empty state */
            <div className="cw-file-view">
              <div className="cw-file-placeholder">
                <div className="cw-file-icon">📄</div>
                <h2>文件浏览</h2>
                <p>从左侧资源管理器选择一个文件</p>
              </div>
            </div>
          ) : splitActive ? (
            /* Split: file | AI */
            <div className="cw-split">
              <div className="cw-split-left" style={{ width: splitLeftW }}>
                <div className="cw-split-title">📄 {selectedFileName}</div>
                <div className="cw-split-content">
                  <p className="cw-preview-text">「{selectedFileName}」的内容预览将在这里显示。</p>
                </div>
              </div>
              <div
                className="cw-split-handle"
                onMouseDown={() => {
                  splitResizeRef.current = true;
                  document.body.style.cursor = "col-resize";
                  document.body.style.userSelect = "none";
                  document.addEventListener("mousemove", onSplitMove);
                  document.addEventListener("mouseup", onSplitUp);
                }}
              />
              <div className="cw-split-right">
                <div className="cw-split-title ai">
                  🧠 {selectedAiItem?.topic} · {selectedAiItem?.title}
                </div>
                <div className="cw-split-content">
                  <p className="cw-preview-text">
                    「{selectedAiItem?.title}」的 AI 讲解内容将在这里展开，包括详细解析、关键知识点和解题步骤。
                  </p>
                </div>
              </div>
            </div>
          ) : selectedFileName ? (
            /* File only */
            <div className="cw-file-view">
              <div className="cw-file-placeholder">
                <div className="cw-file-icon">📄</div>
                <h2>{selectedFileName}</h2>
                <p>文件内容预览将在这里显示</p>
              </div>
            </div>
          ) : (
            /* AI only */
            <div className="cw-file-view">
              <div className="cw-file-placeholder">
                <div className="cw-file-icon">🧠</div>
                <h2>{selectedAiItem?.title}</h2>
                <p>AI 讲解内容将在这里显示</p>
              </div>
            </div>
          )}

        </div>

        {/* AI Panel on the right (when detached from file explorer) */}
        {aiDetached && (
          <>
            <div className="resize-handle cw-resize" onMouseDown={startAiResize} role="separator" aria-orientation="vertical" tabIndex={-1} />
            <aside className="ai-panel-side" style={{ width: aiPanelWidth }}>
              <div className="ai-panel-header">
                <BrainCircuit size={14} />
                <span>AI 讲解</span>
                <button className="fe-ai-popout" onClick={() => setAiDetached(false)} title="移回左侧">
                  <MoveLeft size={14} />
                </button>
              </div>
              <div className="ai-panel-list">
                {aiExplanations.map((item) => (
                  <button
                    key={item.id}
                    className={`fe-row${selectedAi === item.id ? " selected" : ""}`}
                    style={{ paddingLeft: 8 }}
                    onClick={() => setSelectedAi(item.id)}
                  >
                    <AiTypeIcon type={item.type} />
                    <div className="fe-ai-info">
                      <span className="fe-ai-title">{item.title}</span>
                      <span className="fe-ai-topic">{item.topic}</span>
                    </div>
                  </button>
                ))}
              </div>
            </aside>
          </>
        )}

        {/* Quiz overlay – covers entire workspace */}
        <div
          ref={l2Ref}
          className={`cw-level2-overlay${quizOpen ? " open" : ""}${showFileOverlay ? " peeking" : ""}`}
          onPointerDown={(e) => {
            if (showFileOverlay) {
              if (tabTimerRef.current) clearTimeout(tabTimerRef.current);
              tabTimerRef.current = setTimeout(() => setTabHeld(false), 800);
            } else {
              handleL2PointerDown(e);
            }
          }}
          onPointerMove={showFileOverlay ? undefined : handleL2PointerMove}
          onPointerUp={showFileOverlay ? undefined : handleL2PointerUp}
        >
          {quizOpen && <QuizPanel question={sampleQuestion} />}
        </div>
      </div>
    </AppShell>
  );
}
