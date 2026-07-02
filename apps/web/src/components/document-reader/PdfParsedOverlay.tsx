import { useEffect, useMemo, useRef } from "react";

import type { BoundingBox, ParsedPage } from "../../services/parsedBundleContract";
import { bboxToPercentStyle } from "./pdfReaderUtils";

export interface ActiveBlockRef {
  pageNumber: number;
  elementIndex: number;
}

interface PdfParsedOverlayProps {
  pages: ParsedPage[];
  viewerElement: HTMLDivElement | null;
  activeBlock: ActiveBlockRef | null;
  flashBbox: { pageNumber: number; bbox: BoundingBox } | null;
  onBlockHover: (block: ActiveBlockRef | null) => void;
  onBlockClick: (block: ActiveBlockRef) => void;
  onEvent: (event: "pagerendered" | "scalechanging", handler: (evt: unknown) => void) => () => void;
}

export function PdfParsedOverlay({
  pages,
  viewerElement,
  activeBlock,
  flashBbox,
  onBlockHover,
  onBlockClick,
  onEvent,
}: PdfParsedOverlayProps) {
  const layerRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  const pageMap = useMemo(() => {
    const map = new Map<number, ParsedPage>();
    for (const page of pages) map.set(page.page_number, page);
    return map;
  }, [pages]);

  useEffect(() => {
    if (!viewerElement) return;

    function mountLayers() {
      if (!viewerElement) return;
      const pageElements = viewerElement.querySelectorAll<HTMLDivElement>(".page");
      pageElements.forEach((pageEl) => {
        const pageNumber = Number(pageEl.dataset.pageNumber);
        if (!Number.isFinite(pageNumber)) return;

        let layer = pageEl.querySelector<HTMLDivElement>(".pdf-parsed-overlay");
        if (!layer) {
          layer = document.createElement("div");
          layer.className = "pdf-parsed-overlay";
          pageEl.appendChild(layer);
        }
        layerRefs.current.set(pageNumber, layer);

        const pageData = pageMap.get(pageNumber);
        layer.innerHTML = "";
        if (!pageData?.page_size) return;

        pageData.elements.forEach((element, elementIndex) => {
          if (!element.bbox) return;
          const rect = document.createElement("button");
          rect.type = "button";
          rect.className = "pdf-parsed-block";
          rect.dataset.elementIndex = String(elementIndex);
          const style = bboxToPercentStyle(element.bbox, pageData.page_size!);
          Object.assign(rect.style, style);
          if (
            activeBlock?.pageNumber === pageNumber
            && activeBlock.elementIndex === elementIndex
          ) {
            rect.classList.add("is-active");
          }
          rect.addEventListener("mouseenter", () => {
            onBlockHover({ pageNumber, elementIndex });
          });
          rect.addEventListener("mouseleave", () => onBlockHover(null));
          rect.addEventListener("click", (event) => {
            event.preventDefault();
            event.stopPropagation();
            onBlockClick({ pageNumber, elementIndex });
          });
          layer!.appendChild(rect);
        });

        if (
          flashBbox
          && flashBbox.pageNumber === pageNumber
          && pageData.page_size
        ) {
          const flash = document.createElement("div");
          flash.className = "pdf-parsed-flash";
          Object.assign(flash.style, bboxToPercentStyle(flashBbox.bbox, pageData.page_size));
          layer.appendChild(flash);
        }
      });
    }

    mountLayers();
    const offRendered = onEvent("pagerendered", mountLayers);
    const offScale = onEvent("scalechanging", mountLayers);
    return () => {
      offRendered();
      offScale();
    };
  }, [
    activeBlock,
    flashBbox,
    onBlockClick,
    onBlockHover,
    onEvent,
    pageMap,
    viewerElement,
  ]);

  return null;
}
