import { useMemo, useState, useEffect, useRef, useCallback, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  Eye,
  FileText,
  FileWarning,
  FolderClosed,
  FolderOpen,
  Folders,
  Image,
  Link2,
  Loader,
  MoreHorizontal,
  Plus,
  RefreshCw,
  Search,
  Tag,
  Trash2,
  Upload,
  X,
} from "lucide-react";

import { AppShell } from "../components/AppShell";
import {
  deleteSource, reparseSource,
  createFolder, deleteFolder,
  moveSource,
  type FolderItem,
} from "../services/documentApi";
import { buildLibraryReaderPath } from "../services/resourceCompat";
import { useLibraryData } from "../hooks/useLibraryData";
import { SourceUploadModal } from "../components/upload/SourceUploadModal";
import { VirtualLibraryRows } from "../components/VirtualLibraryRows";
import {
  parseStateLabels,
  roleLabels,
  typeLabels,
  type LibraryItem,
  type LibraryItemType,
  type ParseState,
} from "../data/library";

/* ── constants ─────────────────────────────────────── */

const ALL_TYPES: (LibraryItemType | "all")[] = [
  "all", "pdf", "docx", "pptx", "image", "video", "audio", "link",
];

const typeIcons: Record<LibraryItemType, typeof FileText> = {
  pdf: FileText, docx: FileText, pptx: FileText, image: Image, video: FileText, audio: FileText, link: Link2,
};

/* ── icon helpers ──────────────────────────────────── */

function TypeIcon({ type }: { type: LibraryItemType }) {
  const Icon = typeIcons[type];
  return <Icon size={16} />;
}

function ParseIcon({ state }: { state: ParseState }) {
  if (state === "ready") return <Check size={12} />;
  if (state === "uploading" || state === "reading" || state === "analyzing")
    return <Loader size={12} className="spin-icon" />;
  if (state === "pending") return <Clock3 size={12} />;
  if (state === "needs_confirm") return <AlertTriangle size={12} />;
  if (state === "failed") return <FileWarning size={12} />;
  return null;
}

/* ── detail panel ──────────────────────────────────── */

function LibraryDetailPanel({
  item,
  onClose,
  onDelete,
  onReparse,
  onPreview,
}: {
  item: LibraryItem;
  onClose: () => void;
  onDelete?: () => void;
  onReparse?: () => void;
  onPreview: () => void;
}) {
  const [reparsing, setReparsing] = useState(false);

  async function handleReparse() {
    setReparsing(true);
    try {
      await (onReparse as () => Promise<void>)?.();
    } finally {
      setReparsing(false);
    }
  }

  return (
    <aside className="library-detail-panel" role="complementary" aria-label="资料详情">
      <header className="library-detail-header">
        <div>
          <span className="library-detail-type">
            <TypeIcon type={item.type} />
            {typeLabels[item.type]}
          </span>
          <strong>{item.name}</strong>
        </div>
        <button aria-label="关闭详情" onClick={onClose} type="button"><X size={18} /></button>
      </header>

      <div className="library-detail-body">
        <section className="library-detail-section">
          <h3>基本信息</h3>
          <dl>
            <div><dt>版本</dt><dd>v{item.version}</dd></div>
            <div><dt>大小</dt><dd>{item.size ?? "—"}</dd></div>
            {item.pages && <div><dt>页数</dt><dd>{item.pages} 页</dd></div>}
            <div><dt>资料用途</dt><dd><span className={`role-tag role-${item.role}`}>{roleLabels[item.role]}</span></dd></div>
            <div><dt>解析状态</dt><dd><span className={`parse-tag parse-${item.parseState}`}><ParseIcon state={item.parseState} />{parseStateLabels[item.parseState]}</span></dd></div>
            <div><dt>最近更新</dt><dd>{item.updatedAt}</dd></div>
            <div><dt>标签</dt><dd><div className="library-detail-tags">{item.tags.map((tag) => <span key={tag}>{tag}</span>)}</div></dd></div>
          </dl>
        </section>

        <section className="library-detail-section">
          <h3>被引用课程</h3>
          {item.usedBy.length > 0 ? (
            <ul className="used-by-list">
              {item.usedBy.map((courseName) => (
                  <li key={courseName}>
                    <span className="course-dot teal" />
                    <span>{courseName}</span>
                  </li>
                ))}
            </ul>
          ) : (
            <p className="library-detail-empty-text">此资料尚未被任何课程引用。上传资料至资源库不会自动授权课程使用。</p>
          )}
        </section>

        <section className="library-detail-section">
          <h3>版本历史</h3>
          <div className="version-timeline">
            {Array.from({ length: item.version }, (_, i) => (
              <div className="version-entry" key={i}>
                <span className={`version-dot ${i === item.version - 1 ? "current" : ""}`} />
                <div><strong>v{i + 1}</strong><span>{i === 0 ? "首次上传" : i === item.version - 1 ? "当前版本" : `更新于 ${3 * (item.version - i)} 天前`}</span></div>
              </div>
            ))}
          </div>
        </section>

        <section className="library-detail-section">
          <h3>操作</h3>
          <div className="library-detail-actions">
            <button
              className="button secondary compact"
              disabled={item.parseState !== "ready"}
              onClick={onPreview}
              title={item.parseState !== "ready" ? "解析中，完成后可预览" : undefined}
              type="button"
            >
              <Eye size={15} /> 预览
            </button>
            <button className="button secondary compact" type="button" onClick={handleReparse} disabled={reparsing}>
              {reparsing ? <Loader size={15} className="spin" /> : <RefreshCw size={15} />}
              {reparsing ? "解析中…" : "重新解析"}
            </button>
            {item.usedBy.length === 0 && (
              <button className="button secondary compact danger" type="button" onClick={onDelete}><Trash2 size={15} /> 删除</button>
            )}
            {item.usedBy.length > 0 && (
              <p className="library-detail-empty-text">此资料正被 {item.usedBy.length} 门课程使用，删除前请先从课程资料中移除。</p>
            )}
          </div>
        </section>
      </div>
    </aside>
  );
}

/* ── folder sidebar ────────────────────────────────── */

function FolderSidebar({
  folders,
  activeFolder,
  onSelectFolder,
  onCreateFolder,
  onDeleteFolder,
  onDropItem,
  getFolderCount,
}: {
  folders: FolderItem[];
  activeFolder: string | null;
  onSelectFolder: (id: string | null) => void;
  onCreateFolder: (name: string) => void;
  onDeleteFolder: (id: string) => void;
  onDropItem: (itemId: string, folderId: string | null) => void;
  getFolderCount: (folderId: string | null) => number;
}) {
  const [newName, setNewName] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [dragOverId, setDragOverId] = useState<string | null>(null);
  const [dragOverAll, setDragOverAll] = useState(false);

  function handleCreate() {
    if (!newName.trim()) return;
    onCreateFolder(newName.trim());
    setIsCreating(false);
    setNewName("");
  }

  return (
    <aside className="library-folder-sidebar">
      <div className="folder-sidebar-header">
        <strong>文件夹</strong>
        <button
          aria-label="新建文件夹"
          className="folder-create-btn"
          onClick={() => setIsCreating(true)}
          title="新建文件夹"
          type="button"
        >
          <Plus size={15} />
        </button>
      </div>

      <nav className="folder-tree" aria-label="文件夹列表">
        {/* "All Materials" */}
        <button
          className={`folder-item all${activeFolder === null ? " active" : ""}${dragOverAll ? " drag-over" : ""}`}
          onClick={() => onSelectFolder(null)}
          onDragOver={(e) => { e.preventDefault(); setDragOverAll(true); }}
          onDragLeave={() => setDragOverAll(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOverAll(false);
            const itemId = e.dataTransfer.getData("text/lib-item-id");
            if (itemId) onDropItem(itemId, null);
          }}
          type="button"
        >
          <Folders size={15} />
          <span>全部资料</span>
          <span className="folder-count">{getFolderCount(null)}</span>
        </button>

        {folders.map((folder) => (
          <div
            className={`folder-item${activeFolder === folder.id ? " active" : ""}${dragOverId === folder.id ? " drag-over" : ""}`}
            key={folder.id}
            onClick={() => onSelectFolder(folder.id)}
            onDragOver={(e) => { e.preventDefault(); setDragOverId(folder.id); }}
            onDragLeave={() => setDragOverId(null)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOverId(null);
              const itemId = e.dataTransfer.getData("text/lib-item-id");
              if (itemId) onDropItem(itemId, folder.id);
            }}
          >
            {activeFolder === folder.id ? <FolderOpen size={15} /> : <FolderClosed size={15} />}
            <span>{folder.name}</span>
            <span className="folder-count">{getFolderCount(folder.id)}</span>
            <button
              aria-label={`删除文件夹 ${folder.name}`}
              className="folder-delete-btn"
              onClick={(e) => { e.stopPropagation(); onDeleteFolder(folder.id); }}
              title="删除文件夹"
              type="button"
            >
              <Trash2 size={12} />
            </button>
          </div>
        ))}

        {/* create inline */}
        {isCreating && (
          <div className="folder-create-inline">
            <FolderClosed size={15} />
            <input
              autoFocus
              onBlur={() => { if (!newName.trim()) setIsCreating(false); }}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate();
                if (e.key === "Escape") setIsCreating(false);
              }}
              placeholder="文件夹名称"
              type="text"
              value={newName}
            />
          </div>
        )}
      </nav>
    </aside>
  );
}

/* ── main page ─────────────────────────────────────── */

export function LibraryPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading, isFetching, error } = useLibraryData();
  const items = data?.items ?? [];
  const folders = data?.folders ?? [];
  const allTags = data?.tags ?? [];
  const sourceIdMap = useRef<Map<string, string>>(new Map());

  const refreshLibrary = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["library"] });
  }, [queryClient]);

  useEffect(() => {
    const map = new Map<string, string>();
    if (data?.sourceIdByItemId) {
      for (const [itemId, sourceId] of Object.entries(data.sourceIdByItemId)) {
        map.set(itemId, sourceId);
      }
    }
    sourceIdMap.current = map;
  }, [data?.sourceIdByItemId]);

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<LibraryItemType | "all">("all");
  const [tagFilter, setTagFilter] = useState<string>("all");
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<LibraryItem | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [typeMenuOpen, setTypeMenuOpen] = useState(false);
  const [tagMenuOpen, setTagMenuOpen] = useState(false);
  const showLoading = isLoading && items.length === 0;

  const folderCounts = useMemo(() => {
    const counts = new Map<string | null, number>();
    for (const item of items) {
      const key = item.folderId ?? null;
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    return counts;
  }, [items]);

  /* folder operations */
  async function handleCreateFolder(name: string) {
    try {
      await createFolder(name);
      refreshLibrary();
    } catch {
      // 失败静默
    }
  }

  async function handleDeleteFolder(id: string) {
    try {
      await deleteFolder(id);
      if (activeFolder === id) setActiveFolder(null);
      refreshLibrary();
    } catch {
      // 失败静默
    }
  }

  async function handleMoveItem(itemId: string, folderId: string | null) {
    const sourceId = sourceIdMap.current.get(itemId);
    if (!sourceId) return;
    try {
      await moveSource(sourceId, folderId);
      refreshLibrary();
    } catch {
      // 失败静默
    }
  }

  function getFolderCount(folderId: string | null): number {
    return folderCounts.get(folderId) ?? 0;
  }

  async function handleDeleteItem(itemId: string) {
    const sourceId = sourceIdMap.current.get(itemId);
    if (!sourceId) return;
    try {
      await deleteSource(sourceId);
      setSelectedItem(null);
      refreshLibrary();
    } catch {
      // 删除失败静默
    }
  }

  async function handleReparseItem(itemId: string) {
    const sourceId = sourceIdMap.current.get(itemId);
    if (!sourceId) return;
    try {
      await reparseSource(sourceId);
      refreshLibrary();
    } catch {
      // 重新解析失败静默
    }
  }

  const activeFolderName = activeFolder ? folders.find((f) => f.id === activeFolder)?.name ?? "" : "";

  /* table filtering */
  const filtered = useMemo(() => {
    let result = items;
    if (activeFolder !== null) {
      result = result.filter((item) => item.folderId === activeFolder);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (item) =>
          item.name.toLowerCase().includes(q) ||
          item.tags.some((t) => t.toLowerCase().includes(q)),
      );
    }
    if (typeFilter !== "all") result = result.filter((item) => item.type === typeFilter);
    if (tagFilter !== "all") result = result.filter((item) => item.tags.includes(tagFilter));
    return result;
  }, [items, activeFolder, search, typeFilter, tagFilter]);

  /* drag from table */
  function onRowDragStart(e: DragEvent, itemId: string) {
    e.dataTransfer.setData("text/lib-item-id", itemId);
    e.dataTransfer.effectAllowed = "move";
  }

  return (
    <AppShell>
      <div className="library-page">
        <header className="page-header">
          <div>
            <h1>资源库{isFetching && !showLoading ? " · 更新中…" : ""}</h1>
            <p>管理你的学习资料。上传资料仅进入资源库，不会自动授权任何课程使用。</p>
          </div>
          <div className="page-actions">
            <div className="search-field">
              <Search size={16} />
              <input
                onChange={(e) => setSearch(e.target.value)}
                placeholder="搜索资料名称或标签…"
                type="text"
                value={search}
              />
              {search && (
                <button className="search-clear" onClick={() => setSearch("")} type="button" aria-label="清除搜索">
                  <X size={14} />
                </button>
              )}
            </div>
            <button className="button primary" onClick={() => setShowUpload(true)} type="button">
              <Plus size={17} />添加资料
            </button>
          </div>
        </header>

        <div className="library-body">
          {/* folder sidebar */}
          <FolderSidebar
            activeFolder={activeFolder}
            folders={folders}
            getFolderCount={getFolderCount}
            onCreateFolder={handleCreateFolder}
            onDeleteFolder={handleDeleteFolder}
            onDropItem={handleMoveItem}
            onSelectFolder={setActiveFolder}
          />

          {/* main content */}
          <div className="library-main">
            {/* breadcrumb + filters */}
            <div className="library-top-row">
              {activeFolder && (
                <div className="library-breadcrumb">
                  <button onClick={() => setActiveFolder(null)} type="button">全部资料</button>
                  <ChevronRight size={13} />
                  <span>{activeFolderName}</span>
                  <span className="breadcrumb-count">{getFolderCount(activeFolder)} 项</span>
                </div>
              )}

              <div className="library-filters">
                <div className="filter-dropdown">
                  <button
                    className="filter-trigger"
                    onClick={() => { setTypeMenuOpen(!typeMenuOpen); setTagMenuOpen(false); }}
                    type="button"
                  >
                    <FileText size={14} />
                    {typeFilter === "all" ? "全部类型" : typeLabels[typeFilter]}
                    <ChevronDown size={13} />
                  </button>
                  {typeMenuOpen && (
                    <div className="filter-menu">
                      {ALL_TYPES.map((t) => (
                        <button
                          className={typeFilter === t ? "selected" : ""}
                          key={t}
                          onClick={() => { setTypeFilter(t); setTypeMenuOpen(false); }}
                          type="button"
                        >
                          {t === "all" ? "全部类型" : typeLabels[t]}
                          {typeFilter === t && <Check size={14} />}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                <div className="filter-dropdown">
                  <button
                    className="filter-trigger"
                    onClick={() => { setTagMenuOpen(!tagMenuOpen); setTypeMenuOpen(false); }}
                    type="button"
                  >
                    <Tag size={14} />
                    {tagFilter === "all" ? "全部标签" : tagFilter}
                    <ChevronDown size={13} />
                  </button>
                  {tagMenuOpen && (
                    <div className="filter-menu">
                      <button
                        className={tagFilter === "all" ? "selected" : ""}
                        onClick={() => { setTagFilter("all"); setTagMenuOpen(false); }}
                        type="button"
                      >
                        全部标签{tagFilter === "all" && <Check size={14} />}
                      </button>
                      {allTags.map((t) => (
                        <button
                          className={tagFilter === t ? "selected" : ""}
                          key={t}
                          onClick={() => { setTagFilter(t); setTagMenuOpen(false); }}
                          type="button"
                        >
                          {t}{tagFilter === t && <Check size={14} />}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {(activeFolder || search || typeFilter !== "all" || tagFilter !== "all") && (
                  <span className="filter-count">显示 {filtered.length} 项</span>
                )}
              </div>
            </div>

            {/* table */}
            <div className={`library-table-wrapper${selectedItem ? " detail-open" : ""}`}>
              <div className="library-table">
                <div className="library-table-head">
                  <span>资料名称与类型</span>
                  <span>标签</span>
                  <span>解析状态</span>
                  <span>最近更新</span>
                  <span>使用课程</span>
                  <span>操作</span>
                </div>

                {showLoading ? (
                  <div className="library-empty">
                    <Loader size={28} className="spin" />
                    <strong>正在加载…</strong>
                  </div>
                ) : error ? (
                  <div className="library-empty">
                    <AlertTriangle size={28} />
                    <strong>资料加载失败</strong>
                    <span>请检查网络连接后刷新页面，或稍后重试。</span>
                    <button className="button secondary compact" type="button" onClick={refreshLibrary}>
                      <RefreshCw size={15} /> 重试
                    </button>
                  </div>
                ) : items.length === 0 ? (
                  <div className="library-empty">
                    <Upload size={28} />
                    <strong>资源库暂无资料</strong>
                    <span>点击右上角「上传资料」将文件导入资源库</span>
                  </div>
                ) : filtered.length === 0 ? (
                  <div className="library-empty">
                    <Search size={28} />
                    <strong>没有匹配的资料</strong>
                    <span>
                      {activeFolder
                        ? "当前文件夹为空，可点击左侧「全部资料」查看所有资源"
                        : "尝试调整搜索条件或筛选器"}
                    </span>
                    {(activeFolder || search || typeFilter !== "all" || tagFilter !== "all") && (
                      <button
                        className="button secondary compact"
                        type="button"
                        onClick={() => {
                          setActiveFolder(null);
                          setSearch("");
                          setTypeFilter("all");
                          setTagFilter("all");
                        }}
                      >
                        清除筛选
                      </button>
                    )}
                  </div>
                ) : (
                  <VirtualLibraryRows
                    items={filtered}
                    renderRow={(item) => {
                      const Icon = typeIcons[item.type];
                      const isSelected = selectedItem?.id === item.id;
                      return (
                      <div
                        className={`library-row${isSelected ? " selected" : ""}`}
                        draggable
                        key={item.id}
                        onClick={() => setSelectedItem(isSelected ? null : item)}
                        onDragStart={(e) => onRowDragStart(e, item.id)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" || event.key === " ") {
                            event.preventDefault();
                            setSelectedItem(isSelected ? null : item);
                          }
                        }}
                        role="button"
                        tabIndex={0}
                      >
                        <span className="lib-cell-name">
                          <span className={`lib-type-icon type-${item.type}`}><Icon size={14} /></span>
                          <span className="lib-name-text">
                            <strong>{item.name}</strong>
                            <small>{typeLabels[item.type]}{item.size ? ` · ${item.size}` : ""}</small>
                          </span>
                        </span>
                        <span className="lib-cell-tags">
                          {item.tags.map((tag) => <span className="lib-tag" key={tag}>{tag}</span>)}
                        </span>
                        <span className="lib-cell-state">
                          <span className={`parse-tag parse-${item.parseState}`}>
                            <ParseIcon state={item.parseState} />{parseStateLabels[item.parseState]}
                          </span>
                        </span>
                        <span className="lib-cell-date">{item.updatedAt}</span>
                        <span className="lib-cell-courses">
                          {item.usedBy.length > 0
                            ? item.usedBy.map((c) => <span className="lib-course-link" key={c}><BookOpen size={10} />{c}</span>)
                            : <span className="lib-no-course">未引用</span>}
                        </span>
                        <span className="lib-cell-actions" onClick={(e) => e.stopPropagation()}>
                          <button aria-label="更多操作" className="icon-button" type="button"><MoreHorizontal size={17} /></button>
                        </span>
                      </div>
                      );
                    }}
                  />
                )}
              </div>

              {selectedItem && (
                <LibraryDetailPanel
                  item={selectedItem}
                  onClose={() => setSelectedItem(null)}
                  onDelete={() => handleDeleteItem(selectedItem.id)}
                  onPreview={() => navigate(buildLibraryReaderPath(selectedItem.id))}
                  onReparse={() => handleReparseItem(selectedItem.id)}
                />
              )}
            </div>
          </div>
        </div>
      </div>

      {showUpload && (
        <SourceUploadModal
          onClose={() => setShowUpload(false)}
          onUploaded={refreshLibrary}
        />
      )}
    </AppShell>
  );
}
