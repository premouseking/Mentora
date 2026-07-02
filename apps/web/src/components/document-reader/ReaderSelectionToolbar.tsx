import { Copy, Quote } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

interface ReaderSelectionToolbarProps {
  containerRef: React.RefObject<HTMLElement | null>;
}

interface ToolbarState {
  text: string;
  left: number;
  top: number;
}

export function ReaderSelectionToolbar({ containerRef }: ReaderSelectionToolbarProps) {
  const [state, setState] = useState<ToolbarState | null>(null);

  const hide = useCallback(() => setState(null), []);

  const updateFromSelection = useCallback(() => {
    const container = containerRef.current;
    if (!container) {
      hide();
      return;
    }

    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) {
      hide();
      return;
    }

    const range = selection.getRangeAt(0);
    const anchorNode = range.commonAncestorContainer;
    const anchorEl = anchorNode.nodeType === Node.ELEMENT_NODE
      ? (anchorNode as Element)
      : anchorNode.parentElement;
    if (!anchorEl || !container.contains(anchorEl)) {
      hide();
      return;
    }

    const text = selection.toString().trim();
    if (!text) {
      hide();
      return;
    }

    const rect = range.getBoundingClientRect();
    if (!rect.width && !rect.height) {
      hide();
      return;
    }

    setState({
      text,
      left: rect.left + rect.width / 2,
      top: Math.max(8, rect.top - 8),
    });
  }, [containerRef, hide]);

  useEffect(() => {
    document.addEventListener("selectionchange", updateFromSelection);
    document.addEventListener("mouseup", updateFromSelection);
    document.addEventListener("keyup", updateFromSelection);
    const container = containerRef.current;
    container?.addEventListener("scroll", hide, { passive: true });
    return () => {
      document.removeEventListener("selectionchange", updateFromSelection);
      document.removeEventListener("mouseup", updateFromSelection);
      document.removeEventListener("keyup", updateFromSelection);
      container?.removeEventListener("scroll", hide);
    };
  }, [containerRef, hide, updateFromSelection]);

  if (!state) return null;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(state!.text);
    } catch {
      // 浏览器可能拒绝 clipboard
    }
    hide();
    window.getSelection()?.removeAllRanges();
  }

  function handleQuote() {
    // 第一版占位：后续接入 AI 助手上下文
    hide();
    window.getSelection()?.removeAllRanges();
  }

  return (
    <div
      className="reader-selection-toolbar"
      style={{ left: state.left, top: state.top }}
      onMouseDown={(event) => event.preventDefault()}
    >
      <button onClick={handleCopy} title="复制" type="button">
        <Copy size={14} />
        <span>复制</span>
      </button>
      <button onClick={handleQuote} title="引用到 AI 助手" type="button">
        <Quote size={14} />
        <span>引用</span>
      </button>
    </div>
  );
}
