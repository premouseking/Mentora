"""Assessment：course_session_id → creation_session FK。"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_creation_session(apps, schema_editor):
    AssessmentItem = apps.get_model("assessment", "AssessmentItem")
    AssessmentSession = apps.get_model("assessment", "AssessmentSession")
    CourseCreationSession = apps.get_model("courses", "CourseCreationSession")

    for item in AssessmentItem.objects.all().iterator():
        if item.creation_session_id:
            continue
        session_id = getattr(item, "course_session_id", None)
        if not session_id:
            continue
        session = CourseCreationSession.objects.filter(id=session_id).first()
        if session is not None:
            item.creation_session_id = session.id
            item.save(update_fields=["creation_session_id"])

    for session_row in AssessmentSession.objects.all().iterator():
        if session_row.creation_session_id:
            continue
        session_id = getattr(session_row, "course_session_id", None)
        if not session_id:
            continue
        session = CourseCreationSession.objects.filter(id=session_id).first()
        if session is not None:
            session_row.creation_session_id = session.id
            session_row.save(update_fields=["creation_session_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("assessment", "0006_assessment_course_fk"),
        ("courses", "0010_drop_course_session_id"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="assessmentitem",
            name="assessment__course__db0d23_idx",
        ),
        migrations.RemoveIndex(
            model_name="assessmentsession",
            name="assessment__course__6ff0ab_idx",
        ),
        migrations.AddField(
            model_name="assessmentitem",
            name="creation_session",
            field=models.ForeignKey(
                blank=True,
                help_text="建课期关联；确认后以 course FK 为主",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assessment_items",
                to="courses.coursecreationsession",
            ),
        ),
        migrations.AddField(
            model_name="assessmentsession",
            name="creation_session",
            field=models.ForeignKey(
                blank=True,
                help_text="建课期关联；确认后以 course FK 为主",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assessment_sessions",
                to="courses.coursecreationsession",
            ),
        ),
        migrations.RunPython(backfill_creation_session, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="assessmentitem",
            name="course_session_id",
        ),
        migrations.RemoveField(
            model_name="assessmentsession",
            name="course_session_id",
        ),
        migrations.AddIndex(
            model_name="assessmentitem",
            index=models.Index(
                fields=["creation_session"], name="assessment__creatio_5ef045_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="assessmentsession",
            index=models.Index(
                fields=["creation_session", "-created_at"],
                name="assessment__creatio_4b6e5a_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="assessmentsession",
            index=models.Index(
                fields=["course", "-created_at"], name="assessment__course__bfe56d_idx"
            ),
        ),
    ]
