"""
解析基准测试运行器。

约定：
- 使用 tests/fixtures/ 下的 PDF 文件作为基准数据集
- 每条命令可重跑：python -m mentora.parsing.benchmark
- 报告区分产品暂不支持与解析器缺陷

约束：
- 纯图片 PDF 明确延期，不静默当作成功
- benchmark 输出包含处理耗时和内存峰值

@module mentora.parsing.benchmark
"""

import os
import time
import tracemalloc
from dataclasses import dataclass, field

from mentora.parsing.adapters import parse
from mentora.parsing.adapters.exceptions import ParsingError
from mentora.parsing.evidence import split_evidence
from mentora.parsing.schemas import ParsedBundle, EvidenceUnit


@dataclass
class FixtureResult:
    """单个 Fixture 的基准测试结果。"""
    name: str
    path: str
    status: str  # "ok" | "skipped" | "error"
    error_type: str | None = None
    error_message: str | None = None
    page_count: int = 0
    element_count: int = 0
    evidence_count: int = 0
    heading_count: int = 0
    paragraph_count: int = 0
    image_count: int = 0
    quality_score: float | None = None
    elapsed_ms: float = 0
    memory_kb_peak: float = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    """基准测试完整报告。"""
    parser_name: str
    parser_version: str
    fixtures: list[FixtureResult]
    generated_at: str

    @property
    def total_fixtures(self) -> int:
        return len(self.fixtures)

    @property
    def ok_count(self) -> int:
        return sum(1 for f in self.fixtures if f.status == "ok")

    @property
    def skipped_count(self) -> int:
        return sum(1 for f in self.fixtures if f.status == "skipped")

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.fixtures if f.status == "error")

    def to_dict(self) -> dict:
        return {
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "total_fixtures": self.total_fixtures,
            "ok_count": self.ok_count,
            "skipped_count": self.skipped_count,
            "error_count": self.error_count,
            "fixtures": [
                {
                    "name": f.name,
                    "status": f.status,
                    "error_type": f.error_type,
                    "error_message": f.error_message,
                    "page_count": f.page_count,
                    "element_count": f.element_count,
                    "evidence_count": f.evidence_count,
                    "heading_count": f.heading_count,
                    "paragraph_count": f.paragraph_count,
                    "image_count": f.image_count,
                    "quality_score": f.quality_score,
                    "elapsed_ms": f.elapsed_ms,
                    "memory_kb_peak": f.memory_kb_peak,
                    "warnings": f.warnings,
                }
                for f in self.fixtures
            ],
            "generated_at": self.generated_at,
        }


def run_benchmark(
    fixtures_dir: str,
    parser_version: str = "1.0.0",
) -> BenchmarkReport:
    """
    遍历 fixtures_dir 下所有 .pdf 文件，逐一解析并收集指标。

    纯图片 PDF 标记为 skipped（产品暂不支持），不标记为 error。
    加密/损坏 PDF 标记为 error。
    """
    results: list[FixtureResult] = []

    for filename in sorted(os.listdir(fixtures_dir)):
        if not filename.endswith(".pdf"):
            continue

        filepath = os.path.join(fixtures_dir, filename)
        result = FixtureResult(name=filename, path=filepath, status="ok")

        tracemalloc.start()
        t0 = time.perf_counter()

        try:
            bundle = parse(filepath, parser_version)

            # 统计元素类型
            headings = 0
            paragraphs = 0
            images = 0
            for page in bundle.pages:
                for elem in page.elements:
                    if elem.type.value == "heading":
                        headings += 1
                    elif elem.type.value == "paragraph":
                        paragraphs += 1
                    elif elem.type.value == "image":
                        images += 1

            evidence_units = split_evidence(bundle)

            result.page_count = bundle.page_count
            result.element_count = bundle.element_count
            result.evidence_count = len(evidence_units)
            result.heading_count = headings
            result.paragraph_count = paragraphs
            result.image_count = images
            result.quality_score = bundle.quality.score
            result.warnings = bundle.warnings

        except ParsingError as exc:
            exc_type = type(exc).__name__
            # 纯图片 PDF → 产品暂不支持，标记为 skipped
            if "ImageOnly" in exc_type:
                result.status = "skipped"
                result.error_type = exc_type
                result.error_message = str(exc)
            else:
                result.status = "error"
                result.error_type = exc_type
                result.error_message = str(exc)

        finally:
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            result.elapsed_ms = (time.perf_counter() - t0) * 1000
            result.memory_kb_peak = peak / 1024

        results.append(result)

    return BenchmarkReport(
        parser_name="pymupdf",
        parser_version=parser_version,
        fixtures=results,
        generated_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
