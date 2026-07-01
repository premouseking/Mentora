"""LearningPlan 增加 Course FK 并回填。"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_learning_plan_course(apps, schema_editor):
    LearningPlan = apps.get_model("learning", "LearningPlan")
    Course = apps.get_model("courses", "Course")
    for plan in LearningPlan.objects.all().iterator():
        if plan.course_id:
            continue
        course = Course.objects.filter(session_id=plan.course_session_id).first()
        if course is not None:
            plan.course_id = course.id
            plan.save(update_fields=["course_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0009_session_archived_status"),
        ("learning", "0004_ai_explanation_metadata"),
    ]

    operations = [
        migrations.AddField(
            model_name="learningplan",
            name="course",
            field=models.ForeignKey(
                blank=True,
                help_text="正式课程 FK；建课期可为空",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="learning_plans",
                to="courses.course",
            ),
        ),
        migrations.AlterField(
            model_name="learningplan",
            name="course_session_id",
            field=models.UUIDField(
                db_index=True,
                help_text="建课会话 ID（deprecated，见 ADR-0008）",
            ),
        ),
        migrations.RunPython(backfill_learning_plan_course, migrations.RunPython.noop),
    ]
