/** 阅读器可见页窗口：blocks 加载与 overlay 范围共用。 */

export const READER_PAGE_WINDOW_RADIUS = 2;

export function buildReaderPageWindow(
  centerPage: number,
  totalPages: number,
  radius = READER_PAGE_WINDOW_RADIUS,
): number[] {
  if (centerPage <= 0 || totalPages <= 0) return [];
  const minPage = Math.max(1, centerPage - radius);
  const maxPage = Math.min(totalPages, centerPage + radius);
  const pages: number[] = [];
  for (let page = minPage; page <= maxPage; page += 1) {
    pages.push(page);
  }
  return pages;
}
