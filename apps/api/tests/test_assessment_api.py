"""AssessorAgent 测验生成链路测试。"""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mentora.agent_runtime.schemas.output import AgentOutput, ToolInvocationRecord
from mentora.assessment.services.agent_generation import extract_generate_item_session_id
from mentora.knowledge.models import ProcessingStatus, Source, SourceVersion
from mentora.retrieval.models import EvidenceUnit
from mentora.courses.models import CourseCreationSession


class ExtractSessionIdTests(TestCase):
    def test_extract_generate_item_session_id(self):
        output = AgentOutput(
            agent_role="assessor",
            task_id="task-1",
            tool_calls_made=[
                ToolInvocationRecord(
                    tool_name="retrieve_evidence",
                    success=True,
                ),
                ToolInvocationRecord(
                    tool_name="generate_item",
                    success=True,
                    result={"session_id": "session-123", "item_count": 2},
                ),
            ],
        )

        self.assertEqual(extract_generate_item_session_id(output), "session-123")


@override_settings(LLM_API_KEY="test-key")
class AssessmentApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="assessment@example.com", password="test-pass-123",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_generate_requires_source_ids(self):
        response = self.client.post(
            "/api/assessment/sessions/generate/",
            data=json.dumps({"source_version_ids": []}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        body = response.json()
        self.assertTrue("课程文件" in body["error"] or "任务证据" in body["error"])

    @override_settings(DEBUG=False, DEV_COURSE_SESSION_ID=None)
    def test_generate_requires_course_session_id_outside_debug(self):
        response = self.client.post(
            "/api/assessment/sessions/generate/",
            data=json.dumps({"source_version_ids": [str(uuid.uuid4())]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"error": "缺少 course_session_id"})

    def test_generate_submit_and_complete_quiz_session(self):
        source = Source.objects.create(owner=self.user, display_title="Cache 讲义")
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
        evidence = EvidenceUnit.objects.create(
            source_version_id=str(version.id),
            bundle_id=uuid.uuid4(),
            content="Cache 是位于 CPU 和主存之间的高速缓冲存储器。",
            page_number=1,
            element_indices=[0],
        )

        def fake_fast_generation(req):
            from mentora.assessment.models import AssessmentItem
            from mentora.assessment.services import create_item, create_session

            created = create_item(
                course_session_id=req.course_session_id,
                question_type=AssessmentItem.QuestionType.SINGLE_CHOICE,
                question_text="Cache 位于哪两个部件之间？",
                correct_answer="A",
                difficulty=2,
                options_json=[
                    {"label": "A", "text": "CPU 和主存"},
                    {"label": "B", "text": "主存和外存"},
                    {"label": "C", "text": "输入和输出设备"},
                    {"label": "D", "text": "控制器和运算器"},
                ],
                explanation="资料说明 Cache 位于 CPU 和主存之间。",
                source_evidence_ids=[str(evidence.id)],
                status="published",
                source_type="ai",
            )
            session = create_session(
                course_session_id=req.course_session_id,
                item_ids=[created["item_id"]],
                unit_id=req.unit_id or "",
            )
            from mentora.assessment.services.quiz_generation import QuizGenerationMetrics

            return session["session_id"], QuizGenerationMetrics(item_count=1)

        client = self.client
        course_session = CourseCreationSession.objects.create(owner=self.user, goal="Cache")
        course_session_id = str(course_session.id)
        with patch(
            "mentora.assessment.views.run_quiz_generation_fast_sync",
            side_effect=fake_fast_generation,
        ):
            generated = client.post(
                "/api/assessment/sessions/generate/",
                data=json.dumps({
                    "course_session_id": course_session_id,
                    "source_version_ids": [str(version.id)],
                    "count": 1,
                }),
                content_type="application/json",
            )

        self.assertEqual(generated.status_code, 201, generated.content)
        payload = generated.json()
        self.assertEqual(payload["total_items"], 1)
        item = payload["items"][0]
        self.assertEqual(item["question_text"], "Cache 位于哪两个部件之间？")
        self.assertEqual(item["source_links"][0]["source_version_id"], str(version.id))

        submitted = client.post(
            f"/api/assessment/sessions/{payload['session_id']}/attempts/",
            data=json.dumps({"item_id": item["item_id"], "user_answer": "A"}),
            content_type="application/json",
        )
        self.assertEqual(submitted.status_code, 200)
        self.assertTrue(submitted.json()["is_correct"])

        completed = client.post(f"/api/assessment/sessions/{payload['session_id']}/complete/")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.json()["score_pct"], 100)


class ValidateItemAsyncTests(TestCase):
    def test_validate_item_async_handles_structured_output_fallback(self):
        import asyncio

        from mentora.assessment.services import validate_item_async
        from mentora.model_gateway.exceptions import StructuredOutputError
        from mentora.model_gateway.schemas import ChatResponse

        revision_id = str(uuid.uuid4())
        calls = {"count": 0}

        class FakeGateway:
            async def chat(self, **kwargs):
                calls["count"] += 1
                if kwargs.get("structured_output_schema") is not None:
                    raise StructuredOutputError("missing valid field")
                return ChatResponse(content='{"valid": true, "issues": []}')

        async def run_validation():
            with patch(
                "mentora.assessment.services._load_revision_for_validation",
                return_value=(None, ["题干：1+1 等于几？"], "规则"),
            ), patch(
                "mentora.assessment.services._persist_validation_result",
                side_effect=lambda rid, *, valid, issues: {
                    "revision_id": rid,
                    "valid": valid,
                    "issues": issues,
                    "status": "published" if valid else "draft",
                },
            ), patch("mentora.agent_runtime.views.get_gateway", return_value=FakeGateway()):
                return await validate_item_async(revision_id)

        result = asyncio.run(run_validation())
        self.assertTrue(result["valid"])
        self.assertGreaterEqual(calls["count"], 2)


class QuizItemNormalizationTests(TestCase):
    def test_normalize_raw_items_accepts_string_payload(self):
        from mentora.assessment.services.quiz_item_normalization import normalize_raw_items

        accepted, skipped = normalize_raw_items(
            [
                json.dumps({
                    "question_text": "1+1=?",
                    "correct_answer": "A",
                    "options": [
                        {"label": "A", "text": "2"},
                        {"label": "B", "text": "3"},
                        {"label": "C", "text": "4"},
                        {"label": "D", "text": "5"},
                    ],
                    "source_evidence_ids": ["e1"],
                })
            ],
            allowed_evidence_ids={"e1"},
            fallback_evidence_ids=["e1"],
        )
        self.assertEqual(len(accepted), 1)
        self.assertEqual(skipped, [])


class QuizPaperParserTests(TestCase):
    def test_parse_questions_alias_payload(self):
        from mentora.assessment.services.quiz_paper_parser import parse_quiz_items_from_content

        content = json.dumps({
            "questions": [{
                "question": "浮点数精度问题是什么？",
                "answer": "A",
                "options": [
                    {"label": "A", "text": "二进制无法精确表示某些十进制小数"},
                    {"label": "B", "text": "CPU 太慢"},
                    {"label": "C", "text": "内存不足"},
                    {"label": "D", "text": "编译器 bug"},
                ],
                "source_evidence_ids": ["e1"],
            }],
        }, ensure_ascii=False)
        items = parse_quiz_items_from_content(content)
        self.assertEqual(len(items), 1)
        self.assertIn("浮点数", items[0]["question_text"])
