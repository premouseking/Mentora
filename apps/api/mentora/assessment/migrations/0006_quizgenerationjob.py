# Generated manually for quiz generation acceleration

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("assessment", "0005_add_item_provenance"),
    ]

    operations = [
        migrations.CreateModel(
            name="QuizGenerationJob",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "等待中"),
                            ("running", "生成中"),
                            ("succeeded", "已完成"),
                            ("failed", "失败"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("progress", models.CharField(blank=True, default="", max_length=128)),
                ("progress_pct", models.IntegerField(default=0)),
                ("error_message", models.TextField(blank=True, default="")),
                ("error_code", models.CharField(blank=True, default="", max_length=64)),
                ("generation_cache_key", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("request_payload", models.JSONField(default=dict)),
                ("result_session_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "出题任务",
                "verbose_name_plural": "出题任务",
                "db_table": "assessment_generation_job",
                "indexes": [
                    models.Index(fields=["generation_cache_key", "-updated_at"], name="assessment_g_cache_k_7f0a0d_idx"),
                ],
            },
        ),
    ]
