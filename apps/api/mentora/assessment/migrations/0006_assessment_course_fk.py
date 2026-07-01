"""AssessmentItem/Session 增加 Course FK 并回填。"""

import django.db.models.deletion
from django.db import migrations, models


def _resolve_course_id(Course, session_uuid):
    course = Course.objects.filter(id=session_uuid).first()
    if course is not None:
        return course.id
    course = Course.objects.filter(session_id=session_uuid).first()
    return course.id if course else None


def backfill_assessment_course(apps, schema_editor):
    Course = apps.get_model("courses", "Course")
    AssessmentItem = apps.get_model("assessment", "AssessmentItem")
    AssessmentSession = apps.get_model("assessment", "AssessmentSession")

    for item in AssessmentItem.objects.all().iterator():
        if item.course_id:
            continue
        cid = _resolve_course_id(Course, item.course_session_id)
        if cid:
            item.course_id = cid
            item.save(update_fields=["course_id"])

    for session in AssessmentSession.objects.all().iterator():
        if session.course_id:
            continue
        cid = _resolve_course_id(Course, session.course_session_id)
        if cid:
            session.course_id = cid
            session.save(update_fields=["course_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0009_session_archived_status"),
        ("assessment", "0005_add_item_provenance"),
    ]

    operations = [
        migrations.AddField(
            model_name="assessmentitem",
            name="course",
            field=models.ForeignKey(
                blank=True,
                help_text="正式课程 FK",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assessment_items",
                to="courses.course",
            ),
        ),
        migrations.AlterField(
            model_name="assessmentitem",
            name="course_session_id",
            field=models.UUIDField(
                db_index=True,
                help_text="建课会话 ID（deprecated，见 ADR-0008）",
            ),
        ),
        migrations.AddField(
            model_name="assessmentsession",
            name="course",
            field=models.ForeignKey(
                blank=True,
                help_text="正式课程 FK",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="assessment_sessions",
                to="courses.course",
            ),
        ),
        migrations.AlterField(
            model_name="assessmentsession",
            name="course_session_id",
            field=models.UUIDField(
                db_index=True,
                help_text="建课会话 ID（deprecated，见 ADR-0008）",
            ),
        ),
        migrations.RunPython(backfill_assessment_course, migrations.RunPython.noop),
    ]
