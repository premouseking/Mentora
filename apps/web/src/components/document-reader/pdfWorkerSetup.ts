/**
 * pdf.js Worker 初始化。
 *
 * 约定：使用 legacy build，兼容 Vite ?url worker 导入。
 */
import * as pdfjsLib from "pdfjs-dist/legacy/build/pdf.mjs";
import PdfWorkerUrl from "pdfjs-dist/legacy/build/pdf.worker.min.mjs?url";

pdfjsLib.GlobalWorkerOptions.workerSrc = PdfWorkerUrl;

export const sharedPdfWorker = new pdfjsLib.PDFWorker();
export const workerSrcReady: Promise<void> = Promise.resolve();

export { pdfjsLib };
