"""Django 管理命令：向量搜索基准对比。"""

import json

from django.core.management.base import BaseCommand

from mentora.retrieval.benchmark_vector import run


class Command(BaseCommand):
    help = "对比两路(FTS+Trgm)与三路(FTS+Trgm+Vector)检索精度"

    def handle(self, **options):
        self.stdout.write("运行向量搜索基准对比…")
        report = run()

        self.stdout.write(f"语料: {report.corpus_size} 证据")
        self.stdout.write(f"Chunk: {report.chunk_count} 个")
        self.stdout.write(f"已 Embed: {report.chunk_embedded} 个")
        self.stdout.write("")

        s = report._summary()
        for mode, stats in s.items():
            self.stdout.write(self.style.SUCCESS(
                f"{mode}: P@5={stats['avg_p_at_5']} "
                f"P@10={stats['avg_p_at_10']} "
                f"Recall={stats['avg_recall']} "
                f"({stats['avg_ms']}ms)"
            ))

        self.stdout.write("")
        self.stdout.write(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
