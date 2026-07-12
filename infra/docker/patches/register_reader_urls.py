"""向现有 config/urls.py 注册 /api/resources/* 阅读器路由（容器热补丁用）。"""

from __future__ import annotations

from pathlib import Path

URLS_PATH = Path("/app/config/urls.py")

IMPORT_BLOCK = """from mentora.knowledge.reader_views import (
    list_resources,
    resource_info,
    resource_page_thumbnails,
    resource_pdf,
    resource_reader,
    resource_reader_blocks,
    resource_reader_meta,
)
"""

ROUTE_BLOCK = """    # LightRead-like 阅读器
    path("api/resources/", list_resources, name="resource-list"),
    path("api/resources/<uuid:resource_id>/info/", resource_info, name="resource-info"),
    path("api/resources/<uuid:resource_id>/reader/meta/", resource_reader_meta, name="resource-reader-meta"),
    path("api/resources/<uuid:resource_id>/reader/blocks/", resource_reader_blocks, name="resource-reader-blocks"),
    path("api/resources/<uuid:resource_id>/reader/", resource_reader, name="resource-reader"),
    path("api/resources/<uuid:resource_id>/pdf/", resource_pdf, name="resource-pdf"),
    path("api/resources/<uuid:resource_id>/pages/thumbnail/", resource_page_thumbnails, name="resource-thumbnails"),
"""


def main() -> None:
    text = URLS_PATH.read_text(encoding="utf-8")
    if "resource_reader_meta" in text:
        print("reader routes already registered")
        return

    anchor = "from mentora.parsing.views import get_benchmark, preview_parse"
    if anchor not in text:
        raise SystemExit(f"anchor not found in {URLS_PATH}")

    text = text.replace(anchor, IMPORT_BLOCK + anchor, 1)

    anchor = '    path("api/library/sources/", list_sources, name="library-sources"),'
    if anchor not in text:
        raise SystemExit("library routes anchor not found")

    text = text.replace(anchor, ROUTE_BLOCK + anchor, 1)
    URLS_PATH.write_text(text, encoding="utf-8")
    print("reader routes registered")


if __name__ == "__main__":
    main()
