import { parseRawJson, requestRaw, apiClient } from "./client";
import {
  normalizeParsingPreviewResult,
  type ParsingPreviewResult,
} from "./parsedBundleContract";

export interface BenchmarkFixture {
  name: string;
  status: string;
  page_count: number;
  element_count: number;
  evidence_count: number;
  heading_count: number;
  paragraph_count: number;
  quality_score: number | null;
  elapsed_ms: number;
  error_type?: string;
  warnings: string[];
}

export interface BenchmarkData {
  parser_name: string;
  parser_version: string;
  total_fixtures: number;
  ok_count: number;
  skipped_count: number;
  error_count: number;
  fixtures: BenchmarkFixture[];
  generated_at: string;
}

export async function previewParsing(file: File): Promise<ParsingPreviewResult> {
  const form = new FormData();
  form.append("file", file);
  const response = await requestRaw("POST", "/api/parsing/preview", { body: form });
  const data = await parseRawJson<unknown>(response);
  const preview = normalizeParsingPreviewResult(data);
  if (!preview) throw new Error("解析结果格式无效");
  return preview;
}

export function fetchParsingBenchmark(): Promise<BenchmarkData> {
  return apiClient.get<BenchmarkData>("/api/parsing/benchmark");
}
