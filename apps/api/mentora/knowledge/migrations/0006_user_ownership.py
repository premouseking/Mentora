
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_owners(apps, schema_editor):
    User = apps.get_model("users", "User")
    Source = apps.get_model("knowledge", "Source")
    UploadSession = apps.get_model("knowledge", "UploadSession")
    LibraryFolder = apps.get_model("knowledge", "LibraryFolder")

    dev_user, created = User.objects.get_or_create(
        email=getattr(settings, "DEV_USER_EMAIL", "dev@mentora.local"),
        defaults={"display_name": "Mentora Dev", "password": "!"},
    )
    if created and not dev_user.password:
        dev_user.password = "!"
        dev_user.save(update_fields=["password"])

    dev_owner_id = getattr(settings, "DEV_OWNER_ID", "dev-user")
    users = {str(user.id): user.id for user in User.objects.all().only("id")}
    for Model in (Source, UploadSession, LibraryFolder):
        for row in Model.objects.filter(owner__isnull=True).iterator():
            legacy = row.legacy_owner_id
            owner_id = dev_user.id if legacy == dev_owner_id else users.get(legacy)
            if owner_id:
                Model.objects.filter(pk=row.pk).update(owner_id=owner_id)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("knowledge", "0005_coursesource_archived_at"),
    ]

    operations = [
        migrations.RenameField(model_name="source", old_name="owner_id", new_name="legacy_owner_id"),
        migrations.RenameField(model_name="uploadsession", old_name="owner_id", new_name="legacy_owner_id"),
        migrations.RenameField(model_name="libraryfolder", old_name="owner_id", new_name="legacy_owner_id"),
        # 先移除旧 owner_id 的自动索引，避免与新 FK 的 owner_id 自动索引重名。
        migrations.AlterField(
            model_name="source", name="legacy_owner_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="uploadsession", name="legacy_owner_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="libraryfolder", name="legacy_owner_id",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="source", name="owner",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="knowledge_sources", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="uploadsession", name="owner",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="upload_sessions", to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name="libraryfolder", name="owner",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="library_folders", to=settings.AUTH_USER_MODEL),
        ),
        migrations.RunPython(backfill_owners, migrations.RunPython.noop),
    ]
