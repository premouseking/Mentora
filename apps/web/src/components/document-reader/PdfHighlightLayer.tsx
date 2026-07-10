/**
 * LightRead 风格块高亮层：基于 PdfBlock + 页尺寸 overlay。
 * 增量 diff DOM，layer 级事件委托，避免频繁翻页时整层重建。
 */
import { useEffect, useMemo, useRef } from "react";

import type { PdfBlock } from "../../services/resourceTypes";
import { filterInteractiveBlocks } from "./resourceReaderUtils";
import { bboxToPercentStyle } from "./pdfReaderUtils";
import type { ActiveBlockRef, FlashRect } from "./pdfReaderStateStore";

interface PdfHighlightLayerProps {
  blocks: PdfBlock[];
  pageSizes: Map<number, [number, number]>;
  viewerElement: HTMLDivElement | null;
  activeBlock: ActiveBlockRef | null;
  flashRects: FlashRect[];
  onBlockHover: (block: ActiveBlockRef | null) => void;
  onBlockClick: (block: ActiveBlockRef) => void;
  onEvent: (event: "pagerendered" | "scalechanging", handler: (evt: unknown) => void) => () => void;
}

function blockNodeKey(page: number, blockIdx: string): string {
  return `${page}:${blockIdx}`;
}

export function PdfHighlightLayer({
  blocks,
  pageSizes,
  viewerElement,
  activeBlock,
  flashRects,
  onBlockHover,
  onBlockClick,
  onEvent,
}: PdfHighlightLayerProps) {
  const blockNodeRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const onBlockHoverRef = useRef(onBlockHover);
  const onBlockClickRef = useRef(onBlockClick);
  onBlockHoverRef.current = onBlockHover;
  onBlockClickRef.current = onBlockClick;

  const blocksByPage = useMemo(() => {
    const map = new Map<number, PdfBlock[]>();
    for (const block of filterInteractiveBlocks(blocks)) {
      if (!block.bbox) continue;
      const list = map.get(block.page) ?? [];
      list.push(block);
      map.set(block.page, list);
    }
    return map;
  }, [blocks]);

  useEffect(() => {
    if (!viewerElement) return;

    function ensureLayer(pageEl: HTMLDivElement): HTMLDivElement {
      let layer = pageEl.querySelector<HTMLDivElement>(".pdf-highlight-layer");
      if (!layer) {
        layer = document.createElement("div");
        layer.className = "pdf-highlight-layer pdf-parsed-overlay";
        pageEl.appendChild(layer);
      }
      return layer;
    }

    function syncLayers() {
      if (!viewerElement) return;

      const seenKeys = new Set<string>();
      const pageElements = viewerElement.querySelectorAll<HTMLDivElement>(".page");

      pageElements.forEach((pageEl) => {
        const pageNumber = Number(pageEl.dataset.pageNumber);
        if (!Number.isFinite(pageNumber)) return;

        const layer = ensureLayer(pageEl);
        const pageSize = pageSizes.get(pageNumber);
        const pageBlocks = blocksByPage.get(pageNumber) ?? [];

        if (!pageSize) {
          layer.replaceChildren();
          return;
        }

        for (const block of pageBlocks) {
          if (!block.bbox) continue;
          const key = blockNodeKey(pageNumber, block.idx);
          seenKeys.add(key);

          let rect = blockNodeRefs.current.get(key);
          if (!rect || !layer.contains(rect)) {
            rect = document.createElement("button");
            rect.type = "button";
            rect.className = `pdf-parsed-block pdf-block-${block.type}`;
            rect.dataset.blockIdx = block.idx;
            rect.dataset.pageNumber = String(pageNumber);
            if (block.evidence_unit_id) {
              rect.dataset.evidenceUnitId = block.evidence_unit_id;
            }
            layer.appendChild(rect);
            blockNodeRefs.current.set(key, rect);
          }

          const bbox = {
            x0: block.bbox[0],
            y0: block.bbox[1],
            x1: block.bbox[2],
            y1: block.bbox[3],
          };
          Object.assign(rect.style, bboxToPercentStyle(bbox, pageSize));
        }

        const liveKeys = new Set(pageBlocks.map((block) => blockNodeKey(pageNumber, block.idx)));
        layer.querySelectorAll<HTMLButtonElement>(".pdf-parsed-block").forEach((node) => {
          const blockIdx = node.dataset.blockIdx;
          if (!blockIdx) return;
          const key = blockNodeKey(pageNumber, blockIdx);
          if (!liveKeys.has(key)) {
            blockNodeRefs.current.delete(key);
            node.remove();
          }
        });
      });

      blockNodeRefs.current.forEach((node, key) => {
        if (!seenKeys.has(key)) {
          blockNodeRefs.current.delete(key);
          node.remove();
        }
      });
    }

    syncLayers();
    const offRendered = onEvent("pagerendered", syncLayers);
    const offScale = onEvent("scalechanging", syncLayers);
    return () => {
      offRendered();
      offScale();
    };
  }, [blocksByPage, onEvent, pageSizes, viewerElement]);

  useEffect(() => {
    blockNodeRefs.current.forEach((node, key) => {
      const [pageRaw, blockIdx] = key.split(":");
      const page = Number(pageRaw);
      const isActive = activeBlock?.blockIdx === blockIdx && activeBlock.page === page;
      node.classList.toggle("is-active", isActive);
    });
  }, [activeBlock]);

  useEffect(() => {
    if (!viewerElement) return;

    viewerElement.querySelectorAll<HTMLDivElement>(".pdf-evidence-flash").forEach((node) => {
      node.remove();
    });

    if (flashRects.length === 0) return;

    for (const flashRect of flashRects) {
      const pageEl = viewerElement.querySelector<HTMLDivElement>(
        `.page[data-page-number="${flashRect.page}"]`,
      );
      if (!pageEl) continue;

      const layer = pageEl.querySelector<HTMLDivElement>(".pdf-highlight-layer");
      const pageSize = pageSizes.get(flashRect.page);
      if (!layer || !pageSize) continue;

      const flash = document.createElement("div");
      flash.className = "pdf-parsed-flash pdf-evidence-flash";
      const fb = flashRect.bbox;
      Object.assign(
        flash.style,
        bboxToPercentStyle(
          { x0: fb[0], y0: fb[1], x1: fb[2], y1: fb[3] },
          pageSize,
        ),
      );
      layer.appendChild(flash);
    }
  }, [flashRects, pageSizes, viewerElement]);

  useEffect(() => {
    if (!viewerElement) return;

    function handlePointerOver(event: Event) {
      const target = (event.target as HTMLElement | null)?.closest<HTMLButtonElement>(".pdf-parsed-block");
      if (!target?.dataset.blockIdx || !target.dataset.pageNumber) return;
      onBlockHoverRef.current({
        blockIdx: target.dataset.blockIdx,
        page: Number(target.dataset.pageNumber),
      });
    }

    function handlePointerOut(event: Event) {
      const related = (event as MouseEvent).relatedTarget as HTMLElement | null;
      if (related?.closest(".pdf-parsed-block")) return;
      onBlockHoverRef.current(null);
    }

    function handleClick(event: Event) {
      const target = (event.target as HTMLElement | null)?.closest<HTMLButtonElement>(".pdf-parsed-block");
      if (!target?.dataset.blockIdx || !target.dataset.pageNumber) return;
      event.preventDefault();
      event.stopPropagation();
      onBlockClickRef.current({
        blockIdx: target.dataset.blockIdx,
        page: Number(target.dataset.pageNumber),
      });
    }

    viewerElement.addEventListener("mouseover", handlePointerOver);
    viewerElement.addEventListener("mouseout", handlePointerOut);
    viewerElement.addEventListener("click", handleClick);
    return () => {
      viewerElement.removeEventListener("mouseover", handlePointerOver);
      viewerElement.removeEventListener("mouseout", handlePointerOut);
      viewerElement.removeEventListener("click", handleClick);
    };
  }, [viewerElement]);

  return null;
}
