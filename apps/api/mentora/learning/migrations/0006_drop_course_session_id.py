"""LearningPlan：course_session_id → creation_session FK。"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_creation_session(apps, schema_editor):
    LearningPlan = apps.get_model("learning", "LearningPlan")
    CourseCreationSession = apps.get_model("courses", "CourseCreationSession")
    for plan in LearningPlan.objects.all().iterator():
        if plan.creation_session_id:
            continue
        session_id = getattr(plan, "course_session_id", None)
        if not session_id:
            continue
        session = CourseCreationSession.objects.filter(id=session_id).first()
        if session is not None:
            plan.creation_session_id = session.id
            plan.save(update_fields=["creation_session_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0010_drop_course_session_id"),
        ("learning", "0005_learningplan_course_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="learningplan",
            name="creation_session",
            field=models.OneToOneField(
                blank=True,
                help_text="建课期关联；确认后以 course FK 为主",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="learning_plan",
                to="courses.coursecreationsession",
            ),
        ),
        migrations.RunPython(backfill_creation_session, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="learningplan",
            name="course_session_id",
        ),
    ]
