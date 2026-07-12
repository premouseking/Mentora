"""
资源库上传 smoke：fixture PDF → 对象存储 → SourceVersion → 解析 → 证据入库。

@module mentora/knowledge/management/commands/smoke_upload_resource
"""

import hashlib
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.test import Client

from mentora.knowledge.models import ProcessingStatus, SourceVersion
from mentora.knowledge.services.upload import upload_file_direct
from mentora.retrieval.models import EvidenceUnit


class Command(BaseCommand):
    help = "运行资源库上传与解析 smoke（支持 HTTP 或直接服务调用）"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture",
            default="normal.pdf",
            help="tests/fixtures 下的 PDF 文件名",
        )
        parser.add_argument(
            "--via-http",
            action="store_true",
            help="通过 HTTP API 走上传 create/complete 链路",
        )

    def handle(self, *args, **options):
        fixture_name = options["fixture"]
        fixture_path = os.path.join(
            settings.BASE_DIR, "tests", "fixtures", fixture_name
        )
        if not os.path.exists(fixture_path):
            self.stderr.write(self.style.ERROR(f"Fixture 不存在: {fixture_path}"))
            return

        with open(fixture_path, "rb") as fh:
            file_bytes = fh.read()
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        size = len(file_bytes)

        if options["via_http"]:
            result = self._smoke_via_http(fixture_name, sha256, size, file_bytes)
        else:
            from config.authentication import get_development_user
            result = upload_file_direct(
                file_bytes=file_bytes,
                filename=fixture_name,
                content_sha256=sha256,
                owner=get_development_user(),
                sync_processing=True,
            )

        sv = SourceVersion.objects.get(id=result["sourceVersionId"])
        if sv.processing_status != ProcessingStatus.COMPLETED:
            raise CommandError(f"处理未成功: {sv.processing_status}")

        evidence_count = EvidenceUnit.objects.filter(
            source_version_id=str(sv.id)
        ).count()
        if evidence_count == 0:
            raise CommandError("未生成证据单元")

        # 云端迁移性：object_key 不应为本地绝对路径
        if sv.object_key.startswith("/") or "\\" in sv.object_key:
            raise CommandError("object_key 包含本地路径")

        self.stdout.write(
            self.style.SUCCESS(
                json.dumps(
                    {
                        "ok": True,
                        "sourceId": result["sourceId"],
                        "sourceVersionId": result["sourceVersionId"],
                        "objectKey": sv.object_key,
                        "artifactRef": sv.artifact_ref,
                        "evidenceCount": evidence_count,
                    },
                    ensure_ascii=False,
                )
            )
        )

    def _smoke_via_http(
        self,
        filename: str,
        sha256: str,
        size: int,
        file_bytes: bytes,
    ) -> dict:
        client = Client()
        from mentora.common.storage import ObjectStorageService

        create_resp = client.post(
            "/api/uploads/",
            data=json.dumps({"size": size, "filename": filename}),
            content_type="application/json",
        )
        if create_resp.status_code != 200:
            raise RuntimeError(f"create 失败: {create_resp.content}")

        payload = create_resp.json()
        upload_id = payload["uploadId"]
        object_key = payload["objectKey"]

        storage = ObjectStorageService()
        storage.put_object(object_key, file_bytes, content_type="application/pdf")

        complete_resp = client.post(
            "/api/uploads/complete/",
            data=json.dumps(
                {
                    "uploadId": upload_id,
                    "sha256": sha256,
                    "size": size,
                }
            ),
            content_type="application/json",
        )
        if complete_resp.status_code != 200:
            raise RuntimeError(f"complete 失败: {complete_resp.content}")

        return complete_resp.json()
