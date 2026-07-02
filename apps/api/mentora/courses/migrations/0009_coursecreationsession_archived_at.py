from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0008_add_profile_supplement"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursecreationsession",
            name="archived_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="归档时间；非空表示会话已从课程列表隐藏",
                null=True,
            ),
        ),
    ]
