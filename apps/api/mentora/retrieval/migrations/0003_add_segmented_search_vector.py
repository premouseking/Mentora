"""添加 segmented_content 和 search_vector 字段，创建 GIN 索引。"""

import django.contrib.postgres.indexes
import django.contrib.postgres.search
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("retrieval", "0002_rename_chunk_srcver_idx_retrieval_c_source__161748_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="evidenceunit",
            name="segmented_content",
            field=models.TextField(
                default="",
                help_text="jieba 分词后的文本（空格分隔），用于 PG tsvector 索引。",
            ),
        ),
        migrations.AddField(
            model_name="evidenceunit",
            name="search_vector",
            field=django.contrib.postgres.search.SearchVectorField(
                help_text="PG 全文检索向量，由应用层在写入时通过 jieba 分词 + to_tsvector 生成。",
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="evidenceunit",
            index=django.contrib.postgres.indexes.GinIndex(
                fields=["search_vector"],
                name="evidence_search_vector_idx",
            ),
        ),
    ]
