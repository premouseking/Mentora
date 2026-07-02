/** pdf.js 在 flex/tab 容器首帧尺寸未稳定时需延迟 update，避免依赖 window.resize。 */

export function schedulePdfViewerUpdate(
  update: () => void,
): () => void {
  let cancelled = false;
  const raf1 = window.requestAnimationFrame(() => {
    if (cancelled) return;
    update();
    window.requestAnimationFrame(() => {
      if (cancelled) return;
      update();
      window.setTimeout(() => {
        if (!cancelled) update();
      }, 0);
    });
  });
  return () => {
    cancelled = true;
    window.cancelAnimationFrame(raf1);
  };
}
