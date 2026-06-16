"""Django management command：运行端到端检索基准。"""

import json

from django.core.management.base import BaseCommand

from mentora.retrieval.benchmark_runner import run


class Command(BaseCommand):
    help = "解析 PDF Fixture、入库 EvidenceUnit、运行检索基准"

    def handle(self, **options):
        self.stdout.write("运行端到端检索基准…")
        report = run()
        self.stdout.write(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))

        summary = report.to_dict()["summary"]
        self.stdout.write(self.style.SUCCESS(
            f"\nP@5={summary['avg_p_at_5']}  P@10={summary['avg_p_at_10']}  "
            f"Recall={summary['avg_recall']}  corpus={report.corpus_size}"
        ))
