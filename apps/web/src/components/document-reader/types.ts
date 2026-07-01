export interface EvidenceHighlight {
  evidenceId: string;
  sourceVersionId: string;
  pageNumber: number;
  content: string;
}

export interface ReaderTocItem {
  id: string;
  text: string;
  level: number;
  pageNumber: number;
  elementIndex: number;
}
