import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from mentora.courses.models import Course, CourseCreationSession
from mentora.courses.services import resolve_course
from mentora.topics.services import build_topic_tree, get_topic_tree


class CourseIdentityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(email="owner@example.com", password="test-pass")
        self.other_user = user_model.objects.create_user(email="other@example.com", password="test-pass")
        self.session = CourseCreationSession.objects.create(owner=self.user, goal="Learn databases")
        self.course = Course.objects.create(owner=self.user, session=self.session)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_resolve_course_accepts_course_and_session_ids(self):
        by_course = resolve_course(str(self.course.id), owner=self.user)
        by_session = resolve_course(str(self.session.id), owner=self.user)

        self.assertEqual(by_course.course_id, str(self.course.id))
        self.assertEqual(by_session.course_id, str(self.course.id))

    def test_topic_tree_is_bound_to_formal_course(self):
        build_topic_tree(str(self.session.id), [{"name": "SQL", "parent_index": None}])

        tree = get_topic_tree(str(self.course.id))

        self.assertEqual([node["name"] for node in tree], ["SQL"])
        self.assertEqual(self.course.topics.count(), 1)

    def test_course_plan_rejects_another_users_course(self):
        other_session = CourseCreationSession.objects.create(owner=self.other_user, goal="Private")
        other_course = Course.objects.create(owner=self.other_user, session=other_session)

        response = self.client.get(f"/api/courses/{other_course.id}/plan/")

        self.assertEqual(response.status_code, 404)

    def test_course_activity_updates_creation_session(self):
        response = self.client.patch(
            f"/api/courses/{self.course.id}/activity/",
            {"last_studied_at": "2026-07-14T08:30:00Z"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.last_studied_at.isoformat(), "2026-07-14T08:30:00+00:00")

    def test_course_activity_rejects_invalid_datetime(self):
        response = self.client.patch(
            f"/api/courses/{self.course.id}/activity/",
            {"last_studied_at": str(uuid.uuid4())},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
