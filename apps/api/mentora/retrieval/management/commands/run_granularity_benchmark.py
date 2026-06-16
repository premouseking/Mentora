"""Django management command：三粒度检索对比基准。"""

import json

from django.core.management.base import BaseCommand

from mentora.retrieval.benchmark_compare import run


class Command(BaseCommand):
    help = "对比 EvidenceUnit / ChunkProjection / SentenceProjection 三种粒度的检索精度"

    def handle(self, **options):
        self.stdout.write("运行三粒度检索对比基准…")
        report = run()
        self.stdout.write(json.dumps(report, indent=2, ensure_ascii=False))

        s = report["summary"]
        c = report["counts"]
        self.stdout.write(self.style.SUCCESS(
            f"\nEvidence({c['evidence_count']}): P@5={s['EvidenceUnit_avg_P@5']} "
            f"P@10={s['EvidenceUnit_avg_P@10']} Recall={s['EvidenceUnit_avg_Recall']}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Chunk({c['chunk_count']}): P@5={s['ChunkProjection_avg_P@5']} "
            f"P@10={s['ChunkProjection_avg_P@10']} Recall={s['ChunkProjection_avg_Recall']}"
        ))
        self.stdout.write(self.style.SUCCESS(
            f"Sentence({c['sentence_count']}): P@5={s['SentenceProjection_avg_P@5']} "
            f"P@10={s['SentenceProjection_avg_P@10']} Recall={s['SentenceProjection_avg_Recall']}"
        ))
