from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0004_add_folder"),
    ]

    operations = [
        migrations.AddField(
            model_name="coursesource",
            name="archived_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                help_text="从课程内隐藏该资料关联，不删除资源库中的 Source",
                null=True,
            ),
        ),
    ]
