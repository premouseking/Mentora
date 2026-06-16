"""
Django management command：验证检索模块配置和模型。

用法：
    python manage.py validate_retrieval
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "验证检索模块的 ORM 模型、索引和 pgvector 配置"

    def handle(self, **options):
        self.stdout.write("=" * 56)
        self.stdout.write("  检索模块验证")
        self.stdout.write("=" * 56)

        # 1. 模型导入
        try:
            from mentora.retrieval.models import (  # noqa: F401
                ChunkProjection,
                EvidenceUnit,
                PageTextProjection,
                SentenceProjection,
            )
            self.stdout.write(self.style.SUCCESS("  ✓ 四个 ORM 模型导入成功"))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"  ✗ 模型导入失败: {exc}"))
            return

        # 2. 数据库连接
        from django.db import connection
        try:
            connection.ensure_connection()
            self.stdout.write(self.style.SUCCESS("  ✓ 数据库连接正常"))
        except Exception as exc:
            self.stderr.write(self.style.WARNING(f"  ⚠ 数据库不可用（迁移将跳过）: {exc}"))

        # 3. pgvector 扩展
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'vector'")
                if cursor.fetchone():
                    self.stdout.write(self.style.SUCCESS("  ✓ pgvector 扩展已启用"))
                else:
                    self.stderr.write(self.style.WARNING(
                        "  ⚠ pgvector 扩展未启用。执行: CREATE EXTENSION IF NOT EXISTS vector"
                    ))
        except Exception:
            self.stderr.write(self.style.WARNING("  ⚠ 无法检查 pgvector 扩展（数据库不可用）"))

        # 4. pg_trgm 扩展
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT extname FROM pg_extension WHERE extname = 'pg_trgm'")
                if cursor.fetchone():
                    self.stdout.write(self.style.SUCCESS("  ✓ pg_trgm 扩展已启用"))
                else:
                    self.stderr.write(self.style.WARNING(
                        "  ⚠ pg_trgm 扩展未启用。执行: CREATE EXTENSION IF NOT EXISTS pg_trgm"
                    ))
        except Exception:
            self.stderr.write(self.style.WARNING("  ⚠ 无法检查 pg_trgm 扩展（数据库不可用）"))

        # 5. 迁移状态
        from django.db.migrations.recorder import MigrationRecorder
        try:
            recorder = MigrationRecorder(connection)
            applied = set(recorder.applied_migrations())
            retrieval_migrations = {
                m for m in applied if m[0] == "retrieval"
            }
            if retrieval_migrations:
                self.stdout.write(self.style.SUCCESS(
                    f"  ✓ retrieval 迁移已应用: {len(retrieval_migrations)} 个"
                ))
            else:
                self.stderr.write(self.style.WARNING(
                    "  ⚠ retrieval 迁移未应用。执行: python manage.py migrate retrieval"
                ))
        except Exception:
            self.stderr.write(self.style.WARNING("  ⚠ 无法检查迁移状态（数据库不可用）"))

        # 6. 模型计数（无数据库时跳过）
        try:
            self.stdout.write(f"    EvidenceUnit 记录数: {EvidenceUnit.objects.count()}")
            self.stdout.write(f"    ChunkProjection 记录数: {ChunkProjection.objects.count()}")
            self.stdout.write(f"    PageTextProjection 记录数: {PageTextProjection.objects.count()}")
            self.stdout.write(f"    SentenceProjection 记录数: {SentenceProjection.objects.count()}")
        except Exception:
            self.stdout.write("    （跳过计数 — 数据库不可用）")

        self.stdout.write("=" * 56)
        self.stdout.write("  验证完成。⚠ 标记项需在 PostgreSQL 环境中处理。")
