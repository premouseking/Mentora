import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from mentora.courses.models import Course, CourseCreationSession
from mentora.knowledge.models import Source, SourceVersion
from mentora.retrieval.models import EvidenceUnit
from mentora.topics.models import Topic, TopicEdge, TopicEvidence


class TopicOwnershipTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="topic-owner@example.com", password="test-pass-123"
        )
        self.other_user = user_model.objects.create_user(
            email="topic-other@example.com", password="test-pass-123"
        )
        owner_session = CourseCreationSession.objects.create(owner=self.owner, goal="owner")
        other_session = CourseCreationSession.objects.create(owner=self.other_user, goal="other")
        self.owner_course = Course.objects.create(owner=self.owner, session=owner_session)
        self.other_course = Course.objects.create(owner=self.other_user, session=other_session)
        self.owner_topic = Topic.objects.create(
            course=self.owner_course,
            legacy_course_key=str(self.owner_course.id),
            name="owner topic",
        )
        self.other_topic = Topic.objects.create(
            course=self.other_course,
            legacy_course_key=str(self.other_course.id),
            name="private topic",
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.owner)

    def test_owner_can_read_own_topic_tree(self):
        response = self.client.get(f"/api/courses/{self.owner_course.id}/topics/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["name"] for item in response.data], ["owner topic"])

    def test_other_course_tree_cannot_be_read_or_rebuilt(self):
        get_response = self.client.get(f"/api/courses/{self.other_course.id}/topics/")
        create_response = self.client.post(
            f"/api/courses/{self.other_course.id}/topics/create/",
            {"topics": [{"name": "replacement"}]},
            format="json",
        )

        self.assertEqual(get_response.status_code, 404)
        self.assertEqual(create_response.status_code, 404)
        self.other_topic.refresh_from_db()
        self.assertEqual(self.other_topic.name, "private topic")

    def test_other_topic_cannot_be_modified_deleted_or_linked(self):
        update_response = self.client.patch(
            f"/api/topics/{self.other_topic.id}/", {"name": "stolen"}, format="json"
        )
        edge_response = self.client.post(
            f"/api/topics/{self.owner_topic.id}/edges/",
            {"target_id": str(self.other_topic.id)},
            format="json",
        )
        evidence_response = self.client.post(
            f"/api/topics/{self.other_topic.id}/evidence/",
            {"evidence_unit_ids": [str(uuid.uuid4())]},
            format="json",
        )
        delete_response = self.client.delete(f"/api/topics/{self.other_topic.id}/delete/")

        self.assertEqual(update_response.status_code, 404)
        self.assertEqual(edge_response.status_code, 404)
        self.assertEqual(evidence_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.other_topic.refresh_from_db()
        self.assertEqual(self.other_topic.name, "private topic")
        self.assertFalse(TopicEdge.objects.exists())
        self.assertFalse(TopicEvidence.objects.exists())

    def test_topic_cannot_link_evidence_owned_by_another_user(self):
        source = Source.objects.create(owner=self.other_user, display_title="private.pdf")
        version = SourceVersion.objects.create(
            source=source,
            content_sha256="a" * 64,
            object_key="uploads/private.pdf",
            byte_size=10,
        )
        evidence = EvidenceUnit.objects.create(
            source_version_id=str(version.id),
            bundle_id=uuid.uuid4(),
            content="private evidence",
            page_number=1,
        )

        response = self.client.post(
            f"/api/topics/{self.owner_topic.id}/evidence/",
            {"evidence_unit_ids": [str(evidence.id)]},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(TopicEvidence.objects.filter(topic=self.owner_topic).exists())
