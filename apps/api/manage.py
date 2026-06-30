#!/usr/bin/env python
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    # 开发环境自动执行未应用的 migration（runserver 启动时）
    if len(sys.argv) >= 2 and sys.argv[1] == "runserver":
        _auto_migrate()

    execute_from_command_line(sys.argv)


def _auto_migrate() -> None:
    """开发环境自动 migrate，避免手动执行 python manage.py migrate。"""
    import django
    django.setup()
    from django.core.management import call_command
    from io import StringIO

    out = StringIO()
    try:
        call_command("migrate", "--noinput", stdout=out)
        output = out.getvalue()
        if "No migrations" not in output and "No changes" not in output:
            applied = [l for l in output.splitlines() if "Applying" in l]
            if applied:
                print(f"\n[auto-migrate] 已自动应用 {len(applied)} 个迁移:")
                for line in applied:
                    print(f"  {line.strip()}")
                print()
    except Exception:
        pass  # 首次启动或无数据库时静默跳过


if __name__ == "__main__":
    main()

