import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  BrainCircuit,
  ChevronDown,
  ChevronRight,
  FileText,
  Lightbulb,
  ListChecks,
  MoveLeft,
  PenLine,
  X,
  XCircle,
} from "lucide-react";
import { useParams } from "react-router-dom";
import { AppShell } from "../components/AppShell";
import {
  FileExplorer,
  type ExplorerContextMenuTarget,
  type ExplorerItemKind,
  type SectionKey,
} from "../components/FileExplorer";
import { MistakeReviewPanel } from "../components/MistakeReviewPanel";
import { PhaseSummary, type ProfileItem } from "../components/PhaseSummary";
import { QuizPracticeView } from "../components/QuizPracticeView";
import type { FileNode } from "../data/files";
interface MistakeSourceLink {
  title: string;
  location: string;
  excerpt: string;
}
import {
  fetchSources,
  fetchSourceDetail,
  sourcesToFileNodes,
  fetchSessionPhases,
  type BundleRaw,
  type TreeNode,
  type CoursePhasesResponse,
} from "../services/documentApi";
import { getActivePlan, getCourseSession, buildProfileItems, updateCourseSession, type ActivePlan } from "../services/courseApi";
import {
  fetchExplanations,
  fetchMistakes,
  type ExplanationItem,
  type MistakeItem,
} from "../services/learningApi";

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

const SECTION_ICONS: Record<SectionKey, React.ReactNode> = {
  file: <FileText size={14} />,
  ai: <BrainCircuit size={14} />,
  mistakes: <XCircle size={14} />,
};

type WorkspaceTabKind = ExplorerItemKind;

interface WorkspaceTab {
  id: string;
  kind: WorkspaceTabKind;
  itemId: string;
  title: string;
}

interface FileBundleState {
  bundle: BundleRaw | null;
  title: string;
  loading: boolean;
  error: string;
}

interface ContextMenuState {
  x: number;
  y: number;
  target: ExplorerContextMenuTarget;
}

function AiTypeIcon({ type }: { type: string }) {
  if (type === "解题思路") return <Lightbulb size={ICON_SIZE} className="fe-ai-icon solve" />;
  if (type === "知识点讲解") return <BookOpen size={ICON_SIZE} className="fe-ai-icon explain" />;
  if (type === "错题分析") return <AlertTriangle size={ICON_SIZE} className="fe-ai-icon mistake" />;
  if (type === "公式推导") return <PenLine size={ICON_SIZE} className="fe-ai-icon formula" />;
  return <BrainCircuit size={ICON_SIZE} />;
}

function findFileNode(nodes: FileNode[], id: string): FileNode | null {
  for (const node of nodes) {
    if (node.id === id) return node;
    if (node.children) {
      const child = findFileNode(node.children, id);
      if (child) return child;
    }
  }
  return null;
}

function flattenFileNodes(nodes: FileNode[]): FileNode[] {
  return nodes.flatMap((node) => [node, ...(node.children ? flattenFileNodes(node.children) : [])]);
}

function getTabId(kind: WorkspaceTabKind, itemId: string) {
  return `${kind}:${itemId}`;
}

function getTabTitle(
  kind: WorkspaceTabKind,
  itemId: string,
  files: FileNode[],
  aiItems: ExplanationItem[],
  mistakeItems: MistakeItem[],
) {
  if (kind === "file") return findFileNode(files, itemId)?.name ?? `文件 ${itemId.slice(0, 8)}`;
  if (kind === "ai") return aiItems.find((item) => item.id === itemId)?.title ?? "AI 讲解";
  return mistakeItems.find((item) => item.item_id === itemId)?.title ?? "错题";
}

function getTabIcon(kind: WorkspaceTabKind) {
  if (kind === "file") return <FileText size={14} />;
  if (kind === "ai") return <BrainCircuit size={14} />;
  return <AlertTriangle size={14} />;
}

function DocumentRenderer({ bundle }: { bundle: BundleRaw }) {
  return (
    <div className="document-reader">
      {bundle.pages.map((page) => (
        <div key={page.page_number} className="doc-page">
          <div className="doc-page-number">第 {page.page_number} 页</div>
          {page.elements.map((el, index) => {
            if (el.type === "heading") {
              const level = Math.min(el.heading_level ?? 1, 3);
              const sizes = [22, 18, 16];
              return (
                <div key={index} className="doc-heading" style={{ fontSize: sizes[level - 1], fontWeight: 700 }}>
                  {el.text}
                </div>
              );
            }
            if (el.type === "paragraph") {
              return <p key={index} className="doc-paragraph">{el.text}</p>;
            }
            if (el.type === "list_item") {
              return <div key={index} className="doc-list-item">• {el.text}</div>;
            }
            if (el.type === "image") {
              return <div key={index} className="doc-image-placeholder">[图片]</div>;
            }
            return <p key={index} className="doc-paragraph">{el.text || `[${el.type}]`}</p>;
          })}
        </div>
      ))}
    </div>
  );
}

function DetachedSidePanel({
  sections,
  selectedFileId,
  selectedAiId,
  selectedMistakeId,
  onSelectFile,
  onSelectAi,
  onSelectMistake,
  onContextMenu,
  width,
  aiItems,
  mistakeItems,
  onResizeStart,
  onMoveBack,
  files,
}: {
  sections: SectionKey[];
  selectedFileId: string | null;
  selectedAiId: string | null;
  selectedMistakeId: string | null;
  onSelectFile: (id: string) => void;
  onSelectAi: (id: string) => void;
  onSelectMistake: (id: string) => void;
  onContextMenu: (event: React.MouseEvent, target: ExplorerContextMenuTarget) => void;
  width: number;
  onResizeStart: () => void;
  onMoveBack: (section: SectionKey) => void;
  files: FileNode[];
  aiItems: ExplanationItem[];
  mistakeItems: MistakeItem[];
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [heights, setHeights] = useState<number[] | null>(null);
  const [collapsedSections, setCollapsedSections] = useState<Set<SectionKey>>(new Set());
  const dragIdx = useRef<number | null>(null);
  const dragStartY = useRef(0);
  const dragStartRatios = useRef<number[]>([]);
  const dragAreaHeight = useRef(0);

  const expandedSections = sections.filter((section) => !collapsedSections.has(section));

  const toggleCollapse = useCallback((key: SectionKey) => {
    setCollapsedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  useEffect(() => {
    setHeights(null);
    dragStartRatios.current = [];
    dragAreaHeight.current = 0;
  }, [sections.length, collapsedSections.size]);

  const onMoveHandler = useCallback((event: MouseEvent) => {
    if (dragIdx.current === null || dragAreaHeight.current <= 0) return;
    event.preventDefault();
    const idx = dragIdx.current;
    const base = dragStartRatios.current;
    const dy = (event.clientY - dragStartY.current) / dragAreaHeight.current;
    const minRatio = 80 / dragAreaHeight.current;
    const next = [...base];
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

  useEffect(
    () => () => {
      document.removeEventListener("mousemove", onMoveHandler);
      document.removeEventListener("mouseup", onUpHandler);
    },
    [onMoveHandler, onUpHandler],
  );

  function renderSectionContent(section: SectionKey) {
    switch (section) {
      case "file":
        return flattenFileNodes(files)
          .filter((node) => node.type === "file")
          .map((node) => (
            <button
              key={node.id}
              className={`fe-row${selectedFileId === node.id ? " selected" : ""}`}
              style={{ paddingLeft: 8 }}
              onClick={() => onSelectFile(node.id)}
              onContextMenu={(event) => onContextMenu(event, { kind: "file", id: node.id })}
              type="button"
            >
              <FileText size={ICON_SIZE} />
              <span className="fe-name">{node.name}</span>
            </button>
          ));
      case "ai":
        return aiItems.map((item) => (
          <button
            key={item.id}
            className={`fe-row${selectedAiId === item.id ? " selected" : ""}`}
            style={{ paddingLeft: 8 }}
            onClick={() => onSelectAi(item.id)}
            onContextMenu={(event) => onContextMenu(event, { kind: "ai", id: item.id })}
            type="button"
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
            key={item.item_id}
            className={`fe-row${selectedMistakeId === item.item_id ? " selected" : ""}`}
            style={{ paddingLeft: 8 }}
            onClick={() => onSelectMistake(item.item_id)}
            onContextMenu={(event) => onContextMenu(event, { kind: "mistake", id: item.item_id })}
            type="button"
          >
            <AlertTriangle size={ICON_SIZE} className="fe-ai-icon mistake" />
            <div className="fe-ai-info">
              <span className="fe-ai-title">{item.title}</span>
              <span className="fe-mistake-count">错 {item.wrong_count} 次</span>
            </div>
          </button>
        ));
    }
  }

  if (sections.length === 0) return null;

  return (
    <>
      <div className="resize-handle cw-resize" onMouseDown={onResizeStart} role="separator" aria-orientation="vertical" tabIndex={-1} />
      <aside className="detached-side-panel" ref={containerRef} style={{ width, flexShrink: 0 }}>
        <div className="fe-expanded-area">
          {sections.map((section) => {
            const collapsed = collapsedSections.has(section);
            const expIdx = expandedSections.indexOf(section);
            const style = !collapsed && heights
              ? { flex: `0 0 ${(heights[expIdx] * 100).toFixed(2)}%` }
              : !collapsed
                ? { flex: 1, minHeight: 80 }
                : { flex: "0 0 auto", height: 26 };

            return (
              <React.Fragment key={section}>
                {!collapsed && expIdx > 0 && (
                  <div
                    className="fe-resize-handle"
                    onMouseDown={(event) => {
                      const area = containerRef.current?.querySelector<HTMLElement>(".fe-expanded-area");
                      if (!area) return;
                      const areaH = area.getBoundingClientRect().height;
                      if (areaH <= 0) return;
                      const els = area.querySelectorAll<HTMLElement>(":scope > .fe-section:not(.collapsed)");
                      const pixelHeights = Array.from(els).map((el) => el.getBoundingClientRect().height);
                      if (pixelHeights.length < 2) return;
                      const total = pixelHeights.reduce((a, b) => a + b, 0);
                      const ratios = pixelHeights.map((height) => height / total);
                      dragStartRatios.current = ratios;
                      dragStartY.current = event.clientY;
                      dragAreaHeight.current = areaH;
                      setHeights(ratios);
                      dragIdx.current = expIdx - 1;
                      document.body.style.cursor = "row-resize";
                      document.body.style.userSelect = "none";
                      document.addEventListener("mousemove", onMoveHandler);
                      document.addEventListener("mouseup", onUpHandler);
                    }}
                  />
                )}
                <div className={`fe-section${collapsed ? " collapsed" : ""}`} style={style}>
                  <div className={`fe-section-title${collapsed ? " collapsed-title" : expIdx > 0 ? " sub" : ""}`}>
                    <button
                      className="fe-collapse-toggle"
                      onClick={() => toggleCollapse(section)}
                      title={collapsed ? "展开" : "收起"}
                      type="button"
                    >
                      {collapsed ? <ChevronRight size={12} /> : <ChevronDown size={12} />}
                    </button>
                    {SECTION_ICONS[section]}
                    <span>{SECTION_LABELS[section]}</span>
                    <button className="fe-ai-popout" onClick={() => onMoveBack(section)} title="移回左侧" type="button">
                      <MoveLeft size={14} />
                    </button>
                  </div>
                  {!collapsed && <div className="fe-section-content">{renderSectionContent(section)}</div>}
                </div>
              </React.Fragment>
            );
          })}
        </div>
      </aside>
    </>
  );
}

function TabBar({
  tabs,
  activeTabId,
  onActivate,
  onClose,
}: {
  tabs: WorkspaceTab[];
  activeTabId: string | null;
  onActivate: (id: string) => void;
  onClose: (id: string) => void;
}) {
  return (
    <div className="cw-tab-bar" role="tablist" aria-label="已打开内容">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`cw-tab${activeTabId === tab.id ? " active" : ""}`}
          onClick={() => onActivate(tab.id)}
          role="tab"
          aria-selected={activeTabId === tab.id}
          type="button"
        >
          <span className="cw-tab-icon">{getTabIcon(tab.kind)}</span>
          <span className="cw-tab-title">{tab.title}</span>
          <span
            className="cw-tab-close"
            onClick={(event) => {
              event.stopPropagation();
              onClose(tab.id);
            }}
            role="button"
            aria-label={`关闭 ${tab.title}`}
            tabIndex={-1}
          >
            <X size={13} />
          </span>
        </button>
      ))}
    </div>
  );
}

function ContentBody({
  tab,
  fileState,
  files,
  onOpenSourceFile,
  onStartQuiz,
  aiItems,
  mistakeItems,
}: {
  tab: WorkspaceTab;
  fileState?: FileBundleState;
  files: FileNode[];
  onOpenSourceFile: (id: string, newTab?: boolean) => void;
  onStartQuiz: (sourceId: string | null) => void;
  aiItems: ExplanationItem[];
  mistakeItems: MistakeItem[];
}) {
  const selectedAi = tab.kind === "ai" ? aiItems.find((item) => item.id === tab.itemId) : null;
  const selectedMistake = tab.kind === "mistake" ? mistakeItems.find((item) => item.item_id === tab.itemId) ?? null : null;

  function canOpenSource(link: MistakeSourceLink) {
    // source_links 来自后端，可能无对应本地 fileId
    return false;
  }

  function handleOpenSource(link: MistakeSourceLink) {
    // 预留：后续通过 evidence_id 定位原文
  }

  if (tab.kind === "file") {
    return (
      <>
        <div className="cw-content-toolbar">
          <button className="cw-panel-quiz" onClick={() => onStartQuiz(tab.itemId)} type="button">
            <ListChecks size={14} />
            <span>刷题</span>
          </button>
        </div>
        {fileState?.loading && <p className="cw-preview-text">加载中...</p>}
        {!fileState?.loading && fileState?.bundle && <DocumentRenderer bundle={fileState.bundle} />}
        {!fileState?.loading && fileState?.error && <p className="cw-preview-text">{fileState.error}</p>}
        {!fileState?.loading && !fileState?.bundle && !fileState?.error && (
          <p className="cw-preview-text">无法加载文档内容。</p>
        )}
      </>
    );
  }

  if (tab.kind === "mistake") {
    if (!selectedMistake) return <p className="cw-preview-text">这道错题暂时不可用。</p>;
    return (
      <MistakeReviewPanel
        canOpenSource={canOpenSource}
        mistake={selectedMistake}
        onOpenSource={handleOpenSource}
      />
    );
  }

  return (
    <div className="cw-ai-preview">
      <div className="cw-ai-preview-icon">
        <BrainCircuit size={22} />
      </div>
      <div>
        <p className="cw-ai-preview-kicker">{selectedAi?.type ?? "AI 讲解"}</p>
        <h2>{selectedAi?.title ?? tab.title}</h2>
        <p>{selectedAi?.topic ? `关联知识点：${selectedAi.topic}` : "AI 讲解内容将在这里显示。"}</p>
      </div>
    </div>
  );
}

function ContextMenu({
  state,
  onOpen,
  onOpenNewTab,
  onStartQuiz,
}: {
  state: ContextMenuState;
  onOpen: (target: ExplorerContextMenuTarget) => void;
  onOpenNewTab: (target: ExplorerContextMenuTarget) => void;
  onStartQuiz: (target: ExplorerContextMenuTarget) => void;
}) {
  return (
    <div
      className="cw-context-menu"
      style={{ left: state.x, top: state.y }}
      onPointerDown={(event) => event.stopPropagation()}
      role="menu"
    >
      <button onClick={() => onOpen(state.target)} role="menuitem" type="button">打开</button>
      <button onClick={() => onOpenNewTab(state.target)} role="menuitem" type="button">在新标签页中打开</button>
      <button onClick={() => onStartQuiz(state.target)} role="menuitem" type="button">刷题</button>
    </div>
  );
}

export function CourseWorkspacePage() {
  const [quizPracticeOpen, setQuizPracticeOpen] = useState(false);
  const [quizDefaultSourceId, setQuizDefaultSourceId] = useState<string | null>(null);
  const [phaseSummaryOpen, setPhaseSummaryOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [selectedAi, setSelectedAi] = useState<string | null>(null);
  const [selectedMistake, setSelectedMistake] = useState<string | null>(null);
  const [explorerWidth, setExplorerWidth] = useState(220);
  const [detachedSections, setDetachedSections] = useState<Set<SectionKey>>(new Set());
  const [sidePanelWidth, setSidePanelWidth] = useState(240);
  const [openTabs, setOpenTabs] = useState<WorkspaceTab[]>([]);
  const [activeTabId, setActiveTabId] = useState<string | null>(null);
  const [fileCache, setFileCache] = useState<Record<string, FileBundleState>>({});
  const [contextMenu, setContextMenu] = useState<ContextMenuState | null>(null);
  const [fileNodes, setFileNodes] = useState<FileNode[]>([]);
  const [activePlan, setActivePlan] = useState<ActivePlan | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [aiItems, setAiItems] = useState<ExplanationItem[]>([]);
  const [mistakeItems, setMistakeItems] = useState<MistakeItem[]>([]);
  const [phases, setPhases] = useState<CoursePhasesResponse | null>(null);
  const [profileItems, setProfileItems] = useState<ProfileItem[]>([]);

  const { courseId } = useParams<{ courseId: string }>();
  const activeTab = useMemo(
    () => openTabs.find((tab) => tab.id === activeTabId) ?? null,
    [activeTabId, openTabs],
  );



  /* ── Fetch plan + update last_studied_at on mount ── */
  useEffect(() => {
    if (!courseId) return;
    setPlanLoading(true);
    getActivePlan(courseId)
      .then((plan) => setActivePlan(plan))
      .catch(() => setActivePlan(null))
      .finally(() => setPlanLoading(false));
    getCourseSession(courseId)
      .then((session) => setProfileItems(buildProfileItems(session)))
      .catch(() => setProfileItems([]));
    // 更新最近学习时间
    updateCourseSession(courseId, {
      last_studied_at: new Date().toISOString(),
    }).catch(() => {});

    // 加载讲解、错题、阶段数据
    Promise.all([
      fetchExplanations(courseId).then((d) => setAiItems(d.items)).catch(() => {}),
      fetchMistakes(courseId).then((d) => setMistakeItems(d.items)).catch(() => {}),
      fetchSessionPhases(courseId).then(setPhases).catch(() => {}),
    ]);
  }, [courseId]);

  /* ── Fetch sources on mount (filtered by course) ── */
  useEffect(() => {
    fetchSources(courseId)
      .then((items) => setFileNodes(sourcesToFileNodes(items)))
      .catch(() => setFileNodes([]));
  }, [courseId]);

  useEffect(() => {
    if (!activeTab) {
      setSelectedFile(null);
      setSelectedAi(null);
      setSelectedMistake(null);
      return;
    }
    setSelectedFile(activeTab.kind === "file" ? activeTab.itemId : null);
    setSelectedAi(activeTab.kind === "ai" ? activeTab.itemId : null);
    setSelectedMistake(activeTab.kind === "mistake" ? activeTab.itemId : null);
  }, [activeTab]);

  useEffect(() => {
    if (!activeTab || activeTab.kind !== "file") return;
    const fileId = activeTab.itemId;
    const cached = fileCache[fileId];
    if (cached?.bundle || cached?.loading || cached?.error) return;

    setFileCache((prev) => ({
      ...prev,
      [fileId]: { bundle: null, title: activeTab.title, loading: true, error: "" },
    }));
    fetchSourceDetail(fileId)
      .then((data) => {
        setFileCache((prev) => ({
          ...prev,
          [fileId]: {
            bundle: data.bundle,
            title: data.source.displayTitle || data.version.originalFilename || activeTab.title,
            loading: false,
            error: data.bundle ? "" : "无法加载文档内容。",
          },
        }));
      })
      .catch((error) => {
        setFileCache((prev) => ({
          ...prev,
          [fileId]: {
            bundle: null,
            title: activeTab.title,
            loading: false,
            error: error instanceof Error ? error.message : "加载文档失败。",
          },
        }));
      });
  }, [activeTab, fileCache]);

  useEffect(() => {
    if (!contextMenu) return;
    function handlePointerDown() {
      setContextMenu(null);
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setContextMenu(null);
    }
    document.addEventListener("pointerdown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [contextMenu]);

  const openItem = useCallback((kind: WorkspaceTabKind, itemId: string, mode: "replace" | "new") => {
    const nextTab = {
      id: getTabId(kind, itemId),
      kind,
      itemId,
      title: getTabTitle(kind, itemId, fileNodes, aiItems, mistakeItems),
    };
    setOpenTabs((prev) => {
      const existing = prev.find((tab) => tab.id === nextTab.id);
      if (existing) {
        setActiveTabId(existing.id);
        return prev;
      }
      if (mode === "new" || prev.length === 0 || !activeTabId) {
        setActiveTabId(nextTab.id);
        return [...prev, nextTab];
      }
      setActiveTabId(nextTab.id);
      return prev.map((tab) => (tab.id === activeTabId ? nextTab : tab));
    });
  }, [activeTabId, fileNodes]);

  const handleSelectFile = useCallback((id: string) => openItem("file", id, "replace"), [openItem]);
  const handleSelectAi = useCallback((id: string) => openItem("ai", id, "replace"), [openItem]);
  const handleSelectMistake = useCallback((id: string) => openItem("mistake", id, "replace"), [openItem]);

  function closeTab(tabId: string) {
    setOpenTabs((prev) => {
      const index = prev.findIndex((tab) => tab.id === tabId);
      const next = prev.filter((tab) => tab.id !== tabId);
      if (activeTabId === tabId) {
        const fallback = next[Math.min(index, next.length - 1)] ?? null;
        setActiveTabId(fallback?.id ?? null);
      }
      return next;
    });
  }

  function handleExplorerContextMenu(event: React.MouseEvent, target: ExplorerContextMenuTarget) {
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({ x: event.clientX, y: event.clientY, target });
  }

  function handleContextOpen(target: ExplorerContextMenuTarget) {
    setContextMenu(null);
    openItem(target.kind, target.id, "replace");
  }

  function handleContextOpenNewTab(target: ExplorerContextMenuTarget) {
    setContextMenu(null);
    openItem(target.kind, target.id, "new");
  }

  function startQuiz(sourceId: string | null) {
    setQuizDefaultSourceId(sourceId);
    setQuizPracticeOpen(true);
  }

  function handleContextStartQuiz(target: ExplorerContextMenuTarget) {
    setContextMenu(null);
    startQuiz(target.kind === "file" ? target.id : null);
  }

  const toggleDetach = useCallback((section: SectionKey) => {
    setDetachedSections((prev) => {
      const next = new Set(prev);
      if (next.has(section)) next.delete(section);
      else next.add(section);
      return next;
    });
  }, []);

  const handleBottomClick = useCallback(() => setPhaseSummaryOpen(true), []);


  const explorerResizeRef = useRef(false);
  const onExplorerMove = useCallback((event: MouseEvent) => {
    if (!explorerResizeRef.current) return;
    setExplorerWidth((width) => Math.min(MAX_EXPLORER, Math.max(MIN_EXPLORER, width + event.movementX)));
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

  const sideResizeRef = useRef(false);
  const onSideMove = useCallback((event: MouseEvent) => {
    if (!sideResizeRef.current) return;
    setSidePanelWidth((width) => Math.min(MAX_SIDE_PANEL, Math.max(MIN_SIDE_PANEL, width - event.movementX)));
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

  useEffect(
    () => () => {
      document.removeEventListener("mousemove", onExplorerMove);
      document.removeEventListener("mouseup", onExplorerUp);
      document.removeEventListener("mousemove", onSideMove);
      document.removeEventListener("mouseup", onSideUp);
    },
    [onExplorerMove, onExplorerUp, onSideMove, onSideUp],
  );

  const detachedList = (["file", "ai", "mistakes"] as SectionKey[]).filter((section) => detachedSections.has(section));
  const hasLeftSections = detachedSections.size < 3;

  return (
    <AppShell
      aiChatContext={{
        files: fileNodes,
        aiItems,
        mistakeItems,
        selectedFileId: selectedFile,
        selectedAiId: selectedAi,
        selectedMistakeId: selectedMistake,
      }}
    >
      {quizPracticeOpen ? (
        <QuizPracticeView
          files={fileNodes}
          defaultSourceId={quizDefaultSourceId}
          onBack={() => setQuizPracticeOpen(false)}
          onOpenSource={(id) => {
            setQuizPracticeOpen(false);
            openItem("file", id, "new");
          }}
        />
      ) : (
        <div className="course-workspace-new">
          {hasLeftSections && (
            <>
              <div style={{ width: explorerWidth, flexShrink: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
                <FileExplorer
                  files={fileNodes}
                  aiItems={aiItems}
                  mistakeItems={mistakeItems}
                  selectedFileId={selectedFile}
                  selectedAiId={selectedAi}
                  selectedMistakeId={selectedMistake}
                  onSelectFile={handleSelectFile}
                  onSelectAi={handleSelectAi}
                  onSelectMistake={handleSelectMistake}
                  onContextMenu={handleExplorerContextMenu}
                  detachedSections={detachedSections}
                  onToggleDetach={toggleDetach}
                />
              </div>
              <div className="resize-handle cw-resize" onMouseDown={startExplorerResize} role="separator" aria-orientation="vertical" tabIndex={-1} />
            </>
          )}

          <div className="cw-content">
            {openTabs.length === 0 ? (
              <div className="cw-file-view">
                <div className="cw-file-placeholder">
                  <div className="cw-file-icon"><FileText size={48} /></div>
                  <h2>文件浏览</h2>
                  <p>从左侧选择课程文件、AI 讲解或错题。</p>
                </div>
              </div>
            ) : (
              <div className="cw-tab-workspace">
                <TabBar
                  tabs={openTabs}
                  activeTabId={activeTabId}
                  onActivate={setActiveTabId}
                  onClose={closeTab}
                />
                <main className="cw-tab-content">
                  {activeTab && (
                    <ContentBody
                      tab={activeTab}
                      fileState={activeTab.kind === "file" ? fileCache[activeTab.itemId] : undefined}
                      files={fileNodes}
                      onOpenSourceFile={(id, newTab = false) => openItem("file", id, newTab ? "new" : "replace")}
                      onStartQuiz={startQuiz}
                      aiItems={aiItems}
                      mistakeItems={mistakeItems}
                    />
                  )}
                </main>
              </div>
            )}

            {!phaseSummaryOpen && (
              <div className="cw-bottom-trigger" onClick={handleBottomClick}>
                <div className="cw-bottom-trigger-bar" />
                <span className="cw-bottom-hint">点击查看学习方案</span>
              </div>
            )}
          </div>

          <DetachedSidePanel
            sections={detachedList}
            selectedFileId={selectedFile}
            selectedAiId={selectedAi}
            selectedMistakeId={selectedMistake}
            onSelectFile={handleSelectFile}
            onSelectAi={handleSelectAi}
            onSelectMistake={handleSelectMistake}
            onContextMenu={handleExplorerContextMenu}
            width={sidePanelWidth}
            onResizeStart={startSideResize}
            onMoveBack={toggleDetach}
            files={fileNodes}
            aiItems={aiItems}
            mistakeItems={mistakeItems}
          />

          {/* Phase summary overlay */}
          <div
            className={`phase-summary-overlay${phaseSummaryOpen ? " open" : ""}`}
          >
            {phaseSummaryOpen && (
              <PhaseSummary
                onClose={() => setPhaseSummaryOpen(false)}
                plan={activePlan}
                profileItems={profileItems}
                loading={planLoading}
                courseId={courseId ?? ""}
              />
            )}
          </div>

          {contextMenu && (
            <ContextMenu
              state={contextMenu}
              onOpen={handleContextOpen}
              onOpenNewTab={handleContextOpenNewTab}
              onStartQuiz={handleContextStartQuiz}
            />
          )}
        </div>

      )}
    </AppShell>
  );
}
