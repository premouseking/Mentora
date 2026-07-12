# Generated manually to repair databases where 0006 was recorded but position was not created.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("learning", "0007_alter_learningplantasktemplate_options"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE learning_plan_task_template
                ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 0;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
