import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0008_repair_task_template_position"),
    ]

    operations = [
        migrations.CreateModel(
            name="MistakeArchive",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("course_id", models.CharField(db_index=True, max_length=128)),
                ("item_id", models.UUIDField(db_index=True)),
                ("archived_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "错题归档",
                "verbose_name_plural": "错题归档",
                "db_table": "learning_mistake_archive",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("course_id", "item_id"),
                        name="learning_mistake_archive_uc",
                    )
                ],
            },
        ),
    ]
