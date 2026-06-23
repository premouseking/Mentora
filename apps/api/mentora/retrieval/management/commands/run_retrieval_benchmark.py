"""Django management command：运行端到端检索基准。"""

import json

from django.core.management.base import BaseCommand

from mentora.retrieval.benchmark_runner import run
from mentora.retrieval.models import BenchmarkResult


class Command(BaseCommand):
    help = "解析 PDF Fixture、入库 EvidenceUnit、运行检索基准"

    def handle(self, **options):
        self.stdout.write("运行端到端检索基准…")
        report = run()
        data = report.to_dict()

        self.stdout.write(json.dumps(data, indent=2, ensure_ascii=False))

        summary = data["summary"]
        self.stdout.write(self.style.SUCCESS(
            f"\nP@5={summary['avg_p_at_5']}  P@10={summary['avg_p_at_10']}  "
            f"Recall={summary['avg_recall']}  corpus={report.corpus_size}"
        ))

        # 持久化
        BenchmarkResult.objects.create(
            name="runner",
            corpus_size=report.corpus_size,
            summary=summary,
            details=data.get("queries", []),
        )
        self.stdout.write("结果已持久化。")
