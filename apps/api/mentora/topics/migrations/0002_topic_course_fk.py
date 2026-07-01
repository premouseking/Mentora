"""Topic 增加 Course FK、重命名 legacy 字段并回填。"""

import django.db.models.deletion
from django.db import migrations, models


def backfill_topic_course(apps, schema_editor):
    Topic = apps.get_model("topics", "Topic")
    Course = apps.get_model("courses", "Course")

    for topic in Topic.objects.all().iterator():
        if topic.course_id:
            continue
        legacy = (getattr(topic, "legacy_course_key", None) or "").strip()
        if not legacy:
            continue
        course = Course.objects.filter(id=legacy).first()
        if course is None:
            course = Course.objects.filter(session_id=legacy).first()
        if course is not None:
            topic.course_id = course.id
            topic.save(update_fields=["course_id"])


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0009_session_archived_status"),
        ("topics", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="topic",
            old_name="course_id",
            new_name="legacy_course_key",
        ),
        # RenameField 不会重命名 db_index 自动生成的索引名，AddField(course FK) 会复用 course_id 列名导致冲突
        migrations.RunSQL(
            sql=[
                "DROP INDEX IF EXISTS topics_topic_course_id_308c59d3;",
                "DROP INDEX IF EXISTS topics_topic_course_id_308c59d3_like;",
            ],
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddField(
            model_name="topic",
            name="course",
            field=models.ForeignKey(
                blank=True,
                help_text="正式课程 FK",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="topics",
                to="courses.course",
            ),
        ),
        migrations.AlterField(
            model_name="topic",
            name="legacy_course_key",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                help_text="legacy 关联键（deprecated，见 ADR-0008）",
                max_length=128,
            ),
        ),
        migrations.RunPython(backfill_topic_course, migrations.RunPython.noop),
    ]
