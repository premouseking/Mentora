export interface EvidenceHighlight {
  evidenceId: string;
  sourceVersionId: string;
  pageNumber: number;
  content: string;
  bbox?: {
    x0: number;
    y0: number;
    x1: number;
    y1: number;
  } | null;
}

export interface ReaderTocItem {
  id: string;
  text: string;
  level: number;
  pageNumber: number;
  elementIndex: number;
}
