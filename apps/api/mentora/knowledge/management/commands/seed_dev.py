"""
开发环境种子数据：创建演示用户资源库与解析证据。

约定：
- 幂等：重复执行不制造重复 Source（按 display_title 标记识别）
- 使用仓库内 fixture PDF，不依赖私人资料

@module mentora/knowledge/management/commands/seed_dev
"""

import hashlib
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from mentora.knowledge.models import ProcessingStatus, Source
from mentora.knowledge.services.upload import upload_file_direct
from mentora.retrieval.models import EvidenceUnit
from config.authentication import get_development_user


SEED_TITLE = "[seed] 计算机系统概述"
FIXTURE_REL = ("tests", "fixtures", "normal.pdf")


class Command(BaseCommand):
    help = "填充本地开发最小闭环样例数据（资源库 + 解析证据）"

    def handle(self, *args, **options):
        owner = get_development_user()
        api_root = settings.BASE_DIR
        fixture_path = os.path.join(api_root, *FIXTURE_REL)

        if not os.path.exists(fixture_path):
            self.stderr.write(self.style.ERROR(f"Fixture 不存在: {fixture_path}"))
            return

        existing = Source.objects.filter(
            owner=owner,
            display_title=SEED_TITLE,
        ).first()
        if existing and existing.latest_version:
            sv = existing.latest_version
            if sv.processing_status == ProcessingStatus.COMPLETED:
                count = EvidenceUnit.objects.filter(
                    source_version_id=str(sv.id)
                ).count()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"种子数据已存在: source={existing.id}, "
                        f"evidence={count} 条"
                    )
                )
                return

        with open(fixture_path, "rb") as fh:
            file_bytes = fh.read()
        sha256 = hashlib.sha256(file_bytes).hexdigest()

        result = upload_file_direct(
            file_bytes=file_bytes,
            filename="normal.pdf",
            content_sha256=sha256,
            owner=owner,
            sync_processing=True,
        )

        source = Source.objects.get(id=result["sourceId"])
        source.display_title = SEED_TITLE
        source.save(update_fields=["display_title"])

        evidence_count = EvidenceUnit.objects.filter(
            source_version_id=result["sourceVersionId"]
        ).count()

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_dev 完成: source={result['sourceId']}, "
                f"version={result['sourceVersionId']}, "
                f"status={result['processingStatus']}, "
                f"evidence={evidence_count}"
            )
        )
