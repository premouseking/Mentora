import django.db.models.deletion
from django.db import migrations, models


def backfill_topic_course(apps, schema_editor):
    topic_model = apps.get_model("topics", "Topic")
    course_model = apps.get_model("courses", "Course")

    for topic in topic_model.objects.all().iterator():
        legacy_key = (topic.legacy_course_key or "").strip()
        if not legacy_key:
            continue
        course = course_model.objects.filter(id=legacy_key).first()
        if course is None:
            course = course_model.objects.filter(session_id=legacy_key).first()
        if course is not None:
            topic.course_id = course.id
            topic.save(update_fields=["course_id"])


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0010_course_owner_coursecreationsession_owner"),
        ("topics", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="topic",
            old_name="course_id",
            new_name="legacy_course_key",
        ),
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
                help_text="兼容建课会话 ID 的遗留关联键",
                max_length=128,
            ),
        ),
        migrations.RunPython(backfill_topic_course, migrations.RunPython.noop),
    ]
