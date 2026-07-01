import { apiClient } from "./client";

export interface EvidenceLocation {
  evidence_id: string;
  page_number: number;
  bbox: Record<string, number> | null;
  content: string;
  context_before: string | null;
  context_after: string | null;
  sentences: Array<{ position_index: number; content: string }>;
}

export async function fetchEvidenceLocation(evidenceId: string): Promise<EvidenceLocation> {
  return apiClient.get<EvidenceLocation>(
    `/api/retrieval/evidence/${encodeURIComponent(evidenceId)}/location`,
  );
}
