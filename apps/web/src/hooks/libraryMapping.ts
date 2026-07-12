import type { LibraryItem, LibraryItemType, ParseState } from "../data/library";
import type { SourceItem } from "../services/documentApi";

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function sourceToLibraryItem(s: SourceItem): LibraryItem {
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
    tags: s.tags ?? [],
    parseState: status,
    updatedAt: s.updatedAt?.slice(0, 10) ?? new Date().toISOString().slice(0, 10),
    usedBy: [],
    role: "primary" as const,
    version: v?.versionNumber ?? 1,
    folderId: s.folderId ?? null,
    size: v?.byteSize ? formatBytes(v.byteSize) : undefined,
    lifecycleStatus: s.status === "archived" ? "archived" : "active",
  };
}
