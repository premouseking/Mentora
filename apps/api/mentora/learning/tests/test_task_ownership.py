from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from mentora.learning.models import (
    LearningPlan,
    LearningPlanPhase,
    LearningPlanRevision,
    LearningPlanTaskTemplate,
    LearningPlanUnit,
    LearningTask,
)


class LearningTaskOwnershipTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(
            email="task-owner@example.com", password="test-pass-123"
        )
        self.other_user = user_model.objects.create_user(
            email="task-other@example.com", password="test-pass-123"
        )
        self.course_session_id = self._uuid()
        plan = LearningPlan.objects.create(owner=self.owner, course_session_id=self.course_session_id)
        revision = LearningPlanRevision.objects.create(
            learning_plan=plan,
            status=LearningPlanRevision.Status.ACTIVE,
        )
        plan.active_revision_id = revision.id
        plan.save(update_fields=["active_revision_id"])
        phase = LearningPlanPhase.objects.create(
            revision=revision,
            position=0,
            title="基础阶段",
        )
        unit = LearningPlanUnit.objects.create(
            revision=revision,
            phase=phase,
            position=0,
            title="第一单元",
        )
        self.template = LearningPlanTaskTemplate.objects.create(
            revision=revision,
            unit=unit,
            title="阅读任务",
            task_type=LearningPlanTaskTemplate.TaskType.LECTURE,
        )

    @staticmethod
    def _uuid():
        import uuid

        return uuid.uuid4()

    def test_owner_can_open_task_detail_by_template_id(self):
        client = APIClient()
        client.force_authenticate(user=self.owner)

        response = client.get(f"/api/learning/tasks/{self.template.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["template_id"], str(self.template.id))
        self.assertEqual(LearningTask.objects.filter(template=self.template).count(), 1)

    def test_other_user_cannot_materialize_task_by_template_id(self):
        client = APIClient()
        client.force_authenticate(user=self.other_user)

        response = client.post(f"/api/learning/tasks/{self.template.id}/complete/", {})

        self.assertEqual(response.status_code, 404)
        self.assertFalse(LearningTask.objects.filter(template=self.template).exists())

    def test_assessment_task_resolution_does_not_materialize_other_users_task(self):
        from mentora.assessment.views import _resolve_task_unit_id

        unit_id, error = _resolve_task_unit_id(
            str(self.template.id), str(self.course_session_id), owner=self.other_user
        )

        self.assertEqual(unit_id, "")
        self.assertIsNotNone(error)
        self.assertFalse(LearningTask.objects.filter(template=self.template).exists())
