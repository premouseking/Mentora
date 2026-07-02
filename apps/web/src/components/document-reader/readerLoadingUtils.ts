/** 将字节进度映射到 [start, end] 区间百分比。 */
export function mapByteProgress(
  loaded: number,
  total: number | null | undefined,
  start: number,
  end: number,
): number {
  if (!total || total <= 0) {
    // 无 Content-Length 时用对数缓动，避免长期停在低位
    const assumed = 12 * 1024 * 1024;
    const ratio = Math.min(0.92, loaded / assumed);
    return start + (end - start) * ratio;
  }
  const ratio = Math.min(1, Math.max(0, loaded / total));
  return start + (end - start) * ratio;
}

export type ReaderFetchStage = "meta" | "blocks" | "bundle" | "ready";

export function resolveFetchStageProgress(stage: ReaderFetchStage): {
  progress: number;
  label: string;
  indeterminate: boolean;
} {
  switch (stage) {
    case "meta":
      return { progress: 18, label: "加载文档索引…", indeterminate: true };
    case "blocks":
      return { progress: 42, label: "加载页面结构…", indeterminate: true };
    case "bundle":
      return { progress: 58, label: "加载文档内容…", indeterminate: true };
    default:
      return { progress: 100, label: "", indeterminate: false };
  }
}
