"""数据库迁移与扩展 smoke。"""

import pytest
from django.db import connection


@pytest.mark.django_db
def test_pg_extensions_exist():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_trgm')"
        )
        names = {row[0] for row in cursor.fetchall()}
    assert "vector" in names
    assert "pg_trgm" in names
