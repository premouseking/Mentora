import { useEffect, useState, type RefObject } from "react";

/**
 * 容器获得非零且连续两帧稳定的尺寸后再渲染依赖布局的子树（如 pdf.js）。
 * 避免 flex/tab 尚未完成分配时 clientHeight=0 导致白屏，直到 window resize 才恢复。
 */
export function useLayoutReady(targetRef: RefObject<HTMLElement | null>) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const element = targetRef.current;
    if (!element) return;

    let cancelled = false;
    let stableFrames = 0;
    let lastWidth = 0;
    let lastHeight = 0;
    let rafId = 0;

    const evaluate = () => {
      if (cancelled) return;
      const { width, height } = element.getBoundingClientRect();
      if (width <= 0 || height <= 0) {
        stableFrames = 0;
        lastWidth = 0;
        lastHeight = 0;
        setReady(false);
        return;
      }

      const sizeStable =
        Math.abs(width - lastWidth) < 0.5 && Math.abs(height - lastHeight) < 0.5;
      if (sizeStable) {
        stableFrames += 1;
      } else {
        stableFrames = 1;
      }
      lastWidth = width;
      lastHeight = height;

      if (stableFrames >= 2) {
        setReady(true);
      }
    };

    const scheduleEvaluate = () => {
      window.cancelAnimationFrame(rafId);
      rafId = window.requestAnimationFrame(evaluate);
    };

    scheduleEvaluate();
    const observer = new ResizeObserver(() => scheduleEvaluate());
    observer.observe(element);

    return () => {
      cancelled = true;
      window.cancelAnimationFrame(rafId);
      observer.disconnect();
    };
  }, [targetRef]);

  return ready;
}
