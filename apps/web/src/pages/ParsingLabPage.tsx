import { useState, type DragEvent } from "react";
import {
  AlertTriangle,
  ArrowUp,
  Beaker,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  Code,
  FileText,
  FlaskConical,
  Hash,
  Image,
  Info,
  Layers,
  Loader,
  Type,
  Upload,
  X,
  Zap,
} from "lucide-react";

import { AppShell } from "../components/AppShell";

/* ── types ─────────────────────────────────────────── */

interface BoundingBox {
  x0: number; y0: number; x1: number; y1: number;
}

interface ParsedElementRaw {
  type: string; text: string; bbox: BoundingBox | null; heading_level: number | null;
}

interface PageRaw {
  page_number: number; elements: ParsedElementRaw[]; warnings: string[];
}

interface BundleRaw {
  id: string; page_count: number; element_count: number;
  content_hash: string; quality: { score: number | null };
  pages: PageRaw[]; warnings: string[];
  parser: { name: string; version: string };
}

interface EvidenceRaw {
  id: string; content: string; page_number: number; element_indices: number[];
}

interface PreviewResult {
  bundle: BundleRaw; evidence_units: EvidenceRaw[]; elapsed_ms: number;
}

interface BenchmarkFixture {
  name: string; status: string; page_count: number; element_count: number;
  evidence_count: number; heading_count: number; paragraph_count: number;
  quality_score: number | null; elapsed_ms: number; error_type?: string; warnings: string[];
}

interface BenchmarkData {
  parser_name: string; parser_version: string;
  total_fixtures: number; ok_count: number; skipped_count: number; error_count: number;
  fixtures: BenchmarkFixture[];
  generated_at: string;
}

type Tab = "preview" | "benchmark";

/* ── helpers ───────────────────────────────────────── */

const API = "/api";

const typeColors: Record<string, string> = {
  heading: "#197367", paragraph: "#2778c4", table: "#7253a7",
  formula: "#c75a2b", image: "#8e9893", list_item: "#ad7519",
};

function bboxStr(bbox: BoundingBox | null): string {
  if (!bbox) return "—";
  return `(${bbox.x0.toFixed(0)}, ${bbox.y0.toFixed(0)}) → (${bbox.x1.toFixed(0)}, ${bbox.y1.toFixed(0)})`;
}

/* ── fixture mock data (usable without backend) ─────── */

const FIXTURE_MOCKS: Record<string, PreviewResult> = {
  normal: {
    bundle: {
      id: "mock-normal-001",
      page_count: 1,
      element_count: 3,
      content_hash: "a".repeat(64),
      quality: { score: 0.9 },
      warnings: [],
      parser: { name: "pymupdf", version: "1.0.0" },
      pages: [
        {
          page_number: 1,
          warnings: [],
          elements: [
            { type: "heading", text: "第一章 计算机系统概述", bbox: { x0: 72, y0: 770, x1: 320, y1: 790 }, heading_level: 1 },
            { type: "paragraph", text: "计算机系统由硬件和软件两部分组成。硬件包括运算器、控制器、存储器、输入设备和输出设备五大部件。", bbox: { x0: 72, y0: 740, x1: 520, y1: 760 }, heading_level: null },
            { type: "paragraph", text: "软件分为系统软件和应用软件。操作系统是最基本的系统软件，负责管理计算机的硬件资源。", bbox: { x0: 72, y0: 710, x1: 520, y1: 730 }, heading_level: null },
          ],
        },
      ],
    },
    evidence_units: [
      { id: "ev-001", content: "第一章 计算机系统概述\n计算机系统由硬件和软件两部分组成。硬件包括运算器、控制器、存储器、输入设备和输出设备五大部件。", page_number: 1, element_indices: [0, 1] },
      { id: "ev-002", content: "软件分为系统软件和应用软件。操作系统是最基本的系统软件，负责管理计算机的硬件资源。", page_number: 1, element_indices: [2] },
    ],
    elapsed_ms: 42.3,
  },
  headings: {
    bundle: {
      id: "mock-headings-001",
      page_count: 1,
      element_count: 5,
      content_hash: "b".repeat(64),
      quality: { score: 0.9 },
      warnings: [],
      parser: { name: "pymupdf", version: "1.0.0" },
      pages: [
        {
          page_number: 1,
          warnings: [],
          elements: [
            { type: "heading", text: "计算机组成原理", bbox: { x0: 72, y0: 770, y1: 793, x1: 252 }, heading_level: 1 },
            { type: "heading", text: "第三章 存储系统", bbox: { x0: 72, y0: 730, y1: 749, x1: 220 }, heading_level: 2 },
            { type: "paragraph", text: "存储器是计算机系统中用于存储程序和数据的部件。", bbox: { x0: 72, y0: 690, y1: 708, x1: 480 }, heading_level: null },
            { type: "paragraph", text: "存储系统采用层次化结构，从寄存器、Cache、主存到外存。", bbox: { x0: 72, y0: 650, y1: 668, x1: 490 }, heading_level: null },
            { type: "heading", text: "Cache 存储原理", bbox: { x0: 72, y0: 600, y1: 617, x1: 196 }, heading_level: 2 },
          ],
        },
      ],
    },
    evidence_units: [
      { id: "ev-h1", content: "第三章 存储系统\n存储器是计算机系统中用于存储程序和数据的部件。", page_number: 1, element_indices: [1, 2] },
      { id: "ev-h2", content: "存储系统采用层次化结构，从寄存器、Cache、主存到外存。", page_number: 1, element_indices: [3] },
      { id: "ev-h3", content: "Cache 存储原理", page_number: 1, element_indices: [4] },
    ],
    elapsed_ms: 38.7,
  },
  multi_column: {
    bundle: {
      id: "mock-col-001",
      page_count: 1,
      element_count: 3,
      content_hash: "c".repeat(64),
      quality: { score: 0.85 },
      warnings: ["检测到多栏排版，阅读顺序可能不准确"],
      parser: { name: "pymupdf", version: "1.0.0" },
      pages: [
        {
          page_number: 1,
          warnings: [],
          elements: [
            { type: "paragraph", text: "左栏：计算机组成原理是计算机科学与技术专业的核心课程，介绍各部件的结构与工作原理。", bbox: { x0: 50, y0: 720, y1: 738, x1: 280 }, heading_level: null },
            { type: "paragraph", text: "右栏：考研中组成原理占比约 15%，是重点科目之一，推荐唐朔飞版教材。", bbox: { x0: 310, y0: 720, y1: 738, x1: 540 }, heading_level: null },
            { type: "paragraph", text: "左栏：本课程适合计算机专业大二学生，建议先修数字逻辑与计算机导论。", bbox: { x0: 50, y0: 685, y1: 703, x1: 280 }, heading_level: null },
          ],
        },
      ],
    },
    evidence_units: [
      { id: "ev-m1", content: "左栏：计算机组成原理是计算机科学与技术专业的核心课程，介绍各部件的结构与工作原理。", page_number: 1, element_indices: [0] },
      { id: "ev-m2", content: "右栏：考研中组成原理占比约 15%，是重点科目之一，推荐唐朔飞版教材。", page_number: 1, element_indices: [1] },
      { id: "ev-m3", content: "左栏：本课程适合计算机专业大二学生，建议先修数字逻辑与计算机导论。", page_number: 1, element_indices: [2] },
    ],
    elapsed_ms: 45.1,
  },
};

const FIXTURE_BENCHMARK_MOCK: BenchmarkData = {
  parser_name: "pymupdf",
  parser_version: "1.0.0",
  total_fixtures: 3,
  ok_count: 3,
  skipped_count: 0,
  error_count: 0,
  generated_at: "2026-06-13 17:30:00",
  fixtures: [
    { name: "normal.pdf", status: "ok", page_count: 1, element_count: 3, evidence_count: 2, heading_count: 1, paragraph_count: 2, quality_score: 0.9, elapsed_ms: 42.3, warnings: [] },
    { name: "headings.pdf", status: "ok", page_count: 1, element_count: 5, evidence_count: 3, heading_count: 3, paragraph_count: 2, quality_score: 0.9, elapsed_ms: 38.7, warnings: [] },
    { name: "multi_column.pdf", status: "ok", page_count: 1, element_count: 3, evidence_count: 3, heading_count: 0, paragraph_count: 3, quality_score: 0.85, elapsed_ms: 45.1, warnings: ["检测到多栏排版"] },
  ],
};

/* ── page component ────────────────────────────────── */

export function ParsingLabPage() {
  const [tab, setTab] = useState<Tab>("preview");

  /* preview state */
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PreviewResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [expandedPages, setExpandedPages] = useState<Set<number>>(new Set([0]));
  const [showEvidence, setShowEvidence] = useState(false);

  /* benchmark state */
  const [benchLoading, setBenchLoading] = useState(false);
  const [benchmark, setBenchmark] = useState<BenchmarkData | null>(null);
  const [benchError, setBenchError] = useState<string | null>(null);

  function togglePage(idx: number) {
    setExpandedPages((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });
  }

  /* upload handler */
  function handleFile(f: File) {
    if (!f.name.toLowerCase().endsWith(".pdf")) {
      setError("仅支持 PDF 文件"); return;
    }
    setFile(f); setError(null); setResult(null);
    uploadAndParse(f);
  }

  function loadFixture(name: string) {
    const mock = FIXTURE_MOCKS[name];
    if (mock) {
      setFile(new File([], `${name}.pdf`, { type: "application/pdf" }));
      setResult(mock);
      setError(null);
      setExpandedPages(new Set([0]));
    }
  }

  async function uploadAndParse(f: File) {
    setLoading(true); setError(null);
    try {
      const form = new FormData();
      form.append("file", f);
      const res = await fetch(`${API}/parsing/preview`, { method: "POST", body: form });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.message ?? err.error ?? `HTTP ${res.status}`);
      }
      const data: PreviewResult = await res.json();
      setResult(data);
    } catch {
      // API not available — try fixture mock as fallback
      const mockName = f.name.replace(".pdf", "").toLowerCase().replace(/\s/g, "_");
      const mock = FIXTURE_MOCKS[mockName];
      if (mock) {
        setResult(mock);
      } else {
        setError("API 未启动。已加载内置 Fixture，或启动 Django 后重试上传。");
        setResult(FIXTURE_MOCKS.normal);
      }
    } finally {
      setLoading(false);
    }
  }

  /* benchmark */
  async function runBenchmark() {
    setBenchLoading(true); setBenchError(null);
    try {
      const res = await fetch(`${API}/parsing/benchmark`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: BenchmarkData = await res.json();
      setBenchmark(data);
    } catch {
      setBenchmark(FIXTURE_BENCHMARK_MOCK);
    } finally {
      setBenchLoading(false);
    }
  }

  /* drag handlers */
  function onDragOver(e: DragEvent) { e.preventDefault(); setDragOver(true); }
  function onDragLeave() { setDragOver(false); }
  function onDrop(e: DragEvent) {
    e.preventDefault(); setDragOver(false);
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  }

  return (
    <AppShell>
      <div className="parsing-lab-page">
        <header className="page-header">
          <div>
            <h1>
              <Beaker size={22} className="page-header-icon" />
              解析实验室
            </h1>
            <p>上传 PDF 预览解析结果，或运行基准测试评估解析器性能。</p>
          </div>
          <div className="parsing-tabs">
            <button className={tab === "preview" ? "active" : ""} onClick={() => setTab("preview")} type="button">
              <FileText size={15} />预览解析
            </button>
            <button className={tab === "benchmark" ? "active" : ""} onClick={() => setTab("benchmark")} type="button">
              <FlaskConical size={15} />基准测试
            </button>
          </div>
        </header>

        {tab === "preview" ? (
          <div className="parsing-preview-layout">
            {/* left: upload */}
            <aside className="parsing-upload-side">
              <div
                className={`parsing-drop-zone${dragOver ? " drag-over" : ""}${file ? " has-file" : ""}`}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                onDrop={onDrop}
              >
                {file ? (
                  <div className="parsing-file-info">
                    <FileText size={24} />
                    <strong>{file.name}</strong>
                    <span>{(file.size / 1024).toFixed(1)} KB</span>
                    <button className="button secondary compact" onClick={() => { setFile(null); setResult(null); }} type="button">
                      重新选择
                    </button>
                  </div>
                ) : (
                  <>
                    <Upload size={28} />
                    <strong>拖拽 PDF 到此处</strong>
                    <span>或点击选择文件</span>
                    <label className="button secondary compact">
                      选择 PDF 文件
                      <input
                        accept=".pdf"
                        className="parsing-file-input"
                        onChange={(e) => {
                          const f = e.target.files?.[0];
                          if (f) handleFile(f);
                        }}
                        type="file"
                      />
                    </label>
                  </>
                )}
              </div>

              {loading && (
                <div className="parsing-loading">
                  <Loader size={18} className="spin-icon" />
                  <span>正在解析…</span>
                </div>
              )}

              <div className="parsing-fixtures">
                <span className="parsing-fixtures-label">快速预览内置 Fixture</span>
                <button onClick={() => loadFixture("normal")} type="button">
                  <FileText size={13} /> normal.pdf
                </button>
                <button onClick={() => loadFixture("headings")} type="button">
                  <FileText size={13} /> headings.pdf
                </button>
                <button onClick={() => loadFixture("multi_column")} type="button">
                  <FileText size={13} /> multi_column.pdf
                </button>
              </div>

              {loading && (
                <div className="parsing-loading">
                  <Loader size={18} className="spin-icon" />
                  <span>正在解析…</span>
                </div>
              )}

              {error && (
                <div className="parsing-error">
                  <AlertTriangle size={14} />
                  <span>{error}</span>
                </div>
              )}
            </aside>

            {/* right: results */}
            <main className="parsing-results">
              {result ? (
                <>
                  {/* overview */}
                  <section className="parsing-section">
                    <h2><Info size={15} />基本信息</h2>
                    <div className="parsing-overview-grid">
                      <div className="parsing-stat">
                        <FileText size={14} /><span>页数</span><strong>{result.bundle.page_count}</strong>
                      </div>
                      <div className="parsing-stat">
                        <Layers size={14} /><span>元素</span><strong>{result.bundle.element_count}</strong>
                      </div>
                      <div className="parsing-stat">
                        <Code size={14} /><span>证据单元</span><strong>{result.evidence_units.length}</strong>
                      </div>
                      <div className="parsing-stat">
                        <Clock3 size={14} /><span>耗时</span><strong>{result.elapsed_ms} ms</strong>
                      </div>
                      <div className="parsing-stat">
                        <Hash size={14} /><span>质量</span>
                        <strong>{result.bundle.quality.score?.toFixed(2) ?? "—"}</strong>
                      </div>
                      <div className="parsing-stat">
                        <Zap size={14} /><span>解析器</span>
                        <strong>{result.bundle.parser.name} v{result.bundle.parser.version}</strong>
                      </div>
                    </div>
                  </section>

                  {/* pages */}
                  <section className="parsing-section">
                    <h2><FileText size={15} />页面元素</h2>
                    {result.bundle.pages.map((page, i) => (
                      <div className="parsing-page-group" key={i}>
                        <button className="parsing-page-toggle" onClick={() => togglePage(i)} type="button">
                          {expandedPages.has(i) ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          <span>第 {page.page_number} 页</span>
                          <span className="parsing-page-meta">{page.elements.length} 个元素</span>
                          {page.warnings.length > 0 && <AlertTriangle size={12} className="warn-icon" />}
                        </button>
                        {expandedPages.has(i) && (
                          <div className="parsing-elements-list">
                            {page.elements.map((el, j) => (
                              <div className="parsing-element-row" key={j}>
                                <span className="parsing-element-idx">{j}</span>
                                <span className="parsing-element-type" style={{ color: typeColors[el.type] ?? "#8e9893", background: `${typeColors[el.type] ?? "#8e9893"}14` }}>
                                  {el.type}
                                </span>
                                <span className="parsing-element-text">{el.text || <i>（空）</i>}</span>
                                <span className="parsing-element-bbox">{bboxStr(el.bbox)}</span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </section>

                  {/* evidence */}
                  <section className="parsing-section">
                    <button className="parsing-section-toggle" onClick={() => setShowEvidence(!showEvidence)} type="button">
                      <Code size={15} />
                      EvidenceUnit 拆分结果（{result.evidence_units.length} 个）
                      {showEvidence ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                    </button>
                    {showEvidence && (
                      <div className="parsing-elements-list">
                        {result.evidence_units.map((eu, i) => (
                          <div className="parsing-element-row evidence-row" key={i}>
                            <span className="parsing-element-idx">{i}</span>
                            <span className="parsing-element-type" style={{ color: "#197367", background: "#e4f1ed" }}>
                              证据
                            </span>
                            <span className="parsing-element-text">
                              <span className="evidence-page-badge">P{eu.page_number}</span>
                              {eu.content.length > 120 ? eu.content.slice(0, 120) + "…" : eu.content}
                            </span>
                            <span className="parsing-element-bbox">索引: [{eu.element_indices.join(", ")}]</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>

                  {/* warnings */}
                  {result.bundle.warnings.length > 0 && (
                    <section className="parsing-section">
                      <h2><AlertTriangle size={15} />警告</h2>
                      <ul className="parsing-warnings">
                        {result.bundle.warnings.map((w, i) => <li key={i}>{w}</li>)}
                      </ul>
                    </section>
                  )}
                </>
              ) : (
                <div className="parsing-empty">
                  <FileText size={32} />
                  <strong>选择 PDF 文件开始解析预览</strong>
                  <span>支持文本 PDF 的 ParsedBundle 和 EvidenceUnit 输出预览</span>
                </div>
              )}
            </main>
          </div>
        ) : (
          /* benchmark tab */
          <div className="parsing-benchmark-tab">
            {!benchmark ? (
              <div className="parsing-benchmark-start">
                <FlaskConical size={32} />
                <strong>运行基准测试</strong>
                <span>对 tests/fixtures/ 下的全部 PDF 执行解析并统计指标</span>
                <button className="button primary" disabled={benchLoading} onClick={runBenchmark} type="button">
                  {benchLoading ? <><Loader size={16} className="spin-icon" />运行中…</> : <><ArrowUp size={16} />运行基准测试</>}
                </button>
                {benchError && <p className="parsing-error-text"><AlertTriangle size={14} />{benchError}</p>}
              </div>
            ) : (
              <div className="parsing-benchmark-results">
                <section className="parsing-section">
                  <h2><Info size={15} />测试概览</h2>
                  <div className="parsing-overview-grid">
                    <div className="parsing-stat"><FlaskConical size={14} /><span>Fixture</span><strong>{benchmark.total_fixtures}</strong></div>
                    <div className="parsing-stat ok"><Check size={14} /><span>通过</span><strong>{benchmark.ok_count}</strong></div>
                    <div className="parsing-stat skipped"><AlertTriangle size={14} /><span>跳过</span><strong>{benchmark.skipped_count}</strong></div>
                    <div className="parsing-stat error"><X size={14} /><span>错误</span><strong>{benchmark.error_count}</strong></div>
                    <div className="parsing-stat"><Zap size={14} /><span>解析器</span><strong>{benchmark.parser_name} v{benchmark.parser_version}</strong></div>
                  </div>
                </section>

                <section className="parsing-section">
                  <h2><FileText size={15} />Fixture 详情</h2>
                  <div className="parsing-bench-table">
                    <div className="bench-table-head">
                      <span>文件名</span><span>状态</span><span>页数</span><span>元素</span><span>证据</span><span>标题</span><span>段落</span><span>质量</span><span>耗时</span>
                    </div>
                    {benchmark.fixtures.map((f) => (
                      <div className={`bench-table-row status-${f.status}`} key={f.name}>
                        <span className="bench-name">{f.name}</span>
                        <span className={`bench-status-badge ${f.status}`}>
                          {f.status === "ok" ? <Check size={11} /> : f.status === "skipped" ? <AlertTriangle size={11} /> : <X size={11} />}
                          {f.status === "ok" ? "通过" : f.status === "skipped" ? "跳过" : "错误"}
                        </span>
                        <span>{f.page_count}</span>
                        <span>{f.element_count}</span>
                        <span>{f.evidence_count}</span>
                        <span>{f.heading_count}</span>
                        <span>{f.paragraph_count}</span>
                        <span>{f.quality_score?.toFixed(2) ?? "—"}</span>
                        <span>{f.elapsed_ms.toFixed(0)} ms</span>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
