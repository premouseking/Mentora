"""Session → Course 迁移契约测试。"""

import json
import uuid

import pytest
from django.test import Client

from mentora.courses.models import Course, CourseCreationSession, SessionStatus
from mentora.courses.services import bind_durable_course_refs, confirm_course_from_session
from mentora.learning.models import LearningPlan, LearningPlanRevision
from mentora.learning.services import create_plan_revision, get_active_plan


@pytest.fixture
def api_client():
    return Client()


@pytest.fixture
def completed_session(db):
    session = CourseCreationSession.objects.create(
        goal="测试目标",
        title="测试课",
        status=SessionStatus.COMPLETED,
    )
    return session


@pytest.fixture
def plan_on_session(completed_session):
    result = create_plan_revision(
        str(completed_session.id),
        {
            "phases": [
                {
                    "title": "阶段一",
                    "objective": "入门",
                    "estimated_minutes": 60,
                    "units": [
                        {
                            "topic_id": None,
                            "target_depth": "basic",
                            "estimated_minutes": 30,
                            "tasks": [
                                {
                                    "task_type": "lecture",
                                    "delivery_mode": "text",
                                    "estimated_minutes": 30,
                                    "required": True,
                                }
                            ],
                        }
                    ],
                }
            ]
        },
    )
    revision = LearningPlanRevision.objects.get(id=result["revision_id"])
    revision.status = LearningPlanRevision.Status.ACTIVE
    revision.save(update_fields=["status"])
    plan = LearningPlan.objects.get(id=result["plan_id"])
    plan.active_revision_id = revision.id
    plan.save(update_fields=["active_revision_id"])
    completed_session.extra["plan_revision_id"] = str(revision.id)
    completed_session.save(update_fields=["extra"])
    return plan, revision


@pytest.mark.django_db
class TestConfirmCourseFromSession:
    def test_binds_learning_plan_course_fk(self, completed_session, plan_on_session):
        plan, _revision = plan_on_session
        assert plan.course_id is None
        assert plan.creation_session_id == completed_session.id

        result = confirm_course_from_session(str(completed_session.id))
        course = Course.objects.get(id=result["course_id"])

        plan.refresh_from_db()
        assert plan.course_id == course.id

    def test_bind_durable_course_refs_idempotent(self, completed_session, plan_on_session):
        plan, _revision = plan_on_session
        result = confirm_course_from_session(str(completed_session.id))
        course = Course.objects.get(id=result["course_id"])

        bind_durable_course_refs(completed_session, course)
        plan.refresh_from_db()
        assert plan.course_id == course.id


@pytest.mark.django_db
class TestGetActivePlan:
    def test_uses_course_id_not_session(self, completed_session, plan_on_session):
        result = confirm_course_from_session(str(completed_session.id))
        course_id = result["course_id"]

        plan_by_course = get_active_plan(course_id)
        assert plan_by_course is not None
        assert plan_by_course["phases"]

        plan_by_session = get_active_plan(str(completed_session.id))
        assert plan_by_session is not None
        assert plan_by_session["revision_id"] == plan_by_course["revision_id"]


@pytest.mark.django_db
class TestArchivedSessionWrites:
    def test_patch_returns_409_when_archived(self, api_client, completed_session, plan_on_session):
        confirm_course_from_session(str(completed_session.id))
        completed_session.status = SessionStatus.ARCHIVED
        completed_session.save(update_fields=["status"])

        response = api_client.patch(
            f"/api/courses/sessions/{completed_session.id}/update/",
            data=json.dumps({"level": "进阶"}),
            content_type="application/json",
        )
        assert response.status_code == 409


@pytest.mark.django_db
class TestSessionListApi:
    def test_active_courses_and_completed_sessions_split(
        self, api_client, completed_session, plan_on_session,
    ):
        confirm = confirm_course_from_session(str(completed_session.id))
        course_id = confirm["course_id"]

        pending = CourseCreationSession.objects.create(
            goal="待确认",
            title="待确认课",
            status=SessionStatus.COMPLETED,
        )

        response = api_client.get("/api/courses/sessions/")
        assert response.status_code == 200
        data = response.json()

        active_rows = [row for row in data if row["status"] == "active"]
        completed_rows = [row for row in data if row["status"] == "completed"]

        assert any(row["course_id"] == course_id for row in active_rows)
        assert all(row["course_id"] is not None for row in active_rows)
        assert any(row["session_id"] == str(pending.id) for row in completed_rows)
        assert all(row["course_id"] is None for row in completed_rows)


@pytest.mark.django_db
class TestCoursePlanApi:
    def test_course_plan_endpoint(self, api_client, completed_session, plan_on_session):
        confirm = confirm_course_from_session(str(completed_session.id))
        course_id = confirm["course_id"]

        response = api_client.get(f"/api/courses/{course_id}/plan/")
        assert response.status_code == 200
        body = response.json()
        assert body["phases"]
        assert uuid.UUID(body["revision_id"])
