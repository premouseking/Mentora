import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  BrainCircuit,
  BookOpen,
  ChevronDown,
  ChevronRight,
  Lightbulb,
  MoveLeft,
  PenLine,
  AlertTriangle,
  X,
  XCircle,
} from "lucide-react";
import { AppShell } from "../components/AppShell";
import { FileExplorer } from "../components/FileExplorer";
import type { SectionKey } from "../components/FileExplorer";
import { PhaseSummary } from "../components/PhaseSummary";
import { QuizPanel } from "../components/QuizPanel";
import { courseFiles } from "../data/files";
import { aiExplanations } from "../data/aiExplanations";
import { mistakeItems } from "../data/mistakes";
import { sampleQuestion } from "../data/quiz";

const MIN_EXPLORER = 170;
const MAX_EXPLORER = 360;
const MIN_SIDE_PANEL = 160;
const MAX_SIDE_PANEL = 400;

const ICON_SIZE = 14;

const SECTION_LABELS: Record<SectionKey, string> = {
  file: "课程文件",
  ai: "AI 讲解",
  mistakes: "错题集",
};

const SECTION_ICONS: Record<SectionKey, string> = {
  file: "📄",
  ai: "🧠",
  mistakes: "❌",
};

function AiTypeIcon({ type }: { type: string }) {
  if (type === "解题思路") return <Lightbulb size={ICON_SIZE} className="fe-ai-icon solve" />;
  if (type === "知识点讲解") return <BookOpen size={ICON_SIZE} className="fe-ai-icon explain" />;
  if (type === "错题分析") return <AlertTriangle size={ICON_SIZE} className="fe-ai-icon mistake" />;
  if (type === "公式推导") return <PenLine size={ICON_SIZE} className="fe-ai-icon formula" />;
  return <BrainCircuit size={ICON_SIZE} />;
}

/* ── Right-side detached panel (single column, sections split vertically) ── */
function DetachedSidePanel({
  sections,
  selectedFileId,
  selectedAiId,
  selectedMistakeId,
  onSelectFile,
  onSelectAi,
  onSelectMistake,
  width,
  onResizeStart,
  onMoveBack,
  onOpenPanel,
}: {
  sections: SectionKey[];
  selectedFileId: string | null;
  selectedAiId: string | null;
  selectedMistakeId: string | null;
  onSelectFile: (id: string) => void;
  onSelectAi: (id: string) => void;
  onSelectMistake: (id: string) => void;
  width: number;
  onResizeStart: () => void;
  onMoveBack: (section: SectionKey) => void;
  onOpenPanel: (section: SectionKey) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  // null = flex mode; number[] = fraction per section (always sums to 1)
  const [heights, setHeights] = useState<number[] | null>(null);
  const dragIdx = useRef<number | null>(null);
  const dragStartY = useRef(0);
  const dragStartRatios = useRef<number[]>([]);
  const dragAreaHeight = useRef(0);

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

  // Sort: expanded first (original order), collapsed last (original order)
  const sortedSections = sections
    .map((s, i) => ({ section: s, originalIndex: i }))
    .sort((a, b) => {
      const aCollapsed = collapsedSections.has(a.section);
      const bCollapsed = collapsedSections.has(b.section);
      if (aCollapsed === bCollapsed) return a.originalIndex - b.originalIndex;
      return aCollapsed ? 1 : -1;
    })
    .map(({ section }) => section);

  const expandedSections = sortedSections.filter((s) => !collapsedSections.has(s));
  const collapsedList = sortedSections.filter((s) => collapsedSections.has(s));

  // Reset heights when sections or collapse change
  useEffect(() => {
    setHeights(null);
    dragStartRatios.current = [];
    dragAreaHeight.current = 0;
  }, [sections.length, collapsedSections.size]);

  /* ── Resize between expanded sections ── */
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

  /* ── Section icon helper ── */
  function sectionIcon(section: SectionKey) {
    if (section === "ai") return <BrainCircuit size={14} />;
    if (section === "mistakes") return <XCircle size={14} />;
    return <span>{SECTION_ICONS[section]}</span>;
  }

  const renderSectionContent = (section: SectionKey) => {
    switch (section) {
      case "file":
        return courseFiles.map((n) => (
          <button
            key={n.id}
            className={`fe-row${selectedFileId === n.id ? " selected" : ""}`}
            style={{ paddingLeft: 8 }}
            onClick={() => { onSelectFile(n.id); onOpenPanel("file"); }}
          >
            <span className="fe-name">{n.name}</span>
          </button>
        ));
      case "ai":
        return aiExplanations.map((item) => (
          <button
            key={item.id}
            className={`fe-row${selectedAiId === item.id ? " selected" : ""}`}
            style={{ paddingLeft: 8 }}
            onClick={() => { onSelectAi(item.id); onOpenPanel("ai"); }}
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
            onClick={() => { onSelectMistake(item.id); onOpenPanel("mistakes"); }}
          >
            <AlertTriangle size={ICON_SIZE} className="fe-ai-icon mistake" />
            <div className="fe-ai-info">
              <span className="fe-ai-title">{item.title}</span>
              <span className="fe-mistake-count">错 {item.wrongCount} 次</span>
            </div>
          </button>
        ));
    }
  };

  if (sections.length === 0) return null;

  return (
    <>
      <div className="resize-handle cw-resize" onMouseDown={onResizeStart} role="separator" aria-orientation="vertical" tabIndex={-1} />
      <aside className="detached-side-panel" ref={containerRef} style={{ width, flexShrink: 0 }}>
        {/* Expanded section area — resize handles + sections are direct children */}
        {expandedSections.length > 0 && (
          <div className="fe-expanded-area">
            {expandedSections.map((section, i) => {
              const style = heights
                ? { flex: `0 0 ${(heights[i] * 100).toFixed(2)}%` }
                : { flex: 1, minHeight: 80 };
              return (
              <React.Fragment key={section}>
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
                    <button className="fe-collapse-toggle" onClick={() => toggleCollapse(section)} title="收起">
                      <ChevronDown size={12} />
                    </button>
                    {sectionIcon(section)}
                    <span>{SECTION_LABELS[section]}</span>
                    <button className="fe-ai-popout" onClick={() => onMoveBack(section)} title="移回左侧">
                      <MoveLeft size={14} />
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

        {/* Collapsed section area — pinned to bottom */}
        {collapsedList.length > 0 && (
          <div className="fe-collapsed-area">
            {collapsedList.map((section) => (
              <div key={section} className="fe-section collapsed" style={{ flex: "0 0 auto", height: 26 }}>
                  <div className="fe-section-title collapsed-title">
                    <button
                      className="fe-collapse-toggle"
                      onClick={() => toggleCollapse(section)}
                      title="展开"
                    >
                      <ChevronRight size={12} />
                    </button>
                    {sectionIcon(section)}
                    <span>{SECTION_LABELS[section]}</span>
                    <button className="fe-ai-popout" onClick={() => onMoveBack(section)} title="移回左侧">
                      <MoveLeft size={14} />
                    </button>
                  </div>
                </div>
            ))}
          </div>
        )}
      </aside>
    </>
  );
}

/* ── Content preview panel ── */
function ContentPanel({
  section,
  selectedFileId,
  selectedAiId,
  selectedMistakeId,
  width,
  onClose,
  onResizeStart,
}: {
  section: SectionKey;
  selectedFileId: string | null;
  selectedAiId: string | null;
  selectedMistakeId: string | null;
  width?: number;
  onClose: () => void;
  onResizeStart?: () => void;
}) {
  const icon = SECTION_ICONS[section];
  const label = SECTION_LABELS[section];

  const getTitle = () => {
    switch (section) {
      case "file":
        if (!selectedFileId) return label;
        for (const n of courseFiles)
          for (const fn of [n, ...(n.children ?? [])])
            if (fn.id === selectedFileId && fn.type === "file") return fn.name;
        return selectedFileId;
      case "ai":
        return selectedAiId ? aiExplanations.find((a) => a.id === selectedAiId)?.title ?? label : label;
      case "mistakes":
        return selectedMistakeId ? mistakeItems.find((m) => m.id === selectedMistakeId)?.title ?? label : label;
    }
  };

  return (
    <div className="cw-split-pane" style={width !== undefined ? { width, flex: "0 0 auto" } : { flex: 1 }}>
      <div className="cw-split-title">
        <span className="cw-panel-label">{icon} {getTitle()}</span>
        <button className="cw-panel-close" onClick={onClose} title="关闭">
          <X size={14} />
        </button>
      </div>
      <div className="cw-split-content">
        <p className="cw-preview-text">
          「{getTitle()}」的内容预览将在这里显示。
        </p>
      </div>
      {onResizeStart && (
        <div className="cw-split-handle" onMouseDown={onResizeStart} />
      )}
    </div>
  );
}

export function CourseWorkspacePage() {
  const [quizOpen, setQuizOpen] = useState(false);
  const [phaseSummaryOpen, setPhaseSummaryOpen] = useState(false);
  const [tabHeld, setTabHeld] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [selectedAi, setSelectedAi] = useState<string | null>(null);
  const [selectedMistake, setSelectedMistake] = useState<string | null>(null);
  const [explorerWidth, setExplorerWidth] = useState(220);
  const [detachedSections, setDetachedSections] = useState<Set<SectionKey>>(new Set());
  const [sidePanelWidth, setSidePanelWidth] = useState(240);
  const [openPanels, setOpenPanels] = useState<SectionKey[]>([]);
  const [panelWidths, setPanelWidths] = useState<number[]>([]);

  const l2Ref = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  /* ── Open / close panel ── */
  const openPanel = useCallback((section: SectionKey) => {
    setOpenPanels((prev) => {
      if (prev.includes(section)) return prev;
      if (prev.length >= 3) return [...prev.slice(1), section];
      return [...prev, section];
    });
  }, []);

  const closePanel = useCallback((section: SectionKey) => {
    setOpenPanels((prev) => prev.filter((s) => s !== section));
    if (section === "file") setSelectedFile(null);
    if (section === "ai") setSelectedAi(null);
    if (section === "mistakes") setSelectedMistake(null);
  }, []);

  /* ── Toggle detach ── */
  const toggleDetach = useCallback((section: SectionKey) => {
    setDetachedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  }, []);

  /* ── Init panel widths when openPanels change ── */
  useEffect(() => {
    if (openPanels.length > 1 && containerRef.current) {
      const w = containerRef.current.getBoundingClientRect().width;
      const eq = Math.floor(w / openPanels.length);
      setPanelWidths(openPanels.map((_, i) => (i < openPanels.length - 1 ? eq : w - eq * (openPanels.length - 1))));
    } else {
      setPanelWidths([]);
    }
  }, [openPanels.length]);

  /* ── Wrapper: select + open panel ── */
  const handleSelectFile = useCallback((id: string) => {
    setSelectedFile(id);
    openPanel("file");
  }, [openPanel]);

  const handleSelectAi = useCallback((id: string) => {
    setSelectedAi(id);
    openPanel("ai");
  }, [openPanel]);

  const handleSelectMistake = useCallback((id: string) => {
    setSelectedMistake(id);
    openPanel("mistakes");
  }, [openPanel]);

  /* ── Top trigger → open quiz ── */
  const handleTopClick = useCallback(() => setQuizOpen(true), []);

  /* ── Bottom trigger → open phase summary ── */
  const handleBottomClick = useCallback(() => setPhaseSummaryOpen(true), []);

  /* ── Swipe up → close quiz ── */
  const swipeStart = useRef<{ y: number; moved: boolean; active: boolean }>({ y: 0, moved: false, active: false });
  const handleL2PointerDown = useCallback((e: React.PointerEvent) => {
    swipeStart.current = { y: e.clientY, moved: false, active: true };
    e.currentTarget.setPointerCapture(e.pointerId);
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

  /* ── Swipe down → close phase summary ── */
  const psRef = useRef<HTMLDivElement>(null);
  const psSwipeStart = useRef<{ y: number; moved: boolean; active: boolean }>({ y: 0, moved: false, active: false });
  const handlePSPointerDown = useCallback((e: React.PointerEvent) => {
    psSwipeStart.current = { y: e.clientY, moved: false, active: true };
    e.currentTarget.setPointerCapture(e.pointerId);
  }, []);
  const handlePSPointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (!phaseSummaryOpen || !psSwipeStart.current.active) return;
      const dy = e.clientY - psSwipeStart.current.y;
      if (dy > 20) psSwipeStart.current.moved = true;
      if (psSwipeStart.current.moved && psRef.current) {
        psRef.current.style.transform = `translateY(${Math.max(0, dy)}px)`;
        psRef.current.style.opacity = String(Math.max(0.3, 1 - dy / 300));
      }
    },
    [phaseSummaryOpen],
  );
  const handlePSPointerUp = useCallback(
    (e: React.PointerEvent) => {
      if (!phaseSummaryOpen || !psSwipeStart.current.active) return;
      psSwipeStart.current.active = false;
      const dy = e.clientY - psSwipeStart.current.y;
      if (psRef.current) {
        psRef.current.style.transform = "";
        psRef.current.style.opacity = "";
      }
      if (psSwipeStart.current.moved && dy > 60) setPhaseSummaryOpen(false);
    },
    [phaseSummaryOpen],
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

  /* ── Resize right side panel column ── */
  const sideResizeRef = useRef(false);
  const sideMoveRef = useRef<((e: MouseEvent) => void) | null>(null);
  sideMoveRef.current = (e: MouseEvent) => {
    setSidePanelWidth((w) => Math.min(MAX_SIDE_PANEL, Math.max(MIN_SIDE_PANEL, w - e.movementX)));
  };
  const onSideMove = useCallback((e: MouseEvent) => {
    if (!sideResizeRef.current) return;
    sideMoveRef.current?.(e);
  }, []);
  const onSideUp = useCallback(() => {
    sideResizeRef.current = false;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", onSideMove);
    document.removeEventListener("mouseup", onSideUp);
  }, [onSideMove]);
  const startSideResize = useCallback(() => {
    sideResizeRef.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onSideMove);
    document.addEventListener("mouseup", onSideUp);
  }, [onSideMove, onSideUp]);
  useEffect(() => () => {
    document.removeEventListener("mousemove", onSideMove);
    document.removeEventListener("mouseup", onSideUp);
  }, [onSideMove, onSideUp]);

  /* ── Resize content panels ── */
  const splitResizeIdx = useRef<number | null>(null);
  const splitMoveRef = useRef<((e: MouseEvent) => void) | null>(null);
  splitMoveRef.current = (e: MouseEvent) => {
    if (splitResizeIdx.current === null || !containerRef.current) return;
    const idx = splitResizeIdx.current;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const totalW = rect.width - 6 * (openPanels.length - 1);
    const newLeft = Math.max(120, Math.min(totalW - (openPanels.length - idx - 1) * 120, x));
    setPanelWidths((prev) => {
      const next = [...prev];
      let acc = 0;
      for (let i = 0; i < openPanels.length; i++) {
        if (i === idx) {
          next[i] = Math.max(120, newLeft - acc);
        }
        acc += next[i] + 6;
      }
      const remaining = totalW - next.reduce((a, b) => a + b, 0);
      if (remaining > 0) next[openPanels.length - 1] += remaining;
      return next;
    });
  };
  const onSplitMove = useCallback((e: MouseEvent) => splitMoveRef.current?.(e), []);
  const onSplitUp = useCallback(() => {
    splitResizeIdx.current = null;
    document.body.style.cursor = "";
    document.body.style.userSelect = "";
    document.removeEventListener("mousemove", onSplitMove);
    document.removeEventListener("mouseup", onSplitUp);
  }, [onSplitMove]);
  const startSplitResize = useCallback((idx: number) => {
    splitResizeIdx.current = idx;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    document.addEventListener("mousemove", onSplitMove);
    document.addEventListener("mouseup", onSplitUp);
  }, [onSplitMove, onSplitUp]);
  useEffect(() => () => {
    document.removeEventListener("mousemove", onSplitMove);
    document.removeEventListener("mouseup", onSplitUp);
  }, [onSplitMove, onSplitUp]);

  /* ── Detached sections on right side ── */
  const detachedList = (["file", "ai", "mistakes"] as SectionKey[]).filter((s) => detachedSections.has(s));
  const hasLeftSections = detachedSections.size < 3;

  /* ── Render ── */
  const showFileOverlay = quizOpen && tabHeld;

  return (
    <AppShell>
      <div className="course-workspace-new">
        {/* File Explorer (left sidebar - shows non-detached sections) */}
        {hasLeftSections && (
          <>
            <div style={{ width: explorerWidth, flexShrink: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
              <FileExplorer
                files={courseFiles}
                aiItems={aiExplanations}
                mistakeItems={mistakeItems}
                selectedFileId={selectedFile}
                selectedAiId={selectedAi}
                selectedMistakeId={selectedMistake}
                onSelectFile={handleSelectFile}
                onSelectAi={handleSelectAi}
                onSelectMistake={handleSelectMistake}
                detachedSections={detachedSections}
                onToggleDetach={toggleDetach}
              />
            </div>
            <div className="resize-handle cw-resize" onMouseDown={startExplorerResize} role="separator" aria-orientation="vertical" tabIndex={-1} />
          </>
        )}

        {/* Content Area */}
        <div className="cw-content" ref={containerRef}>
          {!quizOpen && !phaseSummaryOpen && (
            <div className="cw-top-trigger" onClick={handleTopClick}>
              <div className="cw-top-trigger-bar" />
              <span className="cw-top-hint">点击进入刷题模式</span>
            </div>
          )}

          {openPanels.length === 0 ? (
            /* Empty state */
            <div className="cw-file-view">
              <div className="cw-file-placeholder">
                <div className="cw-file-icon">{SECTION_ICONS.file}</div>
                <h2>文件浏览</h2>
                <p>从左侧选择一个文件或 AI 讲解</p>
              </div>
            </div>
          ) : openPanels.length === 1 ? (
            /* Single panel */
            <ContentPanel
              section={openPanels[0]}
              selectedFileId={selectedFile}
              selectedAiId={selectedAi}
              selectedMistakeId={selectedMistake}
              onClose={() => closePanel(openPanels[0])}
            />
          ) : (
            /* Multi-panel split */
            <div className="cw-split">
              {openPanels.map((section, i) => (
                <ContentPanel
                  key={section}
                  section={section}
                  selectedFileId={selectedFile}
                  selectedAiId={selectedAi}
                  selectedMistakeId={selectedMistake}
                  width={panelWidths[i]}
                  onClose={() => closePanel(section)}
                  onResizeStart={i < openPanels.length - 1 ? () => startSplitResize(i) : undefined}
                />
              ))}
            </div>
          )}

          {/* Bottom trigger → open phase summary — inside cw-content only */}
          {!quizOpen && !phaseSummaryOpen && (
            <div className="cw-bottom-trigger" onClick={handleBottomClick}>
              <div className="cw-bottom-trigger-bar" />
            </div>
          )}
        </div>

        {/* Detached sections on the right side — single column, sections split vertically */}
        <DetachedSidePanel
          sections={detachedList}
          selectedFileId={selectedFile}
          selectedAiId={selectedAi}
          selectedMistakeId={selectedMistake}
          onSelectFile={handleSelectFile}
          onSelectAi={handleSelectAi}
          onSelectMistake={handleSelectMistake}
          width={sidePanelWidth}
          onResizeStart={startSideResize}
          onMoveBack={toggleDetach}
          onOpenPanel={openPanel}
        />

        {/* Quiz overlay */}
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
          {quizOpen && <QuizPanel question={sampleQuestion} onClose={() => setQuizOpen(false)} />}
        </div>

        {/* Phase summary overlay */}
        <div
          ref={psRef}
          className={`phase-summary-overlay${phaseSummaryOpen ? " open" : ""}`}
          onPointerDown={handlePSPointerDown}
          onPointerMove={handlePSPointerMove}
          onPointerUp={handlePSPointerUp}
        >
          {phaseSummaryOpen && <PhaseSummary onClose={() => setPhaseSummaryOpen(false)} />}
        </div>
      </div>
    </AppShell>
  );
}
