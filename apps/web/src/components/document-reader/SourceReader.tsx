/** 统一资料阅读器 facade（兼容 sourceVersionId → resourceId）。 */
import { ResourceReader } from "./ResourceReader";
import type { EvidenceHighlight } from "./types";

export function SourceReader({
  sourceVersionId,
  resourceId,
  evidenceHighlight,
  onClearEvidenceHighlight,
  layoutRefreshKey,
}: {
  sourceVersionId?: string;
  resourceId?: string;
  evidenceHighlight?: EvidenceHighlight | null;
  onClearEvidenceHighlight?: () => void;
  layoutRefreshKey?: number;
}) {
  return (
    <ResourceReader
      resourceId={resourceId}
      sourceVersionId={sourceVersionId}
      evidenceHighlight={evidenceHighlight}
      onClearEvidenceHighlight={onClearEvidenceHighlight}
      layoutRefreshKey={layoutRefreshKey}
    />
  );
}
