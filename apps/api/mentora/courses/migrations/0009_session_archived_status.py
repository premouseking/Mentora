"""将 started 会话映射为 archived（ADR-0008）。"""

from django.db import migrations


def migrate_started_to_archived(apps, schema_editor):
    Session = apps.get_model("courses", "CourseCreationSession")
    Session.objects.filter(status="started").update(status="archived")


class Migration(migrations.Migration):

    dependencies = [
        ("courses", "0008_add_profile_supplement"),
    ]

    operations = [
        migrations.RunPython(migrate_started_to_archived, migrations.RunPython.noop),
    ]
