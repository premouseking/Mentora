"""上传与资源库 smoke 测试。"""

import hashlib
import json
import os

import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APIClient

from mentora.knowledge.models import ProcessingStatus, SourceVersion
from mentora.knowledge.services.upload import upload_file_direct
from mentora.retrieval.models import EvidenceUnit


@pytest.fixture(autouse=True)
def filesystem_storage():
    with override_settings(
        OBJECT_STORAGE_BACKEND="filesystem",
        OBJECT_STORAGE_FS_ROOT="/tmp/mentora/test-storage",
        CELERY_TASK_ALWAYS_EAGER=True,
    ):
        yield


@pytest.fixture
def normal_pdf_bytes():
    path = os.path.join(settings.BASE_DIR, "tests", "fixtures", "normal.pdf")
    if not os.path.exists(path):
        pytest.skip("normal.pdf fixture 不存在")
    with open(path, "rb") as fh:
        return fh.read()


@pytest.mark.django_db
def test_upload_direct_persists_evidence(normal_pdf_bytes, django_user_model):
    user = django_user_model.objects.create_user(email="direct@example.com", password="test-pass-123")
    sha256 = hashlib.sha256(normal_pdf_bytes).hexdigest()
    result = upload_file_direct(
        file_bytes=normal_pdf_bytes,
        filename="normal.pdf",
        content_sha256=sha256,
        owner=user,
        sync_processing=True,
    )

    sv = SourceVersion.objects.get(id=result["sourceVersionId"])
    assert sv.processing_status == ProcessingStatus.COMPLETED
    assert sv.object_key.startswith("uploads/")
    assert "\\" not in sv.object_key
    assert not sv.object_key.startswith("/")
    assert sv.artifact_ref.startswith("artifacts/")

    count = EvidenceUnit.objects.filter(source_version_id=str(sv.id)).count()
    assert count > 0


@pytest.mark.django_db
def test_upload_http_smoke(normal_pdf_bytes, django_user_model):
    user = django_user_model.objects.create_user(email="http@example.com", password="test-pass-123")
    client = APIClient()
    client.force_authenticate(user=user)
    sha256 = hashlib.sha256(normal_pdf_bytes).hexdigest()
    size = len(normal_pdf_bytes)

    create = client.post(
        "/api/uploads/",
        data=json.dumps({"size": size, "filename": "normal.pdf"}),
        content_type="application/json",
    )
    assert create.status_code == 200
    payload = create.json()

    from mentora.common.storage import ObjectStorageService

    storage = ObjectStorageService()
    storage.put_object(payload["objectKey"], normal_pdf_bytes)

    complete = client.post(
        "/api/uploads/complete/",
        data=json.dumps(
            {
                "uploadId": payload["uploadId"],
                "sha256": sha256,
                "size": size,
            }
        ),
        content_type="application/json",
    )
    assert complete.status_code == 200
    body = complete.json()
    assert body["processingStatus"] == ProcessingStatus.COMPLETED

    list_resp = client.get("/api/library/sources/")
    assert list_resp.status_code == 200
    assert list_resp.json()["count"] >= 1


@pytest.mark.django_db
def test_seed_dev_idempotent(normal_pdf_bytes):
    from django.core.management import call_command

    call_command("seed_dev")
    call_command("seed_dev")

    from mentora.knowledge.models import Source

    seeded = Source.objects.filter(display_title="[seed] 计算机系统概述").count()
    assert seeded == 1
