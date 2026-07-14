/**
 * LightRead 风格阅读器加载态：顶部细进度条 + 居中阶段文案。
 */
export interface ReaderLoadingProgressProps {
  progress: number;
  label: string;
  /** 无可靠进度时使用顶部 indeterminate 动画 */
  indeterminate?: boolean;
}

export function ReaderLoadingProgress({
  progress,
  label,
  indeterminate = false,
}: ReaderLoadingProgressProps) {
  const pct = Math.max(0, Math.min(100, progress));

  return (
    <div
      className="reader-loading-overlay"
      role="status"
      aria-live="polite"
      aria-busy="true"
      aria-valuenow={indeterminate ? undefined : Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div className={`reader-loading-bar-track${indeterminate ? " is-indeterminate" : ""}`}>
        <div
          className="reader-loading-bar-fill"
          style={indeterminate ? undefined : { width: `${pct}%` }}
        />
      </div>
      <div className="reader-loading-panel">
        <p className="reader-loading-label">{label}</p>
        {!indeterminate ? (
          <span className="reader-loading-percent">{Math.round(pct)}%</span>
        ) : null}
      </div>
    </div>
  );
}
