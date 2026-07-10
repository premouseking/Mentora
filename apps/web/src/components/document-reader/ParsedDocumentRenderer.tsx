import { useEffect, useMemo, useRef, useState } from "react";

import type { BundleRaw, ParsedElementRaw } from "../../services/documentApi";
import { buildLibraryAssetUrl } from "../../services/documentApi";
import { fetchProtectedAssetBlobUrl } from "../../services/assetApi";
import {
  buildHighlightNeedle,
  elementAnchorId,
  findHighlightIndex,
  headingAnchorId,
  pageAnchorId,
} from "./readerUtils";
import type { EvidenceHighlight } from "./types";

function HighlightedText({ text, needle }: { text: string; needle: string }) {
  const match = findHighlightIndex(text, needle);
  if (!match) return <>{text}</>;
  const { start, length } = match;
  return (
    <>
      {text.slice(0, start)}
      <mark className="doc-evidence-highlight">{text.slice(start, start + length)}</mark>
      {text.slice(start + length)}
    </>
  );
}

function resolveImageSrc(
  el: ParsedElementRaw,
  sourceVersionId?: string | null,
): string | null {
  const url = el.extra?.url;
  if (typeof url === "string" && url) return url;
  const artifactRef = el.extra?.artifact_ref;
  if (sourceVersionId && typeof artifactRef === "string" && artifactRef) {
    return buildLibraryAssetUrl(sourceVersionId, artifactRef);
  }
  return null;
}

function isMeaningfulCaption(text: string): boolean {
  return Boolean(text && text !== "[图片]");
}

function ProtectedDocumentImage({ src, alt }: { src: string; alt: string }) {
  const [resolvedSrc, setResolvedSrc] = useState(src.startsWith("/api/") ? "" : src);

  useEffect(() => {
    if (!src.startsWith("/api/")) {
      setResolvedSrc(src);
      return;
    }
    const controller = new AbortController();
    let blobUrl = "";
    void fetchProtectedAssetBlobUrl(src, controller.signal).then((url) => {
      blobUrl = url;
      setResolvedSrc(url);
    }).catch(() => setResolvedSrc(""));
    return () => {
      controller.abort();
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [src]);

  return resolvedSrc
    ? <img src={resolvedSrc} alt={alt} className="doc-image" loading="lazy" />
    : null;
}

export function ParsedDocumentRenderer({
  bundle,
  evidenceHighlight,
  activePageNumber,
  sourceVersionId,
}: {
  bundle: BundleRaw;
  evidenceHighlight?: EvidenceHighlight | null;
  activePageNumber?: number | null;
  sourceVersionId?: string | null;
}) {
  const highlightPageRef = useRef<HTMLDivElement | null>(null);
  const highlightNeedle = useMemo(
    () => buildHighlightNeedle(evidenceHighlight?.content ?? ""),
    [evidenceHighlight?.content],
  );

  useEffect(() => {
    if (!evidenceHighlight?.pageNumber) return;
    highlightPageRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [bundle.id, evidenceHighlight?.evidenceId, evidenceHighlight?.pageNumber]);

  return (
    <div className="document-reader">
      {bundle.pages.map((page) => {
        const isHighlightPage = evidenceHighlight?.pageNumber === page.page_number;
        const isActivePage = activePageNumber === page.page_number;
        return (
          <div
            key={page.page_number}
            id={pageAnchorId(page.page_number)}
            ref={isHighlightPage ? highlightPageRef : undefined}
            className={[
              "doc-page",
              isHighlightPage ? "doc-page-highlighted" : "",
              isActivePage ? "doc-page-active" : "",
            ].filter(Boolean).join(" ")}
            data-page-number={page.page_number}
          >
            <div className="doc-page-number">第 {page.page_number} 页</div>
            {page.elements.map((el, index) => {
              const text = el.text || "";
              const shouldHighlight = isHighlightPage && highlightNeedle;
              const content = shouldHighlight
                ? <HighlightedText text={text} needle={highlightNeedle} />
                : text;
              const anchorId = el.type === "heading"
                ? headingAnchorId(page.page_number, index)
                : elementAnchorId(page.page_number, index);

              if (el.type === "heading") {
                const level = Math.min(el.heading_level ?? 1, 3);
                const sizes = [22, 18, 16];
                return (
                  <div
                    key={index}
                    id={anchorId}
                    className="doc-heading"
                    data-toc-id={anchorId}
                    style={{ fontSize: sizes[level - 1], fontWeight: 700 }}
                  >
                    {content}
                  </div>
                );
              }
              if (el.type === "paragraph") {
                return (
                  <p key={index} id={anchorId} className="doc-paragraph">
                    {content}
                  </p>
                );
              }
              if (el.type === "list_item") {
                return (
                  <div key={index} id={anchorId} className="doc-list-item">
                    • {content}
                  </div>
                );
              }
              if (el.type === "image") {
                const src = resolveImageSrc(
                  el,
                  sourceVersionId ?? bundle.source_version_id ?? null,
                );
                if (src) {
                  const caption = isMeaningfulCaption(text) ? text : null;
                  return (
                    <div key={index} id={anchorId} className="doc-image-wrap">
                      <ProtectedDocumentImage src={src} alt={text || "图片"} />
                      {caption ? <div className="doc-image-caption">{caption}</div> : null}
                    </div>
                  );
                }
                return (
                  <div key={index} id={anchorId} className="doc-image-placeholder">
                    [图片]
                  </div>
                );
              }
              return (
                <p key={index} id={anchorId} className="doc-paragraph">
                  {content || `[${el.type}]`}
                </p>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
