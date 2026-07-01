import type { BundleRaw } from "../../services/documentApi";
import type { ReaderTocItem } from "./types";

export function pageAnchorId(pageNumber: number): string {
  return `doc-page-${pageNumber}`;
}

export function elementAnchorId(pageNumber: number, elementIndex: number): string {
  return `doc-el-${pageNumber}-${elementIndex}`;
}

export function headingAnchorId(pageNumber: number, elementIndex: number): string {
  return `doc-heading-${pageNumber}-${elementIndex}`;
}

export function extractTocItems(bundle: BundleRaw): ReaderTocItem[] {
  const items: ReaderTocItem[] = [];
  for (const page of bundle.pages) {
    page.elements.forEach((el, index) => {
      if (el.type !== "heading") return;
      const text = (el.text || "").trim();
      if (!text) return;
      items.push({
        id: headingAnchorId(page.page_number, index),
        text,
        level: Math.min(Math.max(el.heading_level ?? 1, 1), 6),
        pageNumber: page.page_number,
        elementIndex: index,
      });
    });
  }
  return items;
}

export function getPageNumbers(bundle: BundleRaw): number[] {
  return bundle.pages.map((page) => page.page_number).sort((a, b) => a - b);
}

export function clampPageNumber(pageNumber: number, pageNumbers: number[]): number {
  if (pageNumbers.length === 0) return 1;
  const min = pageNumbers[0];
  const max = pageNumbers[pageNumbers.length - 1];
  return Math.min(Math.max(pageNumber, min), max);
}

export function findNearestPageNumber(pageNumbers: number[], target: number): number {
  if (pageNumbers.length === 0) return 1;
  let nearest = pageNumbers[0];
  let bestDistance = Math.abs(target - nearest);
  for (const page of pageNumbers) {
    const distance = Math.abs(target - page);
    if (distance < bestDistance) {
      nearest = page;
      bestDistance = distance;
    }
  }
  return nearest;
}

export function getPreviousPageNumber(pageNumbers: number[], current: number): number | null {
  const index = pageNumbers.indexOf(current);
  if (index <= 0) return null;
  return pageNumbers[index - 1];
}

export function getNextPageNumber(pageNumbers: number[], current: number): number | null {
  const index = pageNumbers.indexOf(current);
  if (index < 0 || index >= pageNumbers.length - 1) return null;
  return pageNumbers[index + 1];
}

/** 从 evidence 原文中提取用于 DOM 高亮的 needle（优先完整匹配，过长则截断）。 */
export function buildHighlightNeedle(content: string, maxLength = 120): string {
  const trimmed = content.trim();
  if (!trimmed) return "";
  if (trimmed.length <= maxLength) return trimmed;
  return trimmed.slice(0, maxLength);
}

/** 在段落文本中查找 needle；若完整匹配失败，尝试较短前缀。 */
export function findHighlightIndex(text: string, needle: string): { start: number; length: number } | null {
  const source = text || "";
  const trimmed = needle.trim();
  if (!trimmed) return null;

  const direct = source.indexOf(trimmed);
  if (direct >= 0) return { start: direct, length: trimmed.length };

  for (let len = Math.min(trimmed.length, 80); len >= 12; len -= 4) {
    const partial = trimmed.slice(0, len);
    const idx = source.indexOf(partial);
    if (idx >= 0) return { start: idx, length: partial.length };
  }
  return null;
}

export function resolveActiveTocId(
  items: ReaderTocItem[],
  container: HTMLElement,
  offset = 72,
): string | null {
  if (items.length === 0) return null;
  const containerTop = container.getBoundingClientRect().top;
  const current = container.scrollTop + offset;

  const positions = items
    .map((item) => {
      const el = document.getElementById(item.id);
      if (!el) return null;
      const top = el.getBoundingClientRect().top - containerTop + container.scrollTop;
      return { id: item.id, top };
    })
    .filter((entry): entry is { id: string; top: number } => entry !== null)
    .sort((a, b) => a.top - b.top);

  if (positions.length === 0) return items[0]?.id ?? null;

  let active = positions[0].id;
  for (const pos of positions) {
    if (pos.top <= current) active = pos.id;
    else break;
  }
  return active;
}

export function resolveVisiblePageNumber(
  pageNumbers: number[],
  container: HTMLElement,
  offset = 96,
): number {
  if (pageNumbers.length === 0) return 1;
  const containerTop = container.getBoundingClientRect().top;
  const current = container.scrollTop + offset;
  let visible = pageNumbers[0];

  for (const pageNumber of pageNumbers) {
    const el = document.getElementById(pageAnchorId(pageNumber));
    if (!el) continue;
    const top = el.getBoundingClientRect().top - containerTop + container.scrollTop;
    if (top <= current) visible = pageNumber;
    else break;
  }
  return visible;
}
