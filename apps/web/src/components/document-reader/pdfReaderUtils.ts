import type { BoundingBox, ParsedElement } from "../../services/parsedBundleContract";

/** PDF 左下角坐标 → 页面 DOM 百分比定位（pdf.js 页面左上角原点）。 */
export function bboxToPercentStyle(
  bbox: BoundingBox,
  pageSize: [number, number],
): { left: string; top: string; width: string; height: string } {
  const [pageWidth, pageHeight] = pageSize;
  const left = (bbox.x0 / pageWidth) * 100;
  const top = ((pageHeight - bbox.y1) / pageHeight) * 100;
  const width = ((bbox.x1 - bbox.x0) / pageWidth) * 100;
  const height = ((bbox.y1 - bbox.y0) / pageHeight) * 100;
  return {
    left: `${left}%`,
    top: `${top}%`,
    width: `${width}%`,
    height: `${height}%`,
  };
}

const BLOCK_PRIORITY: Record<string, number> = {
  heading: 1,
  paragraph: 2,
  list_item: 2,
  formula: 3,
  table: 4,
  image: 5,
};

export function blockHitPriority(type: string): number {
  return BLOCK_PRIORITY[type] ?? 6;
}

export interface OutlineItem {
  id: string;
  title: string;
  pageNumber: number;
  level: number;
  children: OutlineItem[];
}

export function buildFallbackOutline(
  pages: Array<{ page_number: number; elements: ParsedElement[] }>,
): OutlineItem[] {
  const items: OutlineItem[] = [];
  for (const page of pages) {
    for (const [index, element] of page.elements.entries()) {
      if (element.type !== "heading" || !element.text.trim()) continue;
      items.push({
        id: `heading-${page.page_number}-${index}`,
        title: element.text.trim(),
        pageNumber: page.page_number,
        level: element.heading_level ?? 1,
        children: [],
      });
    }
  }
  return items;
}
