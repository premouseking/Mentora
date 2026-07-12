# Generated migration for course agent session models

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("agent_runtime", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CourseAgentSession",
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
                ("course_id", models.UUIDField(db_index=True, help_text="Course.id")),
                (
                    "course_session_id",
                    models.UUIDField(db_index=True, help_text="CourseCreationSession.id"),
                ),
                (
                    "owner_id",
                    models.CharField(
                        blank=True,
                        default="",
                        help_text="用户 ID（预留）",
                        max_length=128,
                    ),
                ),
                ("title", models.CharField(blank=True, default="", max_length=256)),
                (
                    "status",
                    models.CharField(
                        choices=[("active", "进行中"), ("archived", "已归档")],
                        default="active",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "课程 Agent 会话",
                "verbose_name_plural": "课程 Agent 会话",
                "db_table": "agent_runtime_course_agent_session",
            },
        ),
        migrations.CreateModel(
            name="CourseAgentMessage",
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
                (
                    "role",
                    models.CharField(
                        choices=[("user", "用户"), ("assistant", "助手")],
                        max_length=16,
                    ),
                ),
                ("content", models.TextField(blank=True, default="")),
                (
                    "citations_json",
                    models.JSONField(default=list, help_text="引用列表"),
                ),
                (
                    "metadata_json",
                    models.JSONField(default=dict, help_text="mentions 等扩展元数据"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "session",
                    models.ForeignKey(
                        help_text="所属会话",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="messages",
                        to="agent_runtime.courseagentsession",
                    ),
                ),
            ],
            options={
                "verbose_name": "课程 Agent 消息",
                "verbose_name_plural": "课程 Agent 消息",
                "db_table": "agent_runtime_course_agent_message",
                "ordering": ["created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="courseagentsession",
            index=models.Index(
                fields=["course_id", "-updated_at"],
                name="ar_cas_course_updated_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="courseagentsession",
            index=models.Index(
                fields=["course_session_id", "-updated_at"],
                name="ar_cas_session_updated_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="courseagentmessage",
            index=models.Index(
                fields=["session", "created_at"],
                name="ar_cam_session_created_idx",
            ),
        ),
    ]
