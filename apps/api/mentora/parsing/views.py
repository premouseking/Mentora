"""解析预览和基准测试 API。"""

import os
import tempfile
import time

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema

from mentora.parsing.adapters import parse
from mentora.parsing.adapters.exceptions import ParsingError
from mentora.parsing.benchmark import run_benchmark
from mentora.parsing.evidence import split_evidence


@csrf_exempt
@extend_schema(summary="Preview Parse")
def preview_parse(request):
    """
    POST /api/parsing/preview

    上传一个 PDF 文件，返回 ParsedBundle 和 EvidenceUnit 列表。
    用于前端解析实验室页面预览解析效果。
    """
    if request.method != "POST":
        return JsonResponse({"error": "仅支持 POST"}, status=405)

    uploaded = request.FILES.get("file")
    if uploaded is None:
        return JsonResponse({"error": "缺少 file 字段"}, status=400)

    if not uploaded.name.lower().endswith(".pdf"):
        return JsonResponse({"error": "仅支持 PDF 文件"}, status=400)

    # 写入临时文件
    suffix = os.path.splitext(uploaded.name)[1]
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        for chunk in uploaded.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    try:
        t0 = time.perf_counter()
        bundle = parse(tmp_path, parser_version="1.0.0")
        elapsed_ms = (time.perf_counter() - t0) * 1000

        evidence_units = split_evidence(bundle)

        return JsonResponse({
            "bundle": bundle.model_dump(mode="json"),
            "evidence_units": [eu.model_dump(mode="json") for eu in evidence_units],
            "elapsed_ms": round(elapsed_ms, 1),
        })

    except ParsingError as exc:
        return JsonResponse({
            "error": type(exc).__name__,
            "message": str(exc),
        }, status=422)

    finally:
        os.unlink(tmp_path)


@extend_schema(summary="Get Benchmark")
def get_benchmark(request):
    """
    GET /api/parsing/benchmark

    运行基准测试并返回 JSON 报告。
    """
    fixtures_dir = os.path.join(
        os.path.dirname(__file__), "..", "..", "tests", "fixtures"
    )
    fixtures_dir = os.path.abspath(fixtures_dir)

    report = run_benchmark(fixtures_dir)
    return JsonResponse(report.to_dict())
