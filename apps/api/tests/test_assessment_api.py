"""刷题模式 API 测试。"""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import pytest
from django.test import Client, override_settings

from mentora.knowledge.models import ProcessingStatus, Source, SourceVersion
from mentora.model_gateway.schemas import ChatResponse, TokenUsage
from mentora.retrieval.models import EvidenceUnit


class FakeQuizGateway:
    async def chat(self, *args, **kwargs):
        return ChatResponse(
            content="{}",
            usage=TokenUsage(),
            model="fake",
            parsed_output={
                "items": [
                    {
                        "question_text": "Cache 位于哪两个部件之间？",
                        "options": [
                            {"label": "A", "text": "CPU 和主存"},
                            {"label": "B", "text": "主存和外存"},
                            {"label": "C", "text": "输入和输出设备"},
                            {"label": "D", "text": "控制器和运算器"},
                        ],
                        "correct_answer": "A",
                        "explanation": "资料说明 Cache 位于 CPU 和主存之间。",
                        "difficulty": 2,
                        "source_evidence_ids": [],
                    }
                ]
            },
        )


@pytest.mark.django_db
@override_settings(LLM_API_KEY="test-key")
def test_generate_requires_source_ids():
    client = Client()

    response = client.post(
        "/api/assessment/sessions/generate/",
        data=json.dumps({"source_version_ids": []}),
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
@override_settings(LLM_API_KEY="test-key")
def test_generate_submit_and_complete_quiz_session():
    source = Source.objects.create(owner_id="dev", display_title="Cache 讲义")
    version = SourceVersion.objects.create(
        source=source,
        content_sha256="a" * 64,
        object_key="fixtures/cache.pdf",
        byte_size=128,
        original_filename="cache.pdf",
        processing_status=ProcessingStatus.COMPLETED,
    )
    source.latest_version = version
    source.save(update_fields=["latest_version"])
    EvidenceUnit.objects.create(
        source_version_id=str(version.id),
        bundle_id=uuid.uuid4(),
        content="Cache 是位于 CPU 和主存之间的高速缓冲存储器。",
        page_number=1,
        element_indices=[0],
    )

    client = Client()
    with patch("mentora.agent_runtime.views.get_gateway", return_value=FakeQuizGateway()):
        generated = client.post(
            "/api/assessment/sessions/generate/",
            data=json.dumps({"source_version_ids": [str(version.id)], "count": 1}),
            content_type="application/json",
        )

    assert generated.status_code == 201
    payload = generated.json()
    assert payload["total_items"] == 1
    item = payload["items"][0]
    assert item["question_text"] == "Cache 位于哪两个部件之间？"
    assert item["source_links"][0]["source_version_id"] == str(version.id)

    submitted = client.post(
        f"/api/assessment/sessions/{payload['session_id']}/attempts/",
        data=json.dumps({"item_id": item["item_id"], "user_answer": "A"}),
        content_type="application/json",
    )
    assert submitted.status_code == 200
    assert submitted.json()["is_correct"] is True

    completed = client.post(f"/api/assessment/sessions/{payload['session_id']}/complete/")
    assert completed.status_code == 200
    assert completed.json()["score_pct"] == 100
