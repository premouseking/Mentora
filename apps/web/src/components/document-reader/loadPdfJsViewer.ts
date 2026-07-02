/**
 * 延迟加载 pdf.js viewer，确保 pdf.mjs 先完成并写入 globalThis.pdfjsLib。
 *
 * 约束：禁止在 pdfWorkerSetup 之前静态 import pdf_viewer.mjs。
 */
import { pdfjsLib, workerSrcReady } from "./pdfWorkerSetup";

export type PdfJsViewerModule = typeof import("pdfjs-dist/legacy/web/pdf_viewer.mjs");

let viewerModulePromise: Promise<PdfJsViewerModule> | null = null;

const RANGE_CHUNK_SIZE = 65536;
const rangeSupportCache = new Map<string, boolean>();

export async function loadPdfJsViewer(): Promise<PdfJsViewerModule> {
  if (!viewerModulePromise) {
    viewerModulePromise = import("pdfjs-dist/legacy/web/pdf_viewer.mjs");
  }
  return viewerModulePromise;
}

export type PdfLoadProgress = {
  phase: "download" | "parse";
  loaded: number;
  total: number | null;
};

export class PdfLoadAbortedError extends Error {
  constructor(message = "PDF 加载已取消") {
    super(message);
    this.name = "PdfLoadAbortedError";
  }
}

const pdfBytesCache = new Map<string, Promise<ArrayBuffer>>();

/** 阅读器卸载时释放 PDF 二进制缓存，避免多开资料后 ArrayBuffer 滞留。 */
export function evictPdfBytesCache(urls: string[]): void {
  for (const url of urls) {
    if (url) pdfBytesCache.delete(url);
  }
}

async function probeRangeSupport(url: string, signal?: AbortSignal): Promise<boolean> {
  const cached = rangeSupportCache.get(url);
  if (cached !== undefined) return cached;

  try {
    const response = await fetch(url, {
      method: "HEAD",
      signal,
    });
    const supported = response.ok && response.headers.get("accept-ranges") === "bytes";
    rangeSupportCache.set(url, supported);
    return supported;
  } catch {
    rangeSupportCache.set(url, false);
    return false;
  }
}

async function readResponseWithProgress(
  response: Response,
  onProgress?: (progress: PdfLoadProgress) => void,
  signal?: AbortSignal,
): Promise<ArrayBuffer> {
  if (signal?.aborted) {
    throw new PdfLoadAbortedError();
  }

  const totalHeader = response.headers.get("content-length");
  const total = totalHeader ? Number.parseInt(totalHeader, 10) : null;

  const buffer = await response.arrayBuffer();
  if (signal?.aborted) {
    throw new PdfLoadAbortedError();
  }

  onProgress?.({
    phase: "download",
    loaded: buffer.byteLength,
    total: Number.isFinite(total) && total! > 0 ? total : buffer.byteLength,
  });
  return buffer;
}

async function fetchPdfBytes(
  url: string,
  onProgress?: (progress: PdfLoadProgress) => void,
  signal?: AbortSignal,
): Promise<ArrayBuffer> {
  const cached = pdfBytesCache.get(url);
  if (cached) {
    const buffer = await cached;
    onProgress?.({
      phase: "download",
      loaded: buffer.byteLength,
      total: buffer.byteLength,
    });
    return buffer;
  }

  const task = (async () => {
    const response = await fetch(url, { signal });
    if (!response.ok) {
      throw new Error(`PDF 请求失败 (${response.status})`);
    }
    return readResponseWithProgress(response, undefined, signal);
  })();

  pdfBytesCache.set(url, task);
  try {
    const buffer = await task;
    onProgress?.({
      phase: "download",
      loaded: buffer.byteLength,
      total: buffer.byteLength,
    });
    return buffer;
  } catch (error) {
    pdfBytesCache.delete(url);
    if (signal?.aborted) {
      throw new PdfLoadAbortedError();
    }
    throw error;
  }
}

async function loadPdfDocumentFromBuffer(
  buffer: ArrayBuffer,
  onProgress?: (progress: PdfLoadProgress) => void,
): Promise<Awaited<ReturnType<typeof pdfjsLib.getDocument>>["promise"]> {
  const task = pdfjsLib.getDocument({ data: buffer, useSystemFonts: true });
  task.onProgress = (progress: { loaded: number; total: number }) => {
    onProgress?.({
      phase: "parse",
      loaded: progress.loaded,
      total: progress.total > 0 ? progress.total : null,
    });
  };
  return task.promise;
}

async function loadPdfDocumentFromUrl(
  url: string,
  onProgress?: (progress: PdfLoadProgress) => void,
  signal?: AbortSignal,
): Promise<Awaited<ReturnType<typeof pdfjsLib.getDocument>>["promise"]> {
  const task = pdfjsLib.getDocument({
    url,
    rangeChunkSize: RANGE_CHUNK_SIZE,
    useSystemFonts: true,
    disableStream: false,
    disableAutoFetch: false,
  });
  task.onProgress = (progress: { loaded: number; total: number }) => {
    if (signal?.aborted) {
      task.destroy();
      return;
    }
    onProgress?.({
      phase: progress.total > 0 && progress.loaded >= progress.total ? "parse" : "download",
      loaded: progress.loaded,
      total: progress.total > 0 ? progress.total : null,
    });
  };
  return task.promise;
}

/** 优先 Range 分片 URL 加载，失败时回退整文件 ArrayBuffer。 */
export async function loadPdfDocumentFromUrls(
  urls: string[],
  onProgress?: (progress: PdfLoadProgress) => void,
  signal?: AbortSignal,
): Promise<Awaited<ReturnType<typeof pdfjsLib.getDocument>>["promise"]> {
  await workerSrcReady;

  let lastError: unknown = null;
  for (const url of urls) {
    if (!url) continue;
    try {
      if (signal?.aborted) {
        throw new PdfLoadAbortedError();
      }

      const rangeSupported = await probeRangeSupport(url, signal);
      if (rangeSupported) {
        onProgress?.({ phase: "download", loaded: 0, total: null });
        return await loadPdfDocumentFromUrl(url, onProgress, signal);
      }

      const buffer = await fetchPdfBytes(url, onProgress, signal);
      if (buffer.byteLength < 5) {
        throw new Error("PDF 响应为空");
      }
      const header = new TextDecoder().decode(new Uint8Array(buffer.slice(0, 5)));
      if (!header.startsWith("%PDF")) {
        throw new Error("响应内容不是 PDF 文件");
      }
      return await loadPdfDocumentFromBuffer(buffer, onProgress);
    } catch (error) {
      if (signal?.aborted || error instanceof PdfLoadAbortedError) {
        throw error;
      }
      lastError = error;
    }
  }

  throw lastError instanceof Error ? lastError : new Error("PDF 加载失败");
}

export { pdfjsLib, workerSrcReady } from "./pdfWorkerSetup";
