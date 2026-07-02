/**
 * ResourceReader facade：PDF 始终原文渲染；ParsedBundle DOM 仅用于非 PDF。
 */
import { useCallback, useMemo, useState } from "react";

import { buildSourceOriginalAssetUrl } from "../../services/documentApi";
import { buildResourcePdfUrl } from "../../services/resourceApi";
import {
  isPdfResource,
  isResourceReady,
  resourceIdFromSourceVersion,
} from "../../services/resourceTypes";
import {
  useNonPdfSourceDetail,
  useResourceReaderDocument,
} from "../../hooks/useResourceReaderQuery";
import { DocumentReaderShell } from "./DocumentReaderShell";
import { PdfJsDocumentReader } from "./PdfJsDocumentReader";
import { ReaderLoadingProgress } from "./ReaderLoadingProgress";
import { resolveFetchStageProgress } from "./readerLoadingUtils";
import { PDF_LOAD_ERROR_MESSAGE } from "./resourceReaderUtils";
import type { EvidenceHighlight } from "./types";

interface ResourceReaderProps {
  resourceId?: string;
  sourceVersionId?: string;
  evidenceHighlight?: EvidenceHighlight | null;
  onClearEvidenceHighlight?: () => void;
  layoutRefreshKey?: number;
}

export function ResourceReader({
  resourceId,
  sourceVersionId,
  evidenceHighlight,
  onClearEvidenceHighlight,
  layoutRefreshKey = 0,
}: ResourceReaderProps) {
  const resolvedId = resourceId ?? (sourceVersionId ? resourceIdFromSourceVersion(sourceVersionId) : "");
  const [pdfLoadError, setPdfLoadError] = useState("");

  const { readerDoc, loading, fetchStage, error } = useResourceReaderDocument(resolvedId || undefined);

  const usePdf = useMemo(() => {
    if (!readerDoc) return false;
    return isPdfResource(readerDoc.resource);
  }, [readerDoc]);

  const nonPdfQuery = useNonPdfSourceDetail(
    resolvedId || undefined,
    Boolean(readerDoc && !usePdf),
  );

  const handlePdfLoadError = useCallback((message: string) => {
    setPdfLoadError(message || PDF_LOAD_ERROR_MESSAGE);
  }, []);

  if (!resolvedId) {
    return <p className="cw-preview-text reader-shell-message">缺少资源 ID</p>;
  }

  if (loading) {
    const fetchProgress = resolveFetchStageProgress(fetchStage);
    return (
      <div className="document-reader-shell reader-loading-shell">
        <ReaderLoadingProgress
          progress={fetchProgress.progress}
          label={fetchProgress.label}
          indeterminate={fetchProgress.indeterminate}
        />
      </div>
    );
  }

  if (error) {
    return <p className="cw-preview-text reader-shell-message">{error}</p>;
  }

  if (readerDoc && !isResourceReady(readerDoc.resource.processing_status)) {
    return <p className="cw-preview-text reader-shell-message">资料尚未完成解析，解析完成后可预览。</p>;
  }

  if (readerDoc && usePdf) {
    if (pdfLoadError) {
      return <p className="cw-preview-text reader-shell-message">{pdfLoadError}</p>;
    }

    const pdfUrl = readerDoc.pdf_url.startsWith("/")
      ? readerDoc.pdf_url
      : buildResourcePdfUrl(resolvedId);
    const pdfFallbackUrl = buildSourceOriginalAssetUrl(resolvedId);
    const title = readerDoc.resource.resource_name;

    return (
      <PdfJsDocumentReader
        key={resolvedId}
        title={title}
        pdfUrl={pdfUrl}
        pdfFallbackUrl={pdfFallbackUrl}
        readerDoc={readerDoc}
        resourceId={resolvedId}
        evidenceHighlight={evidenceHighlight}
        onClearEvidenceHighlight={onClearEvidenceHighlight}
        onLoadError={handlePdfLoadError}
        layoutRefreshKey={layoutRefreshKey}
      />
    );
  }

  if (readerDoc && !usePdf && nonPdfQuery.isLoading) {
    const fetchProgress = resolveFetchStageProgress("bundle");
    return (
      <div className="document-reader-shell reader-loading-shell">
        <ReaderLoadingProgress
          progress={fetchProgress.progress}
          label={fetchProgress.label}
          indeterminate={fetchProgress.indeterminate}
        />
      </div>
    );
  }

  if (readerDoc && !usePdf && nonPdfQuery.data?.bundle) {
    const title =
      nonPdfQuery.data.source.displayTitle
      || nonPdfQuery.data.version.originalFilename
      || readerDoc.resource.resource_name
      || "资料预览";
    return (
      <DocumentReaderShell
        title={title}
        bundle={nonPdfQuery.data.bundle}
        loading={nonPdfQuery.isLoading}
        error=""
        evidenceHighlight={evidenceHighlight}
        onClearEvidenceHighlight={onClearEvidenceHighlight}
        sourceVersionId={resolvedId}
      />
    );
  }

  return <p className="cw-preview-text reader-shell-message">无法加载文档内容。</p>;
}

export { normalizeReaderDocument } from "../../services/resourceApi";
