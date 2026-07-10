"""课程 Agent 上下文与 API 测试。"""

import json
import uuid
from unittest.mock import patch

from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from mentora.agent_runtime.models import CourseAgentMessage, CourseAgentSession
from mentora.agent_runtime.services.course_context import build_course_agent_context
from mentora.courses.models import (
    Course,
    CourseCreationSession,
    CourseKnowledgeScopeRevision,
    CourseProfileRevision,
    CourseScopeBinding,
)


def _create_course_with_scope(source_ids: list[str], owner=None) -> Course:
    session = CourseCreationSession.objects.create(
        owner=owner,
        goal="测试课程目标",
        title="测试课程",
        level="入门",
    )
    course = Course.objects.create(session=session, owner=owner)
    profile = CourseProfileRevision.objects.create(
        course=course,
        goal=session.goal,
        level=session.level,
        status=CourseProfileRevision.Status.CONFIRMED,
    )
    scope = CourseKnowledgeScopeRevision.objects.create(
        course=course,
        label="v1",
        status=CourseKnowledgeScopeRevision.Status.ACTIVE,
    )
    for pos, source_id in enumerate(source_ids):
        CourseScopeBinding.objects.create(
            revision=scope,
            source_version_id=source_id,
            position=pos,
        )
    course.active_profile_revision_id = profile.id
    course.active_scope_revision_id = scope.id
    course.save(update_fields=["active_profile_revision_id", "active_scope_revision_id"])
    return course


class CourseAgentContextTests(TestCase):
    def test_out_of_scope_mention_not_injected(self):
        course = _create_course_with_scope(["sv-in-scope"])
        context = build_course_agent_context(
            course_id=str(course.id),
            mentions=[
                {"id": "sv-in-scope", "type": "course_file", "label": "讲义"},
                {"id": "sv-out-scope", "type": "course_file", "label": "外部资料"},
            ],
        )

        self.assertIn("sv-in-scope", context["source_version_ids"])
        self.assertNotIn("sv-out-scope", context["source_version_ids"])
        self.assertEqual(context["mention_context"]["source_version_ids"], ["sv-in-scope"])


class CourseAgentApiTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="agent@example.com", password="test-pass-123",
        )
        self.client.force_authenticate(user=self.user)
        self.course = _create_course_with_scope(["sv-1"], owner=self.user)

    def test_list_and_detail_empty(self):
        list_resp = self.client.get(f"/api/courses/{self.course.id}/agent-sessions/")
        self.assertEqual(list_resp.status_code, 200)
        self.assertEqual(list_resp.json()["items"], [])

    @override_settings(LLM_API_KEY="")
    def test_stream_without_llm_returns_503_and_no_session(self):
        before = CourseAgentSession.objects.count()
        resp = self.client.post(
            f"/api/courses/{self.course.id}/agent-sessions/stream/",
            data=json.dumps({"message": "总结当前学习任务"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(CourseAgentSession.objects.count(), before)

    @override_settings(LLM_API_KEY="test-key")
    @patch("mentora.agent_runtime.course_agent_views._ensure_runtime")
    def test_first_message_creates_session_and_messages(self, mock_runtime):
        class FakeOrchestrator:
            async def run_stream(self, task):
                yield 'data: {"type":"chunk","content":"这是测试回复"}\n\n'
                yield 'data: {"type":"done"}\n\n'

        mock_runtime.return_value = FakeOrchestrator()

        resp = self.client.post(
            f"/api/courses/{self.course.id}/agent-sessions/stream/",
            data=json.dumps({"message": "总结当前学习任务"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)

        body = b"".join(resp.streaming_content).decode("utf-8")
        self.assertIn("session_created", body)
        self.assertIn("这是测试回复", body)

        session = CourseAgentSession.objects.get(course_id=self.course.id)
        self.assertEqual(session.messages.count(), 2)
        self.assertEqual(session.messages.first().role, CourseAgentMessage.Role.USER)
        self.assertEqual(session.messages.last().role, CourseAgentMessage.Role.ASSISTANT)
        self.assertEqual(session.messages.last().content, "这是测试回复")

    @override_settings(LLM_API_KEY="test-key")
    @patch("mentora.agent_runtime.course_agent_views._ensure_runtime")
    def test_follow_up_reuses_same_session(self, mock_runtime):
        class FakeOrchestrator:
            async def run_stream(self, task):
                yield 'data: {"type":"chunk","content":"续聊回复"}\n\n'
                yield 'data: {"type":"done"}\n\n'

        mock_runtime.return_value = FakeOrchestrator()

        first = self.client.post(
            f"/api/courses/{self.course.id}/agent-sessions/stream/",
            data=json.dumps({"message": "第一条消息"}),
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 200)
        b"".join(first.streaming_content)
        session = CourseAgentSession.objects.get(course_id=self.course.id)

        second = self.client.post(
            f"/api/courses/{self.course.id}/agent-sessions/stream/",
            data=json.dumps({
                "message": "第二条消息",
                "agent_session_id": str(session.id),
            }),
            content_type="application/json",
        )
        self.assertEqual(second.status_code, 200)
        b"".join(second.streaming_content)
        self.assertEqual(CourseAgentSession.objects.filter(course_id=self.course.id).count(), 1)
        self.assertEqual(session.messages.count(), 4)

        detail = self.client.get(
            f"/api/courses/{self.course.id}/agent-sessions/{session.id}/",
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.json()["messages"]), 4)

    def test_detail_404_for_foreign_session(self):
        other_course = _create_course_with_scope(["sv-2"], owner=self.user)
        session = CourseAgentSession.objects.create(
            course_id=other_course.id,
            course_session_id=other_course.session_id,
            title="其他课程会话",
        )
        resp = self.client.get(
            f"/api/courses/{self.course.id}/agent-sessions/{session.id}/",
        )
        self.assertEqual(resp.status_code, 404)

    @override_settings(LLM_API_KEY="test-key")
    @patch("mentora.agent_runtime.course_agent_views._ensure_runtime")
    def test_greeting_sets_allow_retrieval_false(self, mock_runtime):
        captured: dict = {}

        class FakeOrchestrator:
            async def run_stream(self, task):
                captured["task"] = task
                yield 'data: {"type":"chunk","content":"你好！"}\n\n'
                yield 'data: {"type":"done"}\n\n'

        mock_runtime.return_value = FakeOrchestrator()

        resp = self.client.post(
            f"/api/courses/{self.course.id}/agent-sessions/stream/",
            data=json.dumps({"message": "你好"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        b"".join(resp.streaming_content)

        task = captured["task"]
        self.assertFalse(task.tool_metadata.get("allow_retrieval"))
        self.assertEqual(task.tool_metadata.get("chat_intent"), "smalltalk")

    @override_settings(LLM_API_KEY="test-key")
    @patch("mentora.agent_runtime.course_agent_views._ensure_runtime")
    def test_course_question_sets_allow_retrieval_true(self, mock_runtime):
        captured: dict = {}

        class FakeOrchestrator:
            async def run_stream(self, task):
                captured["task"] = task
                yield 'data: {"type":"chunk","content":"操作系统是..."}\n\n'
                yield 'data: {"type":"done"}\n\n'

        mock_runtime.return_value = FakeOrchestrator()

        resp = self.client.post(
            f"/api/courses/{self.course.id}/agent-sessions/stream/",
            data=json.dumps({"message": "操作系统是什么"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        b"".join(resp.streaming_content)

        task = captured["task"]
        self.assertTrue(task.tool_metadata.get("allow_retrieval"))
        self.assertEqual(task.tool_metadata.get("chat_intent"), "course_qa")
