"""
回填检索索引：jieba 分词、Chunk/Sentence 投影、Embedding 向量。

用法：
  python manage.py backfill_retrieval_index
  python manage.py backfill_retrieval_index --source-version-id <uuid>
  python manage.py backfill_retrieval_index --sync-embed
"""

from __future__ import annotations

import jieba
from django.contrib.postgres.search import SearchVector
from django.core.management.base import BaseCommand

from mentora.knowledge.models import SourceVersion
from mentora.retrieval.index_builder import build_retrieval_projections, enqueue_embeddings
from mentora.retrieval.models import ChunkProjection, EvidenceUnit, SentenceProjection


class Command(BaseCommand):
    help = "回填 Evidence 检索字段与 Chunk/Sentence 投影，并生成 embedding"

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-version-id",
            dest="source_version_id",
            help="仅处理指定 SourceVersion",
        )
        parser.add_argument(
            "--sync-embed",
            action="store_true",
            help="同步调用 embedding API（不经过 Celery）",
        )

    def handle(self, *args, **options):
        sv_id = options.get("source_version_id")
        sync_embed = options["sync_embed"]

        qs = SourceVersion.objects.all().order_by("-created_at")
        if sv_id:
            qs = qs.filter(id=sv_id)

        if not qs.exists():
            self.stderr.write(self.style.ERROR("未找到可处理的 SourceVersion"))
            return

        for version in qs:
            sid = str(version.id)
            self.stdout.write(f"处理 {sid} …")

            updated = self._refresh_evidence_search_fields(sid)
            stats = build_retrieval_projections(sid)
            enqueue_embeddings(sid, sync=sync_embed)

            self.stdout.write(
                self.style.SUCCESS(
                    f"  evidence_search={updated}, "
                    f"chunks={stats['chunks']}, sentences={stats['sentences']}, "
                    f"embed={'sync' if sync_embed else 'queued'}"
                )
            )

        if sync_embed:
            self._print_embedding_stats(sv_id)

    def _refresh_evidence_search_fields(self, source_version_id: str) -> int:
        units = list(EvidenceUnit.objects.filter(source_version_id=source_version_id))
        if not units:
            return 0

        for unit in units:
            unit.segmented_content = " ".join(jieba.cut(unit.content or ""))
        EvidenceUnit.objects.bulk_update(units, ["segmented_content"])
        EvidenceUnit.objects.filter(source_version_id=source_version_id).update(
            search_vector=SearchVector("segmented_content", config="simple"),
        )
        return len(units)

    def _print_embedding_stats(self, source_version_id: str | None) -> None:
        chunk_qs = ChunkProjection.objects.all()
        sentence_qs = SentenceProjection.objects.all()
        if source_version_id:
            chunk_qs = chunk_qs.filter(source_version_id=source_version_id)
            from mentora.retrieval.models import EvidenceUnit

            eids = EvidenceUnit.objects.filter(
                source_version_id=source_version_id
            ).values_list("id", flat=True)
            sentence_qs = sentence_qs.filter(evidence_unit_id__in=eids)

        chunk_emb = chunk_qs.filter(embedding__isnull=False).count()
        sentence_emb = sentence_qs.filter(embedding__isnull=False).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"embedding 完成：chunks {chunk_emb}/{chunk_qs.count()}, "
                f"sentences {sentence_emb}/{sentence_qs.count()}"
            )
        )
