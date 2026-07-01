"""AI 讲解文档：metadata 字段与 updated_at。"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0003_add_history_event"),
    ]

    operations = [
        migrations.AddField(
            model_name="learninghistoryevent",
            name="metadata",
            field=models.JSONField(blank=True, default=dict, help_text="扩展元数据，如 keywords、doc_type"),
        ),
        migrations.AddField(
            model_name="learninghistoryevent",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AlterField(
            model_name="learninghistoryevent",
            name="detail",
            field=models.TextField(blank=True, default="", help_text="AI 讲解 Markdown 正文"),
        ),
        migrations.AlterField(
            model_name="learninghistoryevent",
            name="event_type",
            field=models.CharField(
                choices=[
                    ("task_completed", "完成学习任务"),
                    ("task_started", "开始学习任务"),
                    ("check_passed", "通过检查点"),
                    ("check_failed", "检查未通过"),
                    ("stage_changed", "阶段切换"),
                    ("plan_adjusted", "方案调整"),
                    ("source_added", "新增课程资料"),
                    ("source_updated", "资料版本更新"),
                    ("quiz_attempted", "尝试测验"),
                    ("skill_mastered", "技能掌握"),
                    ("course_started", "开始课程"),
                    ("course_paused", "暂停课程"),
                    ("ai_explanation", "AI 讲解文档"),
                ],
                max_length=20,
            ),
        ),
    ]
