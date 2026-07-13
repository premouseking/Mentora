import json
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from mentora.courses.models import CourseCreationSession
from mentora.knowledge.models import CourseSource, Source, SourceVersion


class CourseApiRegressionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="course-regression@example.com", password="test-pass-123"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_delete_session_removes_non_fk_source_links(self):
        session = CourseCreationSession.objects.create(owner=self.user, goal="test")
        source = Source.objects.create(owner=self.user, display_title="test.pdf")
        version = SourceVersion.objects.create(
            source=source,
            content_sha256="a" * 64,
            object_key="uploads/test.pdf",
            byte_size=10,
        )
        CourseSource.objects.create(
            course_session_id=str(session.id), source_version=version
        )

        response = self.client.delete(f"/api/courses/sessions/{session.id}/delete/")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CourseCreationSession.objects.filter(id=session.id).exists())
        self.assertFalse(CourseSource.objects.filter(course_session_id=str(session.id)).exists())

    def test_profile_revise_returns_404_for_missing_course(self):
        response = self.client.patch(
            f"/api/courses/{uuid.uuid4()}/profile/",
            data=json.dumps({"goal": "new goal"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)

    def test_scope_extend_returns_404_for_missing_course(self):
        response = self.client.post(
            f"/api/courses/{uuid.uuid4()}/scope/",
            data=json.dumps({"source_version_ids": [str(uuid.uuid4())]}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 404)
