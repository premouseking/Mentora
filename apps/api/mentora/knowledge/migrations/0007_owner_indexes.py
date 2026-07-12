from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0006_user_ownership")]

    operations = [
        migrations.RemoveIndex(model_name="libraryfolder", name="knowledge_f_owner_i_4f7030_idx"),
        migrations.RemoveIndex(model_name="source", name="knowledge_s_owner_i_e69aa7_idx"),
        migrations.AlterField(
            model_name="libraryfolder", name="legacy_owner_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="source", name="legacy_owner_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AlterField(
            model_name="uploadsession", name="legacy_owner_id",
            field=models.CharField(blank=True, db_index=True, default="", max_length=64),
        ),
        migrations.AddIndex(
            model_name="libraryfolder",
            index=models.Index(fields=["owner"], name="knowledge_f_owner_i_4f7030_idx"),
        ),
        migrations.AddIndex(
            model_name="source",
            index=models.Index(fields=["owner", "created_at"], name="knowledge_s_owner_i_e69aa7_idx"),
        ),
    ]
