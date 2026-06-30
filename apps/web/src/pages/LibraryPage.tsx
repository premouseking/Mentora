import { useMemo, useState, useEffect, useRef, useCallback, type DragEvent } from "react";
import {
  AlertTriangle,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  ExternalLink,
  Eye,
  FileText,
  FileWarning,
  FolderClosed,
  FolderOpen,
  Folders,
  Globe,
  HardDrive,
  History,
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
  fetchSources, deleteSource, reparseSource,
  fetchFolders, createFolder, deleteFolder,
  fetchTags, moveSource,
  type SourceItem, type FolderItem,
} from "../services/documentApi";
import { uploadFile, type UploadProgress } from "../services/uploadService";
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

const allTags: string[] = [];

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

function LibraryDetailPanel({ item, onClose, onDelete, onReparse }: { item: LibraryItem; onClose: () => void; onDelete?: () => void; onReparse?: () => void }) {
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
            <button className="button secondary compact" type="button"><Eye size={15} /> 预览</button>
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

/* ── upload modal ──────────────────────────────────── */

const ACCEPTED_TYPES = ".pdf,.docx,.pptx,.xlsx,.png,.jpg,.jpeg,.mp4,.mp3";

interface UploadModalProps {
  onClose: () => void;
  onUploaded: () => void;
}

function UploadModal({ onClose, onUploaded }: UploadModalProps) {
  const [dragOver, setDragOver] = useState(false);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function pickFile() {
    fileInputRef.current?.click();
  }

  async function handleFile(file: File) {
    setProgress({ step: "create", message: "正在创建上传会话…" });
    try {
      await uploadFile(file, (p) => setProgress(p));
      setProgress({ step: "done", message: "上传完成，解析中…" });
      setTimeout(() => {
        onUploaded();
        onClose();
      }, 800);
    } catch (err: unknown) {
      setProgress({
        step: "error",
        message: err instanceof Error ? err.message : "上传失败",
      });
    }
  }

  function onFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (f) handleFile(f);
    // reset so same file can be picked again
    e.target.value = "";
  }

  function onDrop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }

  if (progress) {
    const isError = progress.step === "error";
    return (
      <div className="library-modal-overlay" onClick={isError ? onClose : undefined}>
        <div className="library-modal" onClick={(e) => e.stopPropagation()}>
          <header className="library-modal-header">
            <strong>{isError ? "上传失败" : "正在上传"}</strong>
            <button aria-label="关闭" onClick={onClose} type="button"><X size={17} /></button>
          </header>
          <div className="library-upload-zone" style={{ textAlign: "center", padding: "40px 24px" }}>
            {isError ? (
              <>
                <FileWarning size={32} color="#e74c3c" />
                <p style={{ color: "#e74c3c", marginTop: 12 }}>{progress.message}</p>
                <button className="button secondary" onClick={() => setProgress(null)} style={{ marginTop: 12 }}>
                  重新上传
                </button>
              </>
            ) : (
              <>
                <Loader size={32} className="spin" />
                <p style={{ marginTop: 12 }}>{progress.message}</p>
              </>
            )}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="library-modal-overlay" onClick={onClose}>
      <div className="library-modal" onClick={(e) => e.stopPropagation()}>
        <header className="library-modal-header">
          <strong>添加资料</strong>
          <button aria-label="关闭" onClick={onClose} type="button"><X size={17} /></button>
        </header>
        <input
          ref={fileInputRef}
          accept={ACCEPTED_TYPES}
          style={{ display: "none" }}
          type="file"
          onChange={onFileChange}
        />
        <div
          className={`library-upload-zone${dragOver ? " drag-over" : ""}`}
          onDragEnter={() => setDragOver(true)}
          onDragLeave={() => setDragOver(false)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
        >
          <Upload size={28} />
          <strong>拖拽文件到此处上传</strong>
          <span>支持 PDF、Word、PPT、图片、视频、音频</span>
        </div>
        <div className="library-modal-separator"><span>或者</span></div>
        <div className="library-add-options">
          <button className="button secondary" type="button" onClick={pickFile}><Folders size={16} />从本地选择文件</button>
          <button className="button secondary" type="button" onClick={() => {}}><Globe size={16} />添加网页链接</button>
        </div>
        <p className="library-upload-note">上传资料仅进入资源库，不会自动授权任何课程访问。</p>
      </div>
    </div>
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

function sourceToLibraryItem(s: SourceItem): LibraryItem {
  const v = s.latestVersion;
  const status: ParseState = v
    ? v.processingStatus === "completed" ? "ready"
    : v.processingStatus === "failed" ? "failed"
    : v.processingStatus === "processing" ? "reading"
    : "pending"
    : "pending";
  const filename = v?.originalFilename ?? "";
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  const typeMap: Record<string, LibraryItemType> = {
    pdf: "pdf", docx: "docx", pptx: "pptx",
    png: "image", jpg: "image", jpeg: "image",
    mp4: "video", mp3: "audio",
  };
  return {
    id: v?.id ?? s.id,
    name: s.displayTitle || filename || "未命名",
    type: typeMap[ext] ?? "pdf",
    tags: [],
    parseState: status,
    updatedAt: new Date().toISOString().slice(0, 10),
    usedBy: [],
    role: "primary" as const,
    version: v?.versionNumber ?? 1,
    folderId: null,
  };
}

export function LibraryPage() {
  const [items, setItems] = useState<LibraryItem[]>([]);
  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [allTags, setAllTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const sourceIdMap = useRef<Map<string, string>>(new Map());

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<LibraryItemType | "all">("all");
  const [tagFilter, setTagFilter] = useState<string>("all");
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [selectedItem, setSelectedItem] = useState<LibraryItem | null>(null);
  const [showUpload, setShowUpload] = useState(false);
  const [typeMenuOpen, setTypeMenuOpen] = useState(false);
  const [tagMenuOpen, setTagMenuOpen] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [sources, folderData, tagData] = await Promise.all([
        fetchSources(),
        fetchFolders(),
        fetchTags(),
      ]);
      const map = new Map<string, string>();
      const mapped = sources.map((s) => {
        const item = sourceToLibraryItem(s);
        map.set(item.id, s.id);
        return item;
      });
      sourceIdMap.current = map;
      setItems(mapped);
      setFolders(folderData);
      setAllTags(tagData);
    } catch {
      // 保留现有数据
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  /* folder operations */
  async function handleCreateFolder(name: string) {
    try {
      const created = await createFolder(name);
      setFolders((prev) => [...prev, created]);
    } catch {
      // 失败静默
    }
  }

  async function handleDeleteFolder(id: string) {
    try {
      await deleteFolder(id);
      setFolders((prev) => prev.filter((f) => f.id !== id));
      setItems((prev) => prev.map((item) => (item.folderId === id ? { ...item, folderId: null } : item)));
      if (activeFolder === id) setActiveFolder(null);
    } catch {
      // 失败静默
    }
  }

  async function handleMoveItem(itemId: string, folderId: string | null) {
    const sourceId = sourceIdMap.current.get(itemId);
    if (!sourceId) return;
    try {
      await moveSource(sourceId, folderId);
      setItems((prev) => prev.map((item) => (item.id === itemId ? { ...item, folderId } : item)));
    } catch {
      // 失败静默
    }
  }

  function getFolderCount(folderId: string | null): number {
    return items.filter((item) => item.folderId === folderId).length;
  }

  async function handleDeleteItem(itemId: string) {
    const sourceId = sourceIdMap.current.get(itemId);
    if (!sourceId) return;
    try {
      await deleteSource(sourceId);
      setItems((prev) => prev.filter((i) => i.id !== itemId));
      setSelectedItem(null);
    } catch {
      // 删除失败静默
    }
  }

  async function handleReparseItem(itemId: string) {
    const sourceId = sourceIdMap.current.get(itemId);
    if (!sourceId) return;
    try {
      await reparseSource(sourceId);
      loadData();  // 刷新列表（更新解析状态）
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
            <h1>资源库</h1>
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

                {loading ? (
                  <div className="library-empty">
                    <Loader size={28} className="spin" />
                    <strong>正在加载…</strong>
                  </div>
                ) : filtered.length === 0 ? (
                  <div className="library-empty">
                    <Search size={28} />
                    <strong>没有匹配的资料</strong>
                    <span>尝试调整搜索条件或筛选器</span>
                  </div>
                ) : (
                  filtered.map((item) => {
                    const Icon = typeIcons[item.type];
                    const isSelected = selectedItem?.id === item.id;
                    return (
                      <button
                        className={`library-row${isSelected ? " selected" : ""}`}
                        draggable
                        key={item.id}
                        onClick={() => setSelectedItem(isSelected ? null : item)}
                        onDragStart={(e) => onRowDragStart(e, item.id)}
                        type="button"
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
                      </button>
                    );
                  })
                )}
              </div>

              {selectedItem && (
                <LibraryDetailPanel item={selectedItem} onClose={() => setSelectedItem(null)} onDelete={() => handleDeleteItem(selectedItem.id)} onReparse={() => handleReparseItem(selectedItem.id)} />
              )}
            </div>
          </div>
        </div>
      </div>

      {showUpload && <UploadModal onClose={() => setShowUpload(false)} onUploaded={loadData} />}
    </AppShell>
  );
}
